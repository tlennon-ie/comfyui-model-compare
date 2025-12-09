"""CLIP Config Compare node for per-chain CLIP configuration.

This node allows configuring CLIP variations that connect to specific chain nodes.
Each CLIP slot can have:
- A clip_type selection (determines if dual CLIP is needed)
- Primary CLIP model selection
- Secondary CLIP model selection (for dual CLIP types like FLUX, Hunyuan)
- Device selection (default or cpu for VRAM savings)
- A custom label for display

CLIP Config nodes connect to SamplingConfigChain nodes via clip_config input.
"""

import folder_paths


class ClipConfigCompare:
    """Configure CLIP variations for model comparison chains."""
    
    CATEGORY = "Model Compare/Loaders"
    
    # CLIP types that require dual CLIP models
    DUAL_CLIP_TYPES = ["flux", "hunyuan_video", "hunyuan_video_15"]
    
    # All available CLIP types
    CLIP_TYPES = [
        "default", "sd", "sdxl", "sd3", 
        "flux", "flux2", "flux_kontext", 
        "wan", "wan22", 
        "hunyuan_video", "hunyuan_video_15", 
        "qwen", "qwen_edit", 
        "lumina2"
    ]
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the CLIP Config Compare node."""
        clip_models = cls._get_cached_clips()
        
        inputs = {
            "required": {
                "num_clips": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of CLIP variations to configure"
                }),
            },
            "optional": {},
        }
        
        # Add CLIP fields for each slot (0-9)
        for i in range(10):
            # CLIP type determines if we need single or dual CLIP
            inputs["optional"][f"clip_type_{i}"] = (
                cls.CLIP_TYPES,
                {"default": "default",
                 "tooltip": f"CLIP {i+1}: Type determines CLIP loading (flux/hunyuan need dual CLIP)"},
            )
            
            # Primary CLIP model (or CLIP A for dual types)
            inputs["optional"][f"clip_{i}"] = (
                ["NONE", "__baked__"] + clip_models,
                {"default": "NONE" if i > 0 else (clip_models[0] if clip_models else "NONE"),
                 "tooltip": f"CLIP {i+1}: Primary CLIP model (or CLIP A for dual types). Use __baked__ for checkpoint's embedded CLIP"},
            )
            
            # Secondary CLIP model (CLIP B for dual types)
            inputs["optional"][f"clip_{i}_2"] = (
                ["NONE"] + clip_models,
                {"default": "NONE",
                 "tooltip": f"CLIP {i+1}: Secondary CLIP model (CLIP B for flux/hunyuan dual CLIP)"},
            )
            
            # Device selection
            inputs["optional"][f"clip_{i}_device"] = (
                ["default", "cpu"],
                {"default": "default",
                 "tooltip": f"CLIP {i+1}: Device for CLIP model. Use 'cpu' to reduce VRAM usage"},
            )
            
            # Custom label
            inputs["optional"][f"clip_{i}_label"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"CLIP {i+1}: Custom display label (leave empty to use model name)"
                },
            )
        
        return inputs
    
    RETURN_TYPES = ("CLIP_COMPARE_CONFIG",)
    RETURN_NAMES = ("clip_config",)
    FUNCTION = "configure_clips"
    
    @classmethod
    def _get_cached_clips(cls):
        """Get list of available CLIP models."""
        try:
            return folder_paths.get_filename_list("clip")
        except:
            return []
    
    def configure_clips(self, num_clips, **kwargs):
        """Configure CLIPs and return a config object.
        
        Args:
            num_clips: Number of CLIP slots to use
            **kwargs: CLIP fields (clip_type_0, clip_0, clip_0_2, etc.)
        
        Returns:
            CLIP_COMPARE_CONFIG dict containing all CLIP configurations
        """
        config = {
            "clips": [],
        }
        
        # Process each CLIP slot
        for i in range(num_clips):
            clip_type = kwargs.get(f"clip_type_{i}", "default")
            clip_name = kwargs.get(f"clip_{i}", "NONE")
            clip_name_2 = kwargs.get(f"clip_{i}_2", "NONE")
            clip_device = kwargs.get(f"clip_{i}_device", "default")
            clip_label = kwargs.get(f"clip_{i}_label", "")
            
            if clip_name == "NONE":
                continue
            
            # Determine if this clip_type needs dual CLIP
            needs_dual_clip = clip_type in self.DUAL_CLIP_TYPES
            
            # Handle baked CLIP
            if clip_name == "__baked__":
                clip_entry = {
                    "type": "baked",
                    "clip_type": clip_type,
                    "device": clip_device,
                    "label": clip_label if clip_label else "Baked CLIP",
                }
                config["clips"].append(clip_entry)
                continue
            
            # Get primary CLIP path
            clip_path = folder_paths.get_full_path("clip", clip_name)
            if clip_path is None:
                print(f"[ClipConfigCompare] Warning: Could not find CLIP: {clip_name}")
                continue
            
            # Create CLIP entry based on type
            if needs_dual_clip and clip_name_2 != "NONE":
                # Dual CLIP (pair type)
                clip_path_2 = folder_paths.get_full_path("clip", clip_name_2)
                if clip_path_2 is None:
                    print(f"[ClipConfigCompare] Warning: Could not find secondary CLIP: {clip_name_2}")
                    # Fall back to single CLIP
                    clip_entry = {
                        "type": "single",
                        "model": clip_name,
                        "model_path": clip_path,
                        "clip_type": clip_type,
                        "device": clip_device,
                        "label": clip_label if clip_label else clip_name,
                    }
                else:
                    clip_entry = {
                        "type": "pair",
                        "a": clip_name,
                        "b": clip_name_2,
                        "a_path": clip_path,
                        "b_path": clip_path_2,
                        "clip_type": clip_type,
                        "device": clip_device,
                        "label": clip_label if clip_label else f"{clip_name}+{clip_name_2}",
                    }
            else:
                # Single CLIP
                clip_entry = {
                    "type": "single",
                    "model": clip_name,
                    "model_path": clip_path,
                    "clip_type": clip_type,
                    "device": clip_device,
                    "label": clip_label if clip_label else clip_name,
                }
            
            config["clips"].append(clip_entry)
        
        return (config,)
    
    @classmethod
    def IS_CHANGED(cls, num_clips, **kwargs):
        """Check if node inputs have changed."""
        import hashlib
        
        hash_parts = [str(num_clips)]
        
        for i in range(num_clips):
            hash_parts.append(kwargs.get(f"clip_type_{i}", "default"))
            hash_parts.append(kwargs.get(f"clip_{i}", "NONE"))
            hash_parts.append(kwargs.get(f"clip_{i}_2", "NONE"))
            hash_parts.append(kwargs.get(f"clip_{i}_device", "default"))
            hash_parts.append(kwargs.get(f"clip_{i}_label", ""))
        
        hash_input = "|".join(hash_parts)
        return hashlib.md5(hash_input.encode()).hexdigest()


# Export for __init__.py
NODE_CLASS_MAPPINGS = {
    "ClipConfigCompare": ClipConfigCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ClipConfigCompare": "Ⓜ️ Model Compare - CLIP Config",
}
