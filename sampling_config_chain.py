"""
Sampling Config Chain Node

Allows users to configure sampling parameters per-model-variation.
Each chain node matches a model variation from the loader and provides
model-specific sampling parameters.

All parameters are "convertible widgets" - they can be used as regular widgets
OR converted to inputs to receive values from other nodes/chains.

Flow:
ModelCompareLoaders -> ConfigChain1 -> ConfigChain2 -> ... -> SamplerCompareAdvanced
"""

import time
import comfy.samplers


class SamplingConfigChain:
    """
    Configure sampling parameters for a specific model variation.
    Chain multiple nodes together to configure each model in your comparison.
    
    All parameter widgets can be converted to inputs by right-clicking.
    This allows connecting values from one chain to another (e.g., share seed).
    
    The config_type determines which parameters are shown:
    - STANDARD/SDXL/PONY: Basic sampling (seed, steps, cfg, sampler, scheduler)
    - QWEN: AuraFlow sampling with shift and CFG normalization
    - WAN2.1: Video sampling with WAN shift
    - WAN2.2: Two-phase video sampling with high/low noise models
    - HUNYUAN_VIDEO/HUNYUAN_VIDEO_15: Hunyuan video with shift
    - FLUX/FLUX2: FLUX sampling with guidance
    """
    
    _version = int(time.time() % 10000)
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "variation_index": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "tooltip": "Which model variation this config applies to (1 = first model, 2 = second, etc.)"
                }),
                "config_type": ([
                    "STANDARD", "SDXL", "PONY", 
                    "QWEN", 
                    "WAN2.1", "WAN2.2", 
                    "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", 
                    "FLUX", "FLUX2",
                    "Z_IMAGE"
                ], {
                    "default": "STANDARD",
                    "tooltip": "Model type - determines which parameters are shown. Z_IMAGE uses Lumina2 with QWEN3-4B text encoder."
                }),
            },
            "optional": {
                # === Common Sampling Parameters (all types) - Connectable ===
                "seed": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 0xffffffffffffffff,
                    "tooltip": "Random seed for this variation (connectable)",
                    "forceInput": False,  # Widget by default, convertible to input
                }),
                "seed_control": (["fixed", "increment", "decrement", "randomize"], {
                    "default": "fixed",
                    "tooltip": "How to handle seed across batches (connectable)",
                }),
                "steps": ("INT", {
                    "default": 20, 
                    "min": 1, 
                    "max": 10000,
                    "tooltip": "Number of sampling steps (connectable)",
                }),
                "cfg": ("FLOAT", {
                    "default": 7.0, 
                    "min": 0.0, 
                    "max": 100.0, 
                    "step": 0.1,
                    "tooltip": "Classifier-free guidance scale (connectable)",
                }),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, {
                    "tooltip": "Sampling algorithm (connectable)",
                }),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, {
                    "tooltip": "Noise schedule (connectable)",
                }),
                "denoise": ("FLOAT", {
                    "default": 1.0, 
                    "min": 0.0, 
                    "max": 1.0, 
                    "step": 0.01,
                    "tooltip": "Denoising strength (connectable)",
                }),
                
                # === QWEN Parameters ===
                "qwen_shift": ("FLOAT", {
                    "default": 1.15, 
                    "min": 0.0, 
                    "max": 20.0, 
                    "step": 0.1,
                    "tooltip": "[QWEN] AuraFlow shift parameter - QWEN default is 1.15 (connectable)",
                }),
                "qwen_cfg_norm": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "[QWEN] Enable CFG normalization (connectable)",
                }),
                "qwen_cfg_norm_multiplier": ("FLOAT", {
                    "default": 0.7, 
                    "min": 0.0, 
                    "max": 1.0, 
                    "step": 0.01,
                    "tooltip": "[QWEN] CFG normalization multiplier (connectable)",
                }),
                
                # === WAN Parameters ===
                "wan_shift": ("FLOAT", {
                    "default": 8.0, 
                    "min": 0.0, 
                    "max": 20.0, 
                    "step": 0.1,
                    "tooltip": "[WAN 2.1] Shift parameter (connectable)",
                }),
                "wan22_shift": ("FLOAT", {
                    "default": 5.0, 
                    "min": 0.0, 
                    "max": 20.0, 
                    "step": 0.1,
                    "tooltip": "[WAN 2.2] Shift parameter (connectable)",
                }),
                "wan22_high_start": ("INT", {
                    "default": 0, 
                    "min": 0, 
                    "max": 10000,
                    "tooltip": "[WAN 2.2] High noise model start step (connectable)",
                }),
                "wan22_high_end": ("INT", {
                    "default": 10, 
                    "min": 0, 
                    "max": 10000,
                    "tooltip": "[WAN 2.2] High noise model end step (connectable)",
                }),
                "wan22_low_start": ("INT", {
                    "default": 10, 
                    "min": 0, 
                    "max": 10000,
                    "tooltip": "[WAN 2.2] Low noise model start step (connectable)",
                }),
                "wan22_low_end": ("INT", {
                    "default": 20, 
                    "min": 0, 
                    "max": 10000,
                    "tooltip": "[WAN 2.2] Low noise model end step (connectable)",
                }),
                
                # === Hunyuan Parameters ===
                "hunyuan_shift": ("FLOAT", {
                    "default": 7.0, 
                    "min": 0.0, 
                    "max": 20.0, 
                    "step": 0.1,
                    "tooltip": "[Hunyuan] Shift parameter (connectable)",
                }),
                
                # === FLUX Parameters ===
                "flux_guidance": ("FLOAT", {
                    "default": 3.5, 
                    "min": 0.0, 
                    "max": 100.0, 
                    "step": 0.1,
                    "tooltip": "[FLUX/FLUX2] Guidance scale (connectable)",
                }),
                
                # === Video Parameters (WAN, Hunyuan) ===
                "fps": ("INT", {
                    "default": 24, 
                    "min": 1, 
                    "max": 120,
                    "tooltip": "[Video Models] Frames per second (connectable)",
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }
    
    # Output only the config - global parameters should use ModelCompareGlobals
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "apply_config"
    CATEGORY = "Model Compare"
    DESCRIPTION = "Configure sampling parameters for a specific model variation."
    
    def apply_config(
        self,
        config,
        variation_index: int,
        config_type: str,
        # Optional parameters with defaults (can be connected as inputs)
        seed: int = 0,
        seed_control: str = "fixed",
        steps: int = 20,
        cfg: float = 7.0,
        sampler_name: str = "euler",
        scheduler: str = "normal",
        denoise: float = 1.0,
        qwen_shift: float = 1.15,
        qwen_cfg_norm: bool = True,
        qwen_cfg_norm_multiplier: float = 0.7,
        wan_shift: float = 8.0,
        wan22_shift: float = 5.0,
        wan22_high_start: int = 0,
        wan22_high_end: int = 10,
        wan22_low_start: int = 10,
        wan22_low_end: int = 20,
        hunyuan_shift: float = 7.0,
        flux_guidance: float = 3.5,
        fps: int = 24,
        unique_id=None,
    ):
        """
        Apply sampling configuration to a specific model variation.
        The config is passed through with sampling_configs added/updated.
        
        All parameters are also output for chaining to other nodes.
        """
        import copy
        
        # Deep copy to avoid mutating the original
        new_config = copy.deepcopy(config) if config else {}
        
        # Initialize sampling_configs if not present
        if "sampling_configs" not in new_config:
            new_config["sampling_configs"] = {}
        
        # Zero-indexed internally (user sees 1-indexed)
        idx = variation_index - 1
        
        # Build the sampling config for this variation
        sampling_config = {
            "config_type": config_type,
            "seed": seed,
            "seed_control": seed_control,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": denoise,
            "fps": fps,
        }
        
        # Add type-specific parameters
        if config_type == "QWEN":
            sampling_config.update({
                "qwen_shift": qwen_shift,
                "qwen_cfg_norm": qwen_cfg_norm,
                "qwen_cfg_norm_multiplier": qwen_cfg_norm_multiplier,
            })
        elif config_type == "WAN2.1":
            sampling_config.update({
                "wan_shift": wan_shift,
            })
        elif config_type == "WAN2.2":
            sampling_config.update({
                "wan22_shift": wan22_shift,
                "wan22_high_start": wan22_high_start,
                "wan22_high_end": wan22_high_end,
                "wan22_low_start": wan22_low_start,
                "wan22_low_end": wan22_low_end,
            })
        elif config_type in ["HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15"]:
            sampling_config.update({
                "hunyuan_shift": hunyuan_shift,
            })
        elif config_type in ["FLUX", "FLUX2"]:
            sampling_config.update({
                "flux_guidance": flux_guidance,
            })
        
        # Store by variation index
        new_config["sampling_configs"][idx] = sampling_config
        
        # Also update the model variation's FPS if it exists
        model_variations = new_config.get("model_variations", [])
        if idx < len(model_variations):
            model_variations[idx]["fps"] = fps
            # Store the config_type on the model entry too for reference
            model_variations[idx]["sampling_config_type"] = config_type
        
        print(f"[SamplingConfigChain] Applied config for variation {variation_index} ({config_type})")
        print(f"  Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
        if config_type == "QWEN":
            print(f"  QWEN: shift={qwen_shift}, cfg_norm={qwen_cfg_norm}")
        elif config_type == "WAN2.1":
            print(f"  WAN 2.1: shift={wan_shift}")
        elif config_type == "WAN2.2":
            print(f"  WAN 2.2: shift={wan22_shift}, high={wan22_high_start}-{wan22_high_end}, low={wan22_low_start}-{wan22_low_end}")
        elif config_type in ["HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15"]:
            print(f"  Hunyuan: shift={hunyuan_shift}")
        elif config_type in ["FLUX", "FLUX2"]:
            print(f"  FLUX: guidance={flux_guidance}")
        elif config_type == "Z_IMAGE":
            print(f"  Z_IMAGE: Using Lumina2 (standard sampling)")
        
        # Return only config
        return (new_config,)
    
    @classmethod
    def IS_CHANGED(cls, config, variation_index, config_type, **kwargs):
        """Hash the config to enable caching."""
        import hashlib
        
        # Get values with defaults for optional params
        seed = kwargs.get("seed", 0)
        seed_control = kwargs.get("seed_control", "fixed")
        steps = kwargs.get("steps", 20)
        cfg = kwargs.get("cfg", 7.0)
        sampler_name = kwargs.get("sampler_name", "euler")
        scheduler = kwargs.get("scheduler", "normal")
        denoise = kwargs.get("denoise", 1.0)
        
        hash_input = f"{variation_index}|{config_type}|{seed}|{seed_control}|{steps}|{cfg}|{sampler_name}|{scheduler}|{denoise}"
        
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if isinstance(val, (str, int, float, bool)):
                hash_input += f"|{key}:{val}"
        
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "SamplingConfigChain": SamplingConfigChain,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplingConfigChain": "Sampling Config Chain ⛓️",
}
