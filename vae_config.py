"""VAE Config Compare node for per-chain VAE configuration.

This node allows configuring VAE variations that connect to specific chain nodes.
Each VAE slot can have:
- A VAE model selection
- A custom label for display

VAE Config nodes connect to SamplingConfigChain nodes via vae_config input.
"""

import folder_paths


class VaeConfigCompare:
    """Configure VAE variations for model comparison chains."""
    
    CATEGORY = "Model Compare/Loaders"
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the VAE Config Compare node."""
        vaes = cls._get_cached_vaes()
        
        inputs = {
            "required": {
                "num_vaes": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of VAE variations to configure"
                }),
            },
            "optional": {},
        }
        
        # Add VAE fields for each slot (0-9)
        for i in range(10):
            inputs["optional"][f"vae_{i}"] = (
                ["NONE", "__baked__"] + vaes,
                {"default": "NONE" if i > 0 else (vaes[0] if vaes else "NONE"),
                 "tooltip": f"VAE {i+1}: Select VAE model or __baked__ to use checkpoint's embedded VAE"},
            )
            inputs["optional"][f"vae_{i}_label"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"VAE {i+1}: Custom display label (leave empty to use filename)"
                },
            )
        
        return inputs
    
    RETURN_TYPES = ("VAE_COMPARE_CONFIG",)
    RETURN_NAMES = ("vae_config",)
    FUNCTION = "configure_vaes"
    
    @classmethod
    def _get_cached_vaes(cls):
        """Get list of available VAE models."""
        try:
            return folder_paths.get_filename_list("vae")
        except:
            return []
    
    def configure_vaes(self, num_vaes, **kwargs):
        """Configure VAEs and return a config object.
        
        Args:
            num_vaes: Number of VAE slots to use
            **kwargs: VAE fields (vae_0, vae_0_label, etc.)
        
        Returns:
            VAE_COMPARE_CONFIG dict containing all VAE configurations
        """
        config = {
            "vaes": [],
        }
        
        # Process each VAE slot
        for i in range(num_vaes):
            vae_name = kwargs.get(f"vae_{i}", "NONE")
            vae_label = kwargs.get(f"vae_{i}_label", "")
            
            if vae_name == "NONE":
                continue
            
            # Get VAE path (unless baked)
            vae_path = None
            if vae_name != "__baked__":
                vae_path = folder_paths.get_full_path("vae", vae_name)
                if vae_path is None:
                    print(f"[VaeConfigCompare] Warning: Could not find VAE: {vae_name}")
                    continue
            
            # Create VAE entry
            vae_entry = {
                "name": vae_name,
                "path": vae_path,
                "label": vae_label if vae_label else vae_name,
                "is_baked": vae_name == "__baked__",
            }
            
            config["vaes"].append(vae_entry)
        
        return (config,)
    
    @classmethod
    def IS_CHANGED(cls, num_vaes, **kwargs):
        """Check if node inputs have changed."""
        import hashlib
        
        hash_parts = [str(num_vaes)]
        
        for i in range(num_vaes):
            hash_parts.append(kwargs.get(f"vae_{i}", "NONE"))
            hash_parts.append(kwargs.get(f"vae_{i}_label", ""))
        
        hash_input = "|".join(hash_parts)
        return hashlib.md5(hash_input.encode()).hexdigest()


# Export for __init__.py
NODE_CLASS_MAPPINGS = {
    "VaeConfigCompare": VaeConfigCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VaeConfigCompare": "Ⓜ️ Model Compare - VAE Config",
}
