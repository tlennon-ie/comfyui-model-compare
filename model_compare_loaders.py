"""
Model Compare Loaders Node
"""

import folder_paths
import comfy.sd
import comfy.utils
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
                "preset": (["STANDARD", "SDXL", "PONY", "WAN2.1", "WAN2.2", "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "QWEN", "FLUX", "FLUX2"], {
                    "default": "STANDARD",
                    "tooltip": "Model preset - determines available configuration options and sampling behavior. FLUX = dual CLIPs, FLUX2 = single CLIP"
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
                    ["default", "sd", "sdxl", "sd3", "flux", "flux2", "wan", "wan22", "hunyuan_video", "hunyuan_video_15", "qwen"],
                    {"default": "default",
                     "tooltip": "CLIP model type (auto-adjusted based on preset). Use wan22 for High/Low noise model pairing."},
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
                "num_loras": ("INT", {
                    "default": 1,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of LoRA combinations to test",
                }),
            },
            "optional": {
                "prompt_config": ("PROMPT_COMPARE_CONFIG", {
                    "tooltip": "Optional: Connect PromptCompare node to compare multiple prompts"
                }),
                # Video model FPS settings (shown for video presets)
                "fps": ("INT", {
                    "default": 24,
                    "min": 1,
                    "max": 120,
                    "step": 1,
                    "tooltip": "FPS for base video model output. Common: WAN=16, Hunyuan=24, HY1.5=24"
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
                ["default", "sd", "sdxl", "sd3", "flux", "flux2", "wan", "wan22", "hunyuan_video", "hunyuan_video_15", "qwen"],
                {"default": "default", "tooltip": f"Variation {i}: CLIP Type (wan22 enables High/Low noise model pairing)"}
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
            
            # FPS for video model variations
            inputs["optional"][f"fps_variation_{i}"] = ("INT", {
                "default": 24,
                "min": 1,
                "max": 120,
                "step": 1,
                "tooltip": f"Variation {i}: FPS for video output. Common: WAN=16, Hunyuan=24, HY1.5=24"
            })
        
        # LoRA fields (separate section after variations)
        for i in range(10):
            inputs["optional"][f"lora_{i}"] = (
                ["NONE"] + loras,
                {"default": "NONE",
                 "tooltip": "LoRA model (High Noise for WAN 2.2)"},
            )
            inputs["optional"][f"lora_{i}_strengths"] = (
                "STRING",
                {
                    "default": "1.0",
                    "multiline": False,
                    "tooltip": "Comma-separated strength values",
                },
            )
            inputs["optional"][f"lora_{i}_customlabel"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Custom label",
                },
            )
            
            inputs["optional"][f"lora_{i}_low"] = (
                ["NONE"] + loras,
                {"default": "NONE",
                 "tooltip": "Low Noise LoRA (WAN 2.2 only)",
                },
            )
            inputs["optional"][f"lora_{i}_low_strengths"] = (
                "STRING",
                {
                    "default": "1.0",
                    "multiline": False,
                    "tooltip": "Strength for Low Noise LoRA",
                },
            )
            inputs["optional"][f"lora_{i}_low_customlabel"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Custom label for Low Noise LoRA",
                },
            )
            
            if i < 9:
                inputs["optional"][f"lora_combiner_{i}"] = (
                    ["+", " "],
                    {"default": "+", "tooltip": "Combine with next LoRA (+ for AND, space for OR)"}
                )

        return inputs

    RETURN_TYPES = ("MODEL_COMPARE_CONFIG", "MODEL", "VAE", "CONDITIONING", "CONDITIONING")
    RETURN_NAMES = ("config", "base_model", "base_vae", "positive_cond", "negative_cond")
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
               num_diffusion_models, num_vae_variations, num_clip_variations, num_loras,
               prompt_config=None,
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
            """Load a model entry with optional low noise model for WAN 2.2.
            
            Args:
                name_high: High noise model name
                name_low: Low noise model name (for WAN 2.2)
                use_baked: Whether to use baked VAE/CLIP from checkpoint
                current_clip_type: Current CLIP type
                is_base: Whether this is the base model (affects auto-detection)
                var_clip_type: Explicit clip_type for variations (to detect WAN 2.2 variations)
            """
            entry = {"name": name_high, "model_obj": None, "model_low_obj": None, "baked_vae": None, "baked_clip": None}
            
            type_high, path_high = self._parse_model_selector(name_high)
            
            if type_high == "checkpoint":
                # Load Checkpoint
                ckpt_path = folder_paths.get_full_path("checkpoints", path_high)
                out = comfy.sd.load_checkpoint_guess_config(ckpt_path, output_vae=True, output_clip=True, embedding_directory=folder_paths.get_folder_paths("embeddings"))
                entry["model_obj"] = out[0]
                entry["baked_clip"] = out[1]
                entry["baked_vae"] = out[2]
                
                # Auto-detect CLIP type from model
                if is_base:
                    detected = detect_model_clip_type(entry["model_obj"], current_clip_type)
                    if detected != current_clip_type:
                        print(f"[ModelCompareLoaders] Auto-detected CLIP type: {detected} for model {name_high}")
                        current_clip_type = detected
                
                if not use_baked:
                    entry["baked_vae"] = None
                    entry["baked_clip"] = None
                    
            elif type_high == "diffusion":
                # Load Diffusion Model with proper model options
                diff_path = folder_paths.get_full_path("diffusion_models", path_high)
                # Use empty dict - ComfyUI will auto-detect and apply optimal settings
                model_options = {}
                entry["model_obj"] = comfy.sd.load_diffusion_model(diff_path, model_options=model_options)
                
                # Auto-detect CLIP type from model
                if is_base:
                    detected = detect_model_clip_type(entry["model_obj"], current_clip_type)
                    if detected != current_clip_type:
                        print(f"[ModelCompareLoaders] Auto-detected CLIP type: {detected} for model {name_high}")
                        current_clip_type = detected
                
                # Load Low Noise Model if WAN 2.2
                # Check: preset is WAN2.2 OR variation's clip_type is wan22
                is_wan22 = preset == "WAN2.2" or var_clip_type == "wan22"
                if is_wan22 and name_low != "NONE":
                    type_low, path_low = self._parse_model_selector(name_low)
                    if type_low == "diffusion":
                        diff_low_path = folder_paths.get_full_path("diffusion_models", path_low)
                        entry["model_low_obj"] = comfy.sd.load_diffusion_model(diff_low_path, model_options={})
                        print(f"[ModelCompareLoaders] Loaded WAN 2.2 low noise model: {path_low}")
            
            return entry

        # Base Model
        base_entry = load_model_entry(diffusion_model, diffusion_model_low, baked_vae_clip, current_clip_type, is_base=True)
        # Apply custom label if provided
        base_label = kwargs.get("diffusion_model_label", "")
        if base_label:
            base_entry["display_name"] = base_label
        else:
            base_entry["display_name"] = base_entry["name"]
        # Store FPS for video models
        base_entry["fps"] = kwargs.get("fps", 24)
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
                # Store FPS for video models
                var_entry["fps"] = kwargs.get(f"fps_variation_{i}", 24)
                model_variations.append(var_entry)

        # 3. Load VAEs
        vae_map = {} # Map name to VAE object
        
        def get_vae_obj(name):
            if name in vae_map: return vae_map[name]
            if name == "NONE": return None
            path = folder_paths.get_full_path("vae", name)
            v = comfy.sd.VAE(sd=comfy.utils.load_torch_file(path))
            vae_map[name] = v
            return v

        base_vae_obj = None
        if base_entry["baked_vae"]:
            base_vae_obj = base_entry["baked_vae"]
        elif vae != "NONE":
            base_vae_obj = get_vae_obj(vae)
            
        vae_variations = [{"name": vae}]
        for i in range(1, num_vae_variations):
            v_name = kwargs.get(f"vae_variation_{i}", "NONE")
            if v_name != "NONE":
                get_vae_obj(v_name) # Ensure loaded
                vae_variations.append({"name": v_name})

        # 4. Load CLIPs
        base_clip_obj = None
        # Determine if BASE preset needs dual CLIP based on its OWN clip_type
        dual_clip_presets = ["HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "FLUX"]
        base_needs_dual_clip = preset in dual_clip_presets
        
        # Get base CLIP device setting
        clip_device = kwargs.get("clip_device", "default")
        base_clip_model_options = {}
        if clip_device == "cpu":
            base_clip_model_options["load_device"] = torch.device("cpu")
            base_clip_model_options["offload_device"] = torch.device("cpu")
            print(f"[ModelCompareLoaders] Loading base CLIP on CPU to save VRAM")
        
        if base_entry["baked_clip"]:
            base_clip_obj = base_entry["baked_clip"]
        elif clip_model != "NONE":
            # Standard CLIP loading
            path = folder_paths.get_full_path("clip", clip_model)
            
            # Load base CLIP with correct configuration
            if base_needs_dual_clip and clip_model_2 != "NONE":
                 path2 = folder_paths.get_full_path("clip", clip_model_2)
                 base_clip_obj = comfy.sd.load_clip(ckpt_paths=[path, path2], embedding_directory=folder_paths.get_folder_paths("embeddings"), clip_type=self._get_clip_type_enum(current_clip_type), model_options=base_clip_model_options)
            else:
                 # Single CLIP for everything else (including FLUX2)
                 base_clip_obj = comfy.sd.load_clip(ckpt_paths=[path], embedding_directory=folder_paths.get_folder_paths("embeddings"), clip_type=self._get_clip_type_enum(current_clip_type), model_options=base_clip_model_options)
        
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
        
        # Add base CLIP config
        if base_needs_dual_clip:
            # FLUX style - dual CLIP pair
            clip_variations.append({
                "type": "pair",
                "a": clip_model,
                "b": clip_model_2,
                "clip_obj": base_clip_obj,
                "clip_type": base_resolved_clip_type,  # Store for sampler model type detection
            })
        else:
            # FLUX2, QWEN, etc - single CLIP
            clip_variations.append({
                "type": "single",
                "model": clip_model,
                "clip_obj": base_clip_obj,
                "clip_type": base_resolved_clip_type,  # Store for sampler model type detection
            })

        for i in range(1, num_clip_variations):
            c_name = kwargs.get(f"clip_model_variation_{i}", "NONE")
            c_name_2 = kwargs.get(f"clip_model_variation_{i}_2", "NONE")
            c_type = kwargs.get(f"clip_type_variation_{i}", "default")
            c_device = kwargs.get(f"clip_device_variation_{i}", "default")
            
            if c_name != "NONE":
                # Load variation CLIP
                path = folder_paths.get_full_path("clip", c_name)
                c_obj = None
                
                # Build model_options for device
                var_clip_model_options = {}
                if c_device == "cpu":
                    var_clip_model_options["load_device"] = torch.device("cpu")
                    var_clip_model_options["offload_device"] = torch.device("cpu")
                    print(f"[ModelCompareLoaders] Loading CLIP variation {i} on CPU to save VRAM")
                
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
                
                # Load dual CLIP only if THIS VARIATION's clip_type requires it AND secondary CLIP provided
                if variation_needs_dual_clip and c_name_2 != "NONE":
                    path2 = folder_paths.get_full_path("clip", c_name_2)
                    c_obj = comfy.sd.load_clip(ckpt_paths=[path, path2], embedding_directory=folder_paths.get_folder_paths("embeddings"), clip_type=self._get_clip_type_enum(c_type), model_options=var_clip_model_options)
                else:
                    # Single CLIP for all others (including FLUX2 variations)
                    c_obj = comfy.sd.load_clip(ckpt_paths=[path], embedding_directory=folder_paths.get_folder_paths("embeddings"), clip_type=self._get_clip_type_enum(c_type), model_options=var_clip_model_options)
                
                # Append with correct structure based on CLIP type
                if variation_needs_dual_clip and c_name_2 != "NONE":
                    clip_variations.append({
                        "type": "pair",
                        "a": c_name,
                        "b": c_name_2,
                        "clip_obj": c_obj,
                        "clip_type": resolved_clip_type,  # Store for sampler model type detection
                    })
                else:
                    clip_variations.append({
                        "type": "single",
                        "model": c_name,
                        "clip_obj": c_obj,
                        "clip_type": resolved_clip_type,  # Store for sampler model type detection
                    })

        # 5. Load LoRAs
        loras_list = []
        for i in range(num_loras):
            l_name = kwargs.get(f"lora_{i}", "NONE")
            if l_name != "NONE":
                l_strengths = kwargs.get(f"lora_{i}_strengths", "1.0")
                l_label = kwargs.get(f"lora_{i}_customlabel", "")
                
                l_data = {
                    "name": l_name,
                    "strengths": self._parse_strengths(l_strengths),
                    "display_name": l_label if l_label else l_name
                }
                
                # WAN 2.2 Low Noise LoRA
                if preset == "WAN2.2":
                    l_low = kwargs.get(f"lora_{i}_low", "NONE")
                    l_low_str = kwargs.get(f"lora_{i}_low_strengths", "1.0")
                    l_low_lbl = kwargs.get(f"lora_{i}_low_customlabel", "")
                    
                    l_data["name_low"] = l_low
                    l_data["strengths_low"] = self._parse_strengths(l_low_str)
                    l_data["display_name_low"] = l_low_lbl if l_low_lbl else l_low
                
                loras_list.append(l_data)

        # 6. Integrate Prompt Config if provided
        prompt_variations = []
        if prompt_config and isinstance(prompt_config, dict):
            prompt_variations = prompt_config.get("prompt_variations", [])
            print(f"[ModelCompareLoaders] Integrated {len(prompt_variations)} prompt variation(s)")

        # 7. Compute Combinations
        combinations = self._compute_combinations(
            model_variations, vae_variations, clip_variations, loras_list, preset, prompt_variations
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
            "model_variations": model_variations, # Contains objects
            "vae_map": vae_map,
            "vae_variations": vae_variations,
            "clip_variations": clip_variations,
            "loras": loras_list,
            "prompt_variations": prompt_variations,  # NEW: Prompt variations
            "is_grouped": is_grouped,  # Flag for grid to use simple grouped layout
            "num_model_groups": num_models,  # Number of model groups (for grid layout)
        }

        # Encode conditioning for the first prompt variation if available
        # Just pass through whatever encode() returns - it handles the format correctly
        positive_cond = [[torch.zeros((1, 77, 768)), {}]]  # Default empty
        negative_cond = [[torch.zeros((1, 77, 768)), {}]]
        
        if prompt_variations and len(prompt_variations) > 0 and base_clip_obj:
            first_prompt = prompt_variations[0]
            try:
                # Handle FLUX dual-CLIP tokenization specially
                if base_needs_dual_clip and clip_model_2 != "NONE":
                    # For FLUX with dual CLIP, tokenize the prompt for both CLIPs like the standard node
                    # Always encode, even if prompt is empty (to get proper empty conditioning with pooled_output)
                    pos_text = first_prompt.get("positive", "")
                    tokens = base_clip_obj.tokenize(pos_text)
                    positive_cond = base_clip_obj.encode_from_tokens_scheduled(tokens, add_dict={"guidance": 3.5})
                    
                    neg_text = first_prompt.get("negative", "")
                    tokens = base_clip_obj.tokenize(neg_text)
                    negative_cond = base_clip_obj.encode_from_tokens_scheduled(tokens, add_dict={"guidance": 3.5})
                else:
                    # Standard single-CLIP encoding for FLUX2, SDXL, etc.
                    # Always encode, even if prompt is empty
                    pos_text = first_prompt.get("positive", "")
                    tokens = base_clip_obj.tokenize(pos_text)
                    positive_cond = base_clip_obj.encode_from_tokens_scheduled(tokens)
                    
                    neg_text = first_prompt.get("negative", "")
                    tokens = base_clip_obj.tokenize(neg_text)
                    negative_cond = base_clip_obj.encode_from_tokens_scheduled(tokens)
                
                print(f"[ModelCompareLoaders] Encoded conditioning from prompt variations")
            except Exception as e:
                print(f"[ModelCompareLoaders] Warning: Failed to encode conditioning: {e}")
                import traceback
                traceback.print_exc()
                print(f"[ModelCompareLoaders] Using empty conditioning tensors")

        # Return base objects for standard connection if needed (fallback)
        return (config, base_entry["model_obj"], base_vae_obj, positive_cond, negative_cond)

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
        }
        
        # Try direct attribute lookup first for any other types
        key = clip_type_str.upper().replace("_", "")
        if hasattr(comfy.sd.CLIPType, key):
            return getattr(comfy.sd.CLIPType, key)
            
        return mapping.get(clip_type_str, comfy.sd.CLIPType.STABLE_DIFFUSION)

    def _parse_strengths(self, strength_str):
        try:
            return [float(x.strip()) for x in strength_str.split(",")]
        except:
            return [1.0]

    def _compute_combinations(self, models, vaes, clips, loras, preset, prompt_variations=None):
        """
        Compute combinations with GROUPING support and PROMPT variations.
        
        NEW GROUPING SYSTEM:
        - Model variation 0 (base) paired with VAE variation 0 + CLIP variation 0
        - Model variation 1 paired with VAE variation 1 + CLIP variation 1
        - etc.
        
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
        
        # 4. LoRA Combinations
        lora_options = []
        for i, lora in enumerate(loras):
            opts = []
            # High strengths
            strs = lora["strengths"]
            # Low strengths (WAN 2.2)
            strs_low = lora.get("strengths_low", [])
            
            # Match lengths
            if len(strs_low) < len(strs):
                strs_low = strs_low + [strs_low[-1]] * (len(strs) - len(strs_low)) if strs_low else [1.0]*len(strs)
            
            for s_h, s_l in zip(strs, strs_low):
                opts.append({
                    "name": lora["name"],
                    "strength": s_h,
                    "name_low": lora.get("name_low"),
                    "strength_low": s_l,
                    "display": lora["display_name"]
                })
            lora_options.append(opts)
            
        if not lora_options:
            lora_combos = [([], [], [], [])] # names, strengths, names_low, strengths_low
        else:
            lora_combos = []
            for prod in itertools.product(*lora_options):
                names = []
                strengths = []
                names_low = []
                strengths_low = []
                
                for item in prod:
                    if item["name"] != "NONE":
                        names.append(item["name"])
                        strengths.append(item["strength"])
                        if preset == "WAN2.2":
                            names_low.append(item["name_low"])
                            strengths_low.append(item["strength_low"])
                
                lora_combos.append((names, strengths, names_low, strengths_low))

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
            
            # For each LoRA combination, create one combo per model group
            for l_names, l_strs, l_names_low, l_strs_low in lora_combos:
                # For each prompt variation
                for prompt_var in prompt_variations:
                    combos.append({
                        "model_index": m_idx,
                        "vae_name": v_name,
                        "clip_variation": c_clip,
                        "lora_names": l_names,
                        "lora_strengths": l_strs,
                        "lora_names_low": l_names_low,
                        "lora_strengths_low": l_strs_low,
                        "prompt_index": prompt_var.get("index", 1),  # NEW
                        "prompt_positive": prompt_var.get("positive", ""),  # NEW
                        "prompt_negative": prompt_var.get("negative", ""),  # NEW
                    })
                        
        return combos

# Node class mappings
NODE_CLASS_MAPPINGS = {
    "ModelCompareLoaders": ModelCompareLoaders,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareLoaders": "Model Compare Loaders",
}