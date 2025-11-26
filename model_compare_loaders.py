"""
Model Compare Loaders Node

LAZY LOADING: This loader stores paths/configurations only.
Actual model loading is deferred to the sampler for memory efficiency.
"""

import hashlib
import folder_paths
import comfy.sd
import comfy.utils
import comfy.model_management
import torch
import os
import time

class ModelCompareLoaders:
    """
    Node for loading multiple models/VAEs/CLIPs/LoRAs for comparison.
    Generates a configuration dictionary for the sampler.
    """
    
    # Version with timestamp to force UI refresh
    _version = int(time.time() % 10000)  # Last 4 digits of timestamp for UI cache busting

    def __init__(self):
        self.device = comfy.model_management.get_torch_device()

    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the node with preset system."""
        combined_models = cls._get_combined_model_list()
        vaes = cls._get_cached_models("vae")
        clip_models = cls._get_cached_models("clip")
        loras = cls._get_cached_models("loras")

        inputs = {
            "required": {
                "preset": (["STANDARD", "SDXL", "PONY", "WAN2.1", "WAN2.2", "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "QWEN", "FLUX", "FLUX2", "Z_IMAGE"], {
                    "default": "STANDARD",
                    "tooltip": "Model preset - determines available configuration options and sampling behavior. FLUX = dual CLIPs, FLUX2 = single CLIP, Z_IMAGE = Lumina2 with QWEN3-4B"
                }),
                "diffusion_model": (
                    ["NONE"] + combined_models,
                    {"default": combined_models[0] if combined_models else "NONE",
                     "tooltip": "Primary model (or High Noise model for WAN 2.2)"},
                ),
                "baked_vae_clip": ("BOOLEAN", {
                    "default": False,
                    "label_on": "Use Baked VAE/CLIP",
                    "label_off": "Use Separate VAE/CLIP",
                    "tooltip": "If enabled, loads VAE and CLIP from the checkpoint itself (only for Checkpoints)"
                }),
                "diffusion_model_label": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "tooltip": "Custom display label for base model (leave empty to use model filename)"
                    },
                ),
                "diffusion_model_low": (
                    ["NONE"] + combined_models,
                    {"default": "NONE",
                     "tooltip": "Low Noise model (only for WAN 2.2)"},
                ),
                "vae": (
                    ["NONE"] + vaes,
                    {"default": vaes[0] if vaes else "NONE",
                     "tooltip": "Primary VAE for base model (ignored if Baked VAE/CLIP is ON). Each variation has its own vae_variation_i field."},
                ),
                "clip_model": (
                    ["NONE"] + clip_models,
                    {"default": clip_models[0] if clip_models else "NONE",
                     "tooltip": "Primary CLIP for base model (ignored if Baked VAE/CLIP is ON). Each variation has its own clip_model_variation_i field."},
                ),
                "clip_model_2": (
                    ["NONE"] + clip_models,
                    {"default": "NONE",
                     "tooltip": "Secondary CLIP (for Hunyuan Dual CLIP and FLUX Dual CLIP). Not used for FLUX2."},
                ),
                "clip_type": (
                    ["default", "sd", "sdxl", "sd3", "flux", "flux2", "wan", "wan22", "hunyuan_video", "hunyuan_video_15", "qwen", "lumina2"],
                    {"default": "default",
                     "tooltip": "CLIP model type (auto-adjusted based on preset). Use wan22 for High/Low noise model pairing. lumina2 for Z Image model."},
                ),
                "clip_device": (
                    ["default", "cpu"],
                    {"default": "default",
                     "tooltip": "Device for base CLIP model. Use 'cpu' to reduce VRAM usage when comparing large models."},
                ),
                "num_diffusion_models": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of diffusion model variations to compare",
                }),
                "num_vae_variations": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of VAE variations to compare",
                }),
                "num_clip_variations": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of CLIP variations",
                }),
            },
            "optional": {
                "prompt_config": ("PROMPT_COMPARE_CONFIG", {
                    "tooltip": "Optional: Connect PromptCompare node to compare multiple prompts"
                }),
                "global_config": ("GLOBAL_COMPARE_CONFIG", {
                    "tooltip": "Optional: Connect ModelCompareGlobals node to set global sampling parameters"
                }),
            },
        }

        # Add variations grouped by number (variation 1 all fields, then variation 2, etc.)
        for i in range(1, 5):
            # Diffusion model variation i
            inputs["optional"][f"diffusion_model_variation_{i}"] = (
                ["NONE"] + combined_models,
                {"default": "NONE",
                 "tooltip": f"Variation {i}: Primary model"},
            )
            inputs["optional"][f"diffusion_model_variation_{i}_label"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"Variation {i}: Custom display label (leave empty to use filename)"
                },
            )
            inputs["optional"][f"baked_vae_clip_variation_{i}"] = ("BOOLEAN", {
                "default": False,
                "label_on": "Baked",
                "label_off": "Separate",
                "tooltip": f"Variation {i}: Use baked VAE/CLIP"
            })
            inputs["optional"][f"diffusion_model_variation_{i}_low"] = (
                ["NONE"] + combined_models,
                {"default": "NONE",
                 "tooltip": f"Variation {i}: Low Noise model (WAN 2.2)"},
            )
            
            # CLIP variation i
            inputs["optional"][f"clip_model_variation_{i}"] = (
                ["NONE"] + clip_models,
                {"default": "NONE",
                 "tooltip": f"Variation {i}: Primary CLIP (independent of base baked_vae_clip)"},
            )
            inputs["optional"][f"clip_model_variation_{i}_2"] = (
                ["NONE"] + clip_models,
                {"default": "NONE",
                 "tooltip": f"Variation {i}: Secondary CLIP (Hunyuan/FLUX/WAN Dual CLIP support)"},
            )
            inputs["optional"][f"clip_type_variation_{i}"] = (
                ["default", "sd", "sdxl", "sd3", "flux", "flux2", "wan", "wan22", "hunyuan_video", "hunyuan_video_15", "qwen", "lumina2"],
                {"default": "default", "tooltip": f"Variation {i}: CLIP Type (wan22 enables High/Low noise model pairing, lumina2 for Z Image)"}
            )
            inputs["optional"][f"clip_device_variation_{i}"] = (
                ["default", "cpu"],
                {"default": "default", "tooltip": f"Variation {i}: Device for CLIP model. Use 'cpu' to reduce VRAM."}
            )
            
            # VAE variation i
            inputs["optional"][f"vae_variation_{i}"] = (
                ["NONE"] + vaes,
                {"default": "NONE", "tooltip": f"VAE Variation {i} (independent of base baked_vae_clip - set baked_vae_clip_variation_{i} toggle)"}
            )
        
        # LoRA variation inputs (connect LoRA Compare nodes per model variation)
        # Base model LoRA
        inputs["optional"]["lora_config"] = ("LORA_COMPARE_CONFIG", {
            "tooltip": "LoRA configuration for base model (connect from LoRA Compare node)"
        })
        
        # Variation LoRAs
        for i in range(1, 5):
            inputs["optional"][f"lora_config_variation_{i}"] = ("LORA_COMPARE_CONFIG", {
                "tooltip": f"LoRA configuration for variation {i} (connect from LoRA Compare node)"
            })

        return inputs

    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "load_models"
    CATEGORY = "loaders"

    @classmethod
    def _get_cached_models(cls, type_name):
        try:
            return folder_paths.get_filename_list(type_name)
        except:
            return []

    @classmethod
    def _get_combined_model_list(cls):
        """Get a list of both checkpoints and diffusion models."""
        checkpoints = cls._get_cached_models("checkpoints")
        diffusion_models = cls._get_cached_models("diffusion_models")
        
        ckpt_list = [f"[Checkpoint] {x}" for x in checkpoints]
        diff_list = [f"[Diffusion] {x}" for x in diffusion_models]
        
        return ckpt_list + diff_list

    def _parse_model_selector(self, selector_value):
        """Parse the combined model selector value."""
        if selector_value == "NONE":
            return None, None
            
        if selector_value.startswith("[Checkpoint] "):
            return "checkpoint", selector_value[13:]
        elif selector_value.startswith("[Diffusion] "):
            return "diffusion", selector_value[12:]
        else:
            # Fallback for legacy or direct names
            return "unknown", selector_value

    def load_models(self, preset, diffusion_model, baked_vae_clip, diffusion_model_low, vae, clip_model, clip_model_2, clip_type,
               num_diffusion_models, num_vae_variations, num_clip_variations,
               prompt_config=None, global_config=None,
               **kwargs):
        
        # 1. Determine CLIP Type based on Preset if default
        current_clip_type = clip_type  # Local variable we can modify
        if current_clip_type == "default":
            if preset == "SDXL" or preset == "PONY":
                current_clip_type = "sdxl"
            elif preset == "FLUX":
                current_clip_type = "flux"
            elif preset == "QWEN":
                current_clip_type = "qwen"
            elif preset == "WAN2.1" or preset == "WAN2.2":
                current_clip_type = "wan"
            elif preset == "HUNYUAN_VIDEO":
                current_clip_type = "hunyuan_video"
            elif preset == "HUNYUAN_VIDEO_15":
                current_clip_type = "hunyuan_video_15"
            elif preset == "Z_IMAGE":
                current_clip_type = "lumina2"
            else:
                current_clip_type = "sd"

        # 2. Load Base Model(s)
        model_variations = []
        
        def detect_model_clip_type(model_obj, current_clip_type):
            """Auto-detect CLIP type from model if possible."""
            if model_obj is None:
                return current_clip_type
                
            # Check model config for image_model
            if hasattr(model_obj, 'model') and hasattr(model_obj.model, 'model_config'):
                config = model_obj.model.model_config
                if hasattr(config, 'unet_config') and 'image_model' in config.unet_config:
                    image_model = config.unet_config['image_model']
                    if image_model == "flux":
                        return "flux"
                    elif image_model == "hunyuan_video":
                        # Check if it's Hunyuan 1.5 by looking for vision_in_dim
                        if hasattr(config, 'unet_config') and config.unet_config.get('vision_in_dim') == 1152:
                            return "hunyuan_video_15"
                        else:
                            return "hunyuan_video"
                    elif image_model == "qwen_image":
                        return "qwen"
                    elif image_model == "wan":
                        return "wan"
            
            return current_clip_type
        
        def load_model_entry(name_high, name_low, use_baked, current_clip_type, is_base=False, var_clip_type=None):
            """Create model entry storing paths for lazy loading.
            
            LAZY LOADING: No models are loaded here - only paths are stored.
            The sampler will load models on-demand per combination.
            
            Args:
                name_high: High noise model name
                name_low: Low noise model name (for WAN 2.2)
                use_baked: Whether to use baked VAE/CLIP from checkpoint
                current_clip_type: Current CLIP type
                is_base: Whether this is the base model (affects auto-detection)
                var_clip_type: Explicit clip_type for variations (to detect WAN 2.2 variations)
            """
            entry = {
                "name": name_high, 
                "model_path": None,       # Path for lazy loading
                "model_low_path": None,   # Path for lazy loading (WAN 2.2)
                "model_type": None,       # "checkpoint" or "diffusion"
                "use_baked_vae_clip": use_baked,
                "baked_vae": None,        # Only populated if checkpoint with use_baked=True
                "baked_clip": None,       # Only populated if checkpoint with use_baked=True
            }
            
            type_high, path_high = self._parse_model_selector(name_high)
            entry["model_type"] = type_high
            
            if type_high == "checkpoint":
                entry["model_path"] = folder_paths.get_full_path("checkpoints", path_high)
            elif type_high == "diffusion":
                entry["model_path"] = folder_paths.get_full_path("diffusion_models", path_high)
                
                # Store Low Noise Model path if WAN 2.2
                # Check: preset is WAN2.2 OR variation's clip_type is wan22
                is_wan22 = preset == "WAN2.2" or var_clip_type == "wan22"
                if is_wan22 and name_low != "NONE":
                    type_low, path_low = self._parse_model_selector(name_low)
                    if type_low == "diffusion":
                        entry["model_low_path"] = folder_paths.get_full_path("diffusion_models", path_low)
                        print(f"[ModelCompareLoaders] Stored WAN 2.2 low noise model path: {path_low}")
            
            return entry

        # Base Model
        base_entry = load_model_entry(diffusion_model, diffusion_model_low, baked_vae_clip, current_clip_type, is_base=True)
        # Apply custom label if provided
        base_label = kwargs.get("diffusion_model_label", "")
        if base_label:
            base_entry["display_name"] = base_label
        else:
            base_entry["display_name"] = base_entry["name"]
        model_variations.append(base_entry)
        
        # Variation Models
        for i in range(1, num_diffusion_models):
            var_name = kwargs.get(f"diffusion_model_variation_{i}", "NONE")
            var_low_name = kwargs.get(f"diffusion_model_variation_{i}_low", "NONE")
            var_baked = kwargs.get(f"baked_vae_clip_variation_{i}", False)
            var_label = kwargs.get(f"diffusion_model_variation_{i}_label", "")
            # Get variation's clip_type to detect WAN 2.2 variations
            var_clip_type = kwargs.get(f"clip_type_variation_{i}", "default")
            
            if var_name != "NONE":
                var_entry = load_model_entry(var_name, var_low_name, var_baked, current_clip_type, var_clip_type=var_clip_type)
                # Apply custom label if provided
                if var_label:
                    var_entry["display_name"] = var_label
                else:
                    var_entry["display_name"] = var_entry["name"]
                model_variations.append(var_entry)

        # 3. Store VAE paths (LAZY LOADING - no VAEs loaded here)
        vae_paths = {}  # Map name to path for lazy loading
        
        def get_vae_path(name):
            """Get path for VAE - does NOT load it."""
            if name in vae_paths: 
                return vae_paths[name]
            if name == "NONE": 
                return None
            path = folder_paths.get_full_path("vae", name)
            vae_paths[name] = path
            return path

        # Store base VAE path
        base_vae_name = vae if vae != "NONE" else None
        if base_entry.get("use_baked_vae_clip") and base_entry["model_type"] == "checkpoint":
            base_vae_name = "__baked__"  # Special marker for baked VAE
        elif vae != "NONE":
            get_vae_path(vae)  # Store path in map
            
        vae_variations = [{"name": vae if vae != "NONE" else "__baked__" if base_entry.get("use_baked_vae_clip") else "NONE"}]
        for i in range(1, num_vae_variations):
            v_name = kwargs.get(f"vae_variation_{i}", "NONE")
            if v_name != "NONE":
                get_vae_path(v_name)  # Store path in map
                vae_variations.append({"name": v_name})

        # 4. Store CLIP configurations (LAZY LOADING - no CLIPs loaded here)
        # Determine if BASE preset needs dual CLIP based on its OWN clip_type
        dual_clip_presets = ["HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "FLUX"]
        base_needs_dual_clip = preset in dual_clip_presets
        
        # Get base CLIP device setting
        clip_device = kwargs.get("clip_device", "default")
        
        clip_variations = []
        
        # Resolve base clip_type for storage
        base_resolved_clip_type = current_clip_type
        if base_resolved_clip_type == "default":
            # Map preset to clip_type
            preset_to_clip_type = {
                "SDXL": "sdxl", "PONY": "sdxl",
                "FLUX": "flux", "FLUX2": "flux2",
                "QWEN": "qwen",
                "WAN2.1": "wan", "WAN2.2": "wan22",
                "HUNYUAN_VIDEO": "hunyuan_video",
                "HUNYUAN_VIDEO_15": "hunyuan_video_15",
            }
            base_resolved_clip_type = preset_to_clip_type.get(preset, "sd")
        
        # Add base CLIP config - paths only, no loading
        if base_entry.get("use_baked_vae_clip") and base_entry["model_type"] == "checkpoint":
            # Baked CLIP from checkpoint
            clip_variations.append({
                "type": "baked",
                "clip_type": base_resolved_clip_type,
                "device": clip_device,
            })
        elif base_needs_dual_clip:
            # FLUX style - dual CLIP pair
            clip_variations.append({
                "type": "pair",
                "a": clip_model,
                "b": clip_model_2,
                "a_path": folder_paths.get_full_path("clip", clip_model) if clip_model != "NONE" else None,
                "b_path": folder_paths.get_full_path("clip", clip_model_2) if clip_model_2 != "NONE" else None,
                "clip_type": base_resolved_clip_type,
                "device": clip_device,
            })
        else:
            # FLUX2, QWEN, etc - single CLIP
            clip_variations.append({
                "type": "single",
                "model": clip_model,
                "model_path": folder_paths.get_full_path("clip", clip_model) if clip_model != "NONE" else None,
                "clip_type": base_resolved_clip_type,
                "device": clip_device,
            })

        for i in range(1, num_clip_variations):
            c_name = kwargs.get(f"clip_model_variation_{i}", "NONE")
            c_name_2 = kwargs.get(f"clip_model_variation_{i}_2", "NONE")
            c_type = kwargs.get(f"clip_type_variation_{i}", "default")
            c_device = kwargs.get(f"clip_device_variation_{i}", "default")
            
            if c_name != "NONE":
                # Store variation CLIP path - no loading
                path = folder_paths.get_full_path("clip", c_name)
                
                # Determine if THIS VARIATION needs dual CLIP based on its OWN clip_type, not the base preset
                # Resolve clip_type: if "default", infer from its associated model's preset
                resolved_clip_type = c_type
                if resolved_clip_type == "default":
                    # If there's a model variation at this index, use its preset to infer clip_type
                    model_var_preset = kwargs.get(f"model_preset_variation_{i}", preset)
                    
                    if model_var_preset == "SDXL" or model_var_preset == "PONY":
                        resolved_clip_type = "sdxl"
                    elif model_var_preset == "FLUX":
                        resolved_clip_type = "flux"
                    elif model_var_preset == "FLUX2":
                        resolved_clip_type = "flux2"
                    elif model_var_preset == "QWEN":
                        resolved_clip_type = "qwen"
                    elif model_var_preset == "WAN2.1" or model_var_preset == "WAN2.2":
                        resolved_clip_type = "wan"
                    elif model_var_preset == "HUNYUAN_VIDEO":
                        resolved_clip_type = "hunyuan_video"
                    elif model_var_preset == "HUNYUAN_VIDEO_15":
                        resolved_clip_type = "hunyuan_video_15"
                    else:
                        resolved_clip_type = "sd"
                else:
                    # User explicitly chose a clip_type
                    resolved_clip_type = c_type
                
                # Check if VARIATION's clip_type requires dual CLIP
                # Dual CLIP: FLUX, Hunyuan Video, Hunyuan 1.5 (NOT WAN 2.1, NOT WAN 2.2)
                variation_needs_dual_clip = resolved_clip_type in ["flux", "hunyuan_video", "hunyuan_video_15"]
                
                # Store paths only - no loading
                if variation_needs_dual_clip and c_name_2 != "NONE":
                    path2 = folder_paths.get_full_path("clip", c_name_2)
                    clip_variations.append({
                        "type": "pair",
                        "a": c_name,
                        "b": c_name_2,
                        "a_path": path,
                        "b_path": path2,
                        "clip_type": resolved_clip_type,
                        "device": c_device,
                    })
                else:
                    clip_variations.append({
                        "type": "single",
                        "model": c_name,
                        "model_path": path,
                        "clip_type": resolved_clip_type,
                        "device": c_device,
                    })

        # 5. Store LoRA configs per model variation
        # Base model LoRA config
        lora_configs = []
        base_lora_config = kwargs.get("lora_config", None)
        lora_configs.append(base_lora_config)
        
        # Variation LoRA configs
        for i in range(1, 5):
            var_lora_config = kwargs.get(f"lora_config_variation_{i}", None)
            lora_configs.append(var_lora_config)
        
        # Count how many LoRA configs are provided
        num_lora_configs = sum(1 for c in lora_configs if c is not None)
        if num_lora_configs > 0:
            print(f"[ModelCompareLoaders] {num_lora_configs} LoRA configuration(s) connected")

        # 6. Integrate Prompt Config if provided
        prompt_variations = []
        if prompt_config and isinstance(prompt_config, dict):
            prompt_variations = prompt_config.get("prompt_variations", [])
            print(f"[ModelCompareLoaders] Integrated {len(prompt_variations)} prompt variation(s)")

        # 7. Compute Combinations
        combinations = self._compute_combinations(
            model_variations, vae_variations, clip_variations, lora_configs, preset, prompt_variations
        )

        # Determine if this is a "grouped" comparison (Model+VAE+CLIP are paired, not cross-product)
        # Grouped mode: Model 1 with VAE 1 with CLIP 1, Model 2 with VAE 2 with CLIP 2, etc.
        # This is the default behavior when num_models > 1 and num_vaes/num_clips match
        num_models = len(model_variations)
        num_vaes = len(vae_variations)
        num_clips = len(clip_variations)
        is_grouped = num_models > 1 and (num_vaes > 1 or num_clips > 1)
        
        config = {
            "preset": preset,
            "combinations": combinations,
            "model_variations": model_variations,  # Contains paths, not objects
            "vae_paths": vae_paths,  # Map name to path for lazy loading
            "vae_variations": vae_variations,
            "clip_variations": clip_variations,  # Contains paths and config, not objects
            "lora_configs": lora_configs,  # Per-variation LoRA configs from LoRA Compare nodes
            "prompt_variations": prompt_variations,  # Prompt variations
            "global_config": global_config,  # Global sampling parameters from ModelCompareGlobals
            "is_grouped": is_grouped,  # Flag for grid to use simple grouped layout
            "num_model_groups": num_models,  # Number of model groups (for grid layout)
        }
        
        if global_config:
            print(f"[ModelCompareLoaders] Global config connected with {sum(1 for v in global_config.values() if v is not None)} parameter(s)")

        # LAZY LOADING: All model/VAE/CLIP loading deferred to sampler
        # Config only contains paths and configurations
        print(f"[ModelCompareLoaders] Config prepared with {len(combinations)} combinations (LAZY LOADING)")
        return (config,)

    def _get_clip_type_enum(self, clip_type_str):
        """
        Dynamically resolve CLIPType enum from string.
        Handles standard types and attempts to find new types dynamically.
        """
        import comfy.sd
        mapping = {
            "sd": comfy.sd.CLIPType.STABLE_DIFFUSION,
            "sdxl": getattr(comfy.sd.CLIPType, "STABLE_DIFFUSION", comfy.sd.CLIPType.STABLE_DIFFUSION),  # Fallback for older versions
            "sd3": getattr(comfy.sd.CLIPType, "SD3", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux": getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux2": getattr(comfy.sd.CLIPType, "FLUX2", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "wan": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "wan22": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),  # Same CLIP as wan
            "hunyuan_video": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "hunyuan_video_15": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO_15", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "qwen": getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "lumina2": getattr(comfy.sd.CLIPType, "LUMINA2", comfy.sd.CLIPType.STABLE_DIFFUSION),
        }
        
        # Try direct attribute lookup first for any other types
        key = clip_type_str.upper().replace("_", "")
        if hasattr(comfy.sd.CLIPType, key):
            return getattr(comfy.sd.CLIPType, key)
            
        return mapping.get(clip_type_str, comfy.sd.CLIPType.STABLE_DIFFUSION)

    def _compute_combinations(self, models, vaes, clips, lora_configs, preset, prompt_variations=None):
        """
        Compute combinations with GROUPING support and PROMPT variations.
        
        NEW GROUPING SYSTEM:
        - Model variation 0 (base) paired with VAE variation 0 + CLIP variation 0
        - Model variation 1 paired with VAE variation 1 + CLIP variation 1
        - etc.
        
        NEW LORA SYSTEM:
        - lora_configs is a list of per-variation LoRA configurations
        - Each model variation has its own LoRA config (or None)
        - LoRA configs contain list of LoRAs with strength variations
        
        NEW PROMPT SYSTEM:
        - Each model/vae/clip combo is tested with each prompt variation
        - If no prompt variations, defaults to single empty prompt
        
        This prevents cross-contamination (e.g., FLUX1 VAE on FLUX2 model).
        Unset variations (index >= available) reuse the last valid one.
        """
        import itertools
        
        if prompt_variations is None:
            prompt_variations = [{"index": 1, "positive": "", "negative": ""}]
        
        combos = []
        
        # Number of model variations
        num_models = len(models)
        num_vaes = len(vaes)
        num_clips = len(clips)
        
        def get_lora_combos_for_config(lora_config):
            """Generate all LoRA strength combinations from a LoRA config."""
            if lora_config is None:
                return [{"loras": [], "display": "No LoRA"}]
            
            loras = lora_config.get("loras", [])
            if not loras:
                return [{"loras": [], "display": "No LoRA"}]
            
            # Build options for each LoRA
            lora_options = []
            for lora in loras:
                opts = []
                strengths = lora.get("strengths", [1.0])
                low_strengths = lora.get("low_strengths", strengths)  # Default to same as high
                
                # Match lengths
                if len(low_strengths) < len(strengths):
                    low_strengths = low_strengths + [low_strengths[-1] if low_strengths else 1.0] * (len(strengths) - len(low_strengths))
                
                for s_h, s_l in zip(strengths, low_strengths):
                    opts.append({
                        "name": lora["name"],
                        "path": lora["path"],
                        "strength": s_h,
                        "label": lora.get("label", lora["name"]),
                        "mode": lora.get("mode", "SINGLE"),
                        "low_name": lora.get("low_name"),
                        "low_path": lora.get("low_path"),
                        "low_strength": s_l,
                        "low_label": lora.get("low_label", lora.get("low_name", "")),
                        "combinator": lora.get("combinator", "+"),
                    })
                lora_options.append(opts)
            
            # Generate all strength combinations
            lora_combos = []
            for prod in itertools.product(*lora_options):
                combo_loras = list(prod)
                # Build display name from labels and combinators
                display_parts = []
                for i, l in enumerate(combo_loras):
                    display_parts.append(f"{l['label']}:{l['strength']}")
                    if l.get("mode") == "HIGH_LOW_PAIR" and l.get("low_name"):
                        display_parts[-1] += f"/{l['low_label']}:{l['low_strength']}"
                    if i < len(combo_loras) - 1:
                        display_parts.append(l.get("combinator", "+"))
                
                lora_combos.append({
                    "loras": combo_loras,
                    "display": " ".join(display_parts) if display_parts else "No LoRA"
                })
            
            return lora_combos if lora_combos else [{"loras": [], "display": "No LoRA"}]

        # Generate final combinations with GROUPING
        # Each model index is paired with corresponding VAE and CLIP indices
        for m_idx in range(num_models):
            # Get VAE index: map model index to VAE index (reuse last if needed)
            v_idx = min(m_idx, num_vaes - 1) if num_vaes > 0 else 0
            
            # Get CLIP index: map model index to CLIP index (reuse last if needed)
            c_idx = min(m_idx, num_clips - 1) if num_clips > 0 else 0
            
            # Get VAE and CLIP for this group
            v_name = vaes[v_idx]["name"] if num_vaes > 0 else "NONE"
            c_clip = clips[c_idx] if num_clips > 0 else None
            
            # Get LoRA config for this model variation (or reuse last valid one)
            lora_config = None
            for i in range(m_idx, -1, -1):
                if i < len(lora_configs) and lora_configs[i] is not None:
                    lora_config = lora_configs[i]
                    break
            
            # Generate LoRA combinations for this variation
            lora_combos = get_lora_combos_for_config(lora_config)
            
            # For each LoRA combination, create one combo per model group
            for lora_combo in lora_combos:
                # For each prompt variation
                for prompt_var in prompt_variations:
                    combos.append({
                        "model_index": m_idx,
                        "vae_name": v_name,
                        "clip_variation": c_clip,
                        "lora_config": lora_combo,  # Contains list of LoRAs with strengths
                        "prompt_index": prompt_var.get("index", 1),
                        "prompt_positive": prompt_var.get("positive", ""),
                        "prompt_negative": prompt_var.get("negative", ""),
                    })
                        
        return combos

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """
        Compute a hash of all inputs to determine if re-execution is needed.
        This prevents unnecessary re-runs when workflow is queued without changes.
        """
        # Build a string representation of all inputs
        items_to_hash = []
        
        # Add all kwargs to the hash
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            # Skip config objects (they're outputs)
            if key == "prompt_config" and val is not None:
                # For prompt_config, hash its contents
                items_to_hash.append(f"{key}:{str(val)}")
            elif isinstance(val, (str, int, float, bool)):
                items_to_hash.append(f"{key}:{val}")
            elif isinstance(val, (list, tuple)):
                items_to_hash.append(f"{key}:{str(val)}")
            elif val is None:
                items_to_hash.append(f"{key}:None")
        
        # Create hash of all items
        hash_input = "|".join(items_to_hash)
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "ModelCompareLoaders": ModelCompareLoaders,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareLoaders": "Model Compare Loaders",
}