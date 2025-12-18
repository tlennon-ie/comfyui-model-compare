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
        """Define input widgets for the node with preset system.
        
        SIMPLIFIED: VAE, CLIP, and LoRA configs are now handled by separate config nodes
        that connect to the SamplingConfigChain. This loader only handles base models.
        """
        combined_models = cls._get_combined_model_list()

        inputs = {
            "required": {
                "preset": (["STANDARD", "SDXL", "PONY", "WAN2.1", "WAN2.2", "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "QWEN", "QWEN_EDIT", "FLUX", "FLUX2", "FLUX_KONTEXT", "Z_IMAGE", "PIFLOW"], {
                    "default": "STANDARD",
                    "tooltip": "Model preset - determines available configuration options and sampling behavior. PIFLOW requires ComfyUI-piFlow custom node."
                }),
                "model_pairing_mode": (["SINGLE", "AUTO_PAIR"], {
                    "default": "SINGLE",
                    "tooltip": "SINGLE: Manual model selection. AUTO_PAIR: Automatically pairs HIGH/LOW models (e.g., 'Wan 2.2 HIGH' + 'Wan 2.2 LOW')"
                }),
                "diffusion_model": (
                    ["NONE"] + combined_models,
                    {"default": combined_models[0] if combined_models else "NONE",
                     "tooltip": "Primary diffusion model (or High Noise model for WAN 2.2)"},
                ),
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
                     "tooltip": "Low Noise model (only for WAN 2.2 preset, ignored in AUTO_PAIR mode)"},
                ),
                "num_diffusion_models": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of diffusion model variations to compare",
                }),
            },
            "optional": {
                "prompt_config": ("PROMPT_COMPARE_CONFIG", {
                    "tooltip": "Optional: Connect PromptCompare node to compare multiple prompts"
                }),
            },
        }

        # Add model variation fields (1-9)
        for i in range(1, 10):
            inputs["optional"][f"diffusion_model_variation_{i}"] = (
                ["NONE"] + combined_models,
                {"default": "NONE",
                 "tooltip": f"Model Variation {i}: Primary diffusion model"},
            )
            inputs["optional"][f"diffusion_model_variation_{i}_label"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"Model Variation {i}: Custom display label (leave empty to use filename)"
                },
            )
            inputs["optional"][f"diffusion_model_variation_{i}_low"] = (
                ["NONE"] + combined_models,
                {"default": "NONE",
                 "tooltip": f"Model Variation {i}: Low Noise model (WAN 2.2, ignored in AUTO_PAIR mode)"},
            )

        return inputs

    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "load_models"
    CATEGORY = "Model Compare/Loaders"

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
    
    def _find_paired_model(self, model_name, model_type, find_low=True):
        """Find the paired HIGH or LOW model variant.
        
        Args:
            model_name: The model filename (without prefix)
            model_type: "checkpoint" or "diffusion"
            find_low: If True, find LOW variant; if False, find HIGH variant
        
        Returns:
            Paired model name with prefix, or None if not found
        """
        if not model_name or model_name == "NONE":
            return None
        
        # Common pairing patterns
        patterns = [
            ("HIGH", "LOW"),
            ("High", "Low"),
            ("high", "low"),
            ("_HIGH", "_LOW"),
            ("_High", "_Low"),
            ("_high", "_low"),
            ("-HIGH", "-LOW"),
            ("-High", "-Low"),
            ("-high", "-low"),
        ]
        
        search_term = "LOW" if find_low else "HIGH"
        replace_term = "HIGH" if find_low else "LOW"
        
        # Try to find the paired model
        for high_pattern, low_pattern in patterns:
            if find_low and high_pattern in model_name:
                # Looking for LOW variant, model has HIGH in name
                paired_name = model_name.replace(high_pattern, low_pattern)
                
                # Check if paired model exists
                prefix = "[Checkpoint] " if model_type == "checkpoint" else "[Diffusion] "
                
                if model_type == "checkpoint":
                    available = self._get_cached_models("checkpoints")
                else:
                    available = self._get_cached_models("diffusion_models")
                
                if paired_name in available:
                    return f"{prefix}{paired_name}"
            
            elif not find_low and low_pattern in model_name:
                # Looking for HIGH variant, model has LOW in name
                paired_name = model_name.replace(low_pattern, high_pattern)
                
                # Check if paired model exists
                prefix = "[Checkpoint] " if model_type == "checkpoint" else "[Diffusion] "
                
                if model_type == "checkpoint":
                    available = self._get_cached_models("checkpoints")
                else:
                    available = self._get_cached_models("diffusion_models")
                
                if paired_name in available:
                    return f"{prefix}{paired_name}"
        
        return None

    def load_models(self, preset, model_pairing_mode, diffusion_model, diffusion_model_low,
                    num_diffusion_models,
                    prompt_config=None,
                    **kwargs):
        """
        Load model configurations for comparison.
        
        SIMPLIFIED: This now only handles diffusion models.
        VAE, CLIP, and LoRA configs are handled by separate config nodes
        that connect to the SamplingConfigChain.
        
        Args:
            preset: Model preset (STANDARD, WAN2.2, etc.)
            model_pairing_mode: SINGLE or AUTO_PAIR
            diffusion_model: Primary model selection
            diffusion_model_low: Low noise model (for SINGLE mode or WAN2.2)
            num_diffusion_models: Number of model variations
            prompt_config: Optional prompt configuration
            **kwargs: Additional model variation parameters
        """
        
        model_variations = []
        
        def load_model_entry(name_high, name_low, label="", auto_pair=False):
            """Create model entry storing paths for lazy loading.
            
            Args:
                name_high: Primary model name (or HIGH model in paired mode)
                name_low: Low model name (or NONE for auto-pairing)
                label: Custom display label
                auto_pair: If True, attempt to find paired LOW model automatically
            """
            entry = {
                "name": name_high,
                "model_path": None,
                "model_low_path": None,
                "model_type": None,
                "pairing_mode": model_pairing_mode,
            }
            
            type_high, path_high = self._parse_model_selector(name_high)
            entry["model_type"] = type_high
            
            if type_high == "checkpoint":
                entry["model_path"] = folder_paths.get_full_path("checkpoints", path_high)
            elif type_high == "diffusion":
                entry["model_path"] = folder_paths.get_full_path("diffusion_models", path_high)
                
                # Handle paired model loading for WAN 2.2
                if preset == "WAN2.2":
                    if auto_pair and model_pairing_mode == "AUTO_PAIR":
                        # Attempt to find paired LOW model automatically
                        paired_model = self._find_paired_model(path_high, "diffusion", find_low=True)
                        
                        if paired_model:
                            type_low, path_low = self._parse_model_selector(paired_model)
                            if type_low == "diffusion":
                                entry["model_low_path"] = folder_paths.get_full_path("diffusion_models", path_low)
                                entry["paired_model_name"] = paired_model
                                print(f"[ModelCompareLoaders] AUTO_PAIR: Paired '{path_high}' with '{path_low}'")
                        else:
                            print(f"[ModelCompareLoaders] AUTO_PAIR: No LOW variant found for '{path_high}'")
                    
                    elif name_low != "NONE":
                        # Manual pairing (SINGLE mode with explicit LOW model)
                        type_low, path_low = self._parse_model_selector(name_low)
                        if type_low == "diffusion":
                            entry["model_low_path"] = folder_paths.get_full_path("diffusion_models", path_low)
            
            # Set display name
            entry["display_name"] = label if label else name_high
            
            return entry

        # Base Model
        base_label = kwargs.get("diffusion_model_label", "")
        base_entry = load_model_entry(
            diffusion_model, 
            diffusion_model_low, 
            base_label,
            auto_pair=True
        )
        model_variations.append(base_entry)
        
        # Variation Models
        for i in range(1, num_diffusion_models):
            var_name = kwargs.get(f"diffusion_model_variation_{i}", "NONE")
            var_low_name = kwargs.get(f"diffusion_model_variation_{i}_low", "NONE")
            var_label = kwargs.get(f"diffusion_model_variation_{i}_label", "")
            
            if var_name != "NONE":
                var_entry = load_model_entry(
                    var_name, 
                    var_low_name, 
                    var_label,
                    auto_pair=True
                )
                model_variations.append(var_entry)

        # Integrate Prompt Config if provided
        prompt_variations = []
        if prompt_config and isinstance(prompt_config, dict):
            prompt_variations = prompt_config.get("prompt_variations", [])

        # Compute basic combinations (just models + prompts)
        # VAE/CLIP/LoRA combinations are expanded later via chain configs
        combinations = self._compute_combinations(
            model_variations, prompt_variations
        )
        
        config = {
            "preset": preset,
            "combinations": combinations,
            "model_variations": model_variations,
            "prompt_variations": prompt_variations,
            "num_model_groups": len(model_variations),
        }

        return (config,)

    def _compute_combinations(self, models, prompt_variations=None):
        """
        Compute combinations for models and prompts only.
        
        SIMPLIFIED: VAE, CLIP, and LoRA combinations are now handled by 
        SamplingConfigChain when chain configs are provided.
        """
        if prompt_variations is None or len(prompt_variations) == 0:
            prompt_variations = [{"index": 1, "positive": "", "negative": ""}]
        
        combos = []
        
        for m_idx in range(len(models)):
            for prompt_var in prompt_variations:
                combos.append({
                    "model_index": m_idx,
                    "prompt_index": prompt_var.get("index", 1),
                    "prompt_positive": prompt_var.get("positive", ""),
                    "prompt_negative": prompt_var.get("negative", ""),
                })
                        
        return combos

    @classmethod
    def IS_CHANGED(cls, preset, model_pairing_mode, **kwargs):
        """
        Compute a hash of all inputs to determine if re-execution is needed.
        This prevents unnecessary re-runs when workflow is queued without changes.
        """
        # Build a string representation of all inputs
        items_to_hash = [f"preset:{preset}", f"model_pairing_mode:{model_pairing_mode}"]
        
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
    "ModelCompareLoaders": "Ⓜ️ Model Compare - Loaders",
}