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
                    "QWEN", "QWEN_EDIT",
                    "WAN2.1", "WAN2.2", 
                    "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", 
                    "FLUX", "FLUX2", "FLUX_KONTEXT",
                    "Z_IMAGE"
                ], {
                    "default": "STANDARD",
                    "tooltip": "Model type - determines which parameters are shown. QWEN_EDIT for image editing, FLUX_KONTEXT for reference-based generation."
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
                
                # === Latent Size Parameters (all types) ===
                "width": ("INT", {
                    "default": 1024, 
                    "min": 64, 
                    "max": 8192, 
                    "step": 8,
                    "tooltip": "Output width in pixels (connectable)",
                }),
                "height": ("INT", {
                    "default": 1024, 
                    "min": 64, 
                    "max": 8192, 
                    "step": 8,
                    "tooltip": "Output height in pixels (connectable)",
                }),
                
                # === Video Frame Count (video presets only) ===
                "num_frames": ("INT", {
                    "default": 81, 
                    "min": 1, 
                    "max": 1000,
                    "tooltip": "[Video Models] Number of frames to generate (connectable)",
                }),
                
                # === QWEN Parameters ===
                "qwen_shift": ("FLOAT", {
                    "default": 1.15, 
                    "min": 0.0, 
                    "max": 20.0, 
                    "step": 0.1,
                    "tooltip": "[QWEN/QWEN_EDIT] AuraFlow shift parameter - QWEN default is 1.15 (connectable)",
                }),
                "qwen_cfg_norm": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "[QWEN/QWEN_EDIT] Enable CFG normalization (connectable)",
                }),
                "qwen_cfg_norm_multiplier": ("FLOAT", {
                    "default": 0.7, 
                    "min": 0.0, 
                    "max": 1.0, 
                    "step": 0.01,
                    "tooltip": "[QWEN/QWEN_EDIT] CFG normalization multiplier (connectable)",
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
                    "tooltip": "[FLUX/FLUX2/FLUX_KONTEXT] Guidance scale (connectable)",
                }),
                
                # === Video Parameters (WAN, Hunyuan) ===
                "fps": ("INT", {
                    "default": 24, 
                    "min": 1, 
                    "max": 120,
                    "tooltip": "[Video Models] Frames per second (connectable)",
                }),
                
                # === Reference Images (QWEN_EDIT, FLUX2, FLUX_KONTEXT) ===
                "reference_image_1": ("IMAGE", {
                    "tooltip": "[QWEN_EDIT/FLUX2/FLUX_KONTEXT] First reference image for conditioning",
                }),
                "reference_image_2": ("IMAGE", {
                    "tooltip": "[QWEN_EDIT/FLUX2/FLUX_KONTEXT] Second reference image (optional)",
                }),
                "reference_image_3": ("IMAGE", {
                    "tooltip": "[QWEN_EDIT/FLUX2/FLUX_KONTEXT] Third reference image (optional)",
                }),
                
                # === Video I2V Frames (WAN2.1, WAN2.2) ===
                "start_frame": ("IMAGE", {
                    "tooltip": "[WAN/Hunyuan I2V] Starting frame image for image-to-video",
                }),
                "end_frame": ("IMAGE", {
                    "tooltip": "[WAN2.2 FLF2V] Ending frame image for first-last-frame-to-video",
                }),
                
                # === CLIP Vision (Hunyuan I2V) ===
                "clip_vision": ("CLIP_VISION", {
                    "tooltip": "[Hunyuan I2V] CLIP Vision model for image encoding",
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
        # Latent size parameters
        width: int = 1024,
        height: int = 1024,
        num_frames: int = 81,
        # QWEN parameters
        qwen_shift: float = 1.15,
        qwen_cfg_norm: bool = True,
        qwen_cfg_norm_multiplier: float = 0.7,
        # WAN parameters
        wan_shift: float = 8.0,
        wan22_shift: float = 5.0,
        wan22_high_start: int = 0,
        wan22_high_end: int = 10,
        wan22_low_start: int = 10,
        wan22_low_end: int = 20,
        # Hunyuan parameters
        hunyuan_shift: float = 7.0,
        # FLUX parameters
        flux_guidance: float = 3.5,
        # Video parameters
        fps: int = 24,
        # Reference images (optional)
        reference_image_1=None,
        reference_image_2=None,
        reference_image_3=None,
        # I2V frames (optional)
        start_frame=None,
        end_frame=None,
        # CLIP Vision (optional)
        clip_vision=None,
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
            "width": width,
            "height": height,
        }
        
        # Add video frame count for video models
        if config_type in ["WAN2.1", "WAN2.2", "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15"]:
            sampling_config["num_frames"] = num_frames
        
        # Add type-specific parameters
        if config_type in ["QWEN", "QWEN_EDIT"]:
            sampling_config.update({
                "qwen_shift": qwen_shift,
                "qwen_cfg_norm": qwen_cfg_norm,
                "qwen_cfg_norm_multiplier": qwen_cfg_norm_multiplier,
            })
            # QWEN_EDIT can have reference images
            if config_type == "QWEN_EDIT":
                ref_images = []
                if reference_image_1 is not None:
                    ref_images.append(reference_image_1)
                if reference_image_2 is not None:
                    ref_images.append(reference_image_2)
                if reference_image_3 is not None:
                    ref_images.append(reference_image_3)
                if ref_images:
                    sampling_config["reference_images"] = ref_images
        elif config_type == "WAN2.1":
            sampling_config.update({
                "wan_shift": wan_shift,
            })
            # WAN2.1 I2V support
            if start_frame is not None:
                sampling_config["start_frame"] = start_frame
        elif config_type == "WAN2.2":
            sampling_config.update({
                "wan22_shift": wan22_shift,
                "wan22_high_start": wan22_high_start,
                "wan22_high_end": wan22_high_end,
                "wan22_low_start": wan22_low_start,
                "wan22_low_end": wan22_low_end,
            })
            # WAN2.2 I2V/FLF2V support
            if start_frame is not None:
                sampling_config["start_frame"] = start_frame
            if end_frame is not None:
                sampling_config["end_frame"] = end_frame
        elif config_type == "HUNYUAN_VIDEO":
            sampling_config.update({
                "hunyuan_shift": hunyuan_shift,
            })
        elif config_type == "HUNYUAN_VIDEO_15":
            sampling_config.update({
                "hunyuan_shift": hunyuan_shift,
            })
            # Hunyuan 1.5 I2V support
            if start_frame is not None:
                sampling_config["start_frame"] = start_frame
            if clip_vision is not None:
                sampling_config["clip_vision"] = clip_vision
        elif config_type in ["FLUX", "FLUX2", "FLUX_KONTEXT"]:
            sampling_config.update({
                "flux_guidance": flux_guidance,
            })
            # FLUX2 and FLUX_KONTEXT can have reference images
            if config_type in ["FLUX2", "FLUX_KONTEXT"]:
                ref_images = []
                if reference_image_1 is not None:
                    ref_images.append(reference_image_1)
                if reference_image_2 is not None:
                    ref_images.append(reference_image_2)
                if reference_image_3 is not None:
                    ref_images.append(reference_image_3)
                if ref_images:
                    sampling_config["reference_images"] = ref_images
        elif config_type == "Z_IMAGE":
            # Z_IMAGE (Lumina2) uses AuraFlow sampling with shift parameter
            sampling_config.update({
                "qwen_shift": qwen_shift,  # Lumina2 uses the same shift as QWEN
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
        print(f"  Size: {width}x{height}")
        if config_type in ["QWEN", "QWEN_EDIT"]:
            has_refs = "reference_images" in sampling_config
            print(f"  QWEN: shift={qwen_shift}, cfg_norm={qwen_cfg_norm}, has_refs={has_refs}")
        elif config_type == "WAN2.1":
            has_start = "start_frame" in sampling_config
            print(f"  WAN 2.1: shift={wan_shift}, frames={num_frames}, has_start_frame={has_start}")
        elif config_type == "WAN2.2":
            has_start = "start_frame" in sampling_config
            has_end = "end_frame" in sampling_config
            print(f"  WAN 2.2: shift={wan22_shift}, high={wan22_high_start}-{wan22_high_end}, low={wan22_low_start}-{wan22_low_end}, frames={num_frames}, has_start={has_start}, has_end={has_end}")
        elif config_type == "HUNYUAN_VIDEO":
            print(f"  Hunyuan: shift={hunyuan_shift}, frames={num_frames}")
        elif config_type == "HUNYUAN_VIDEO_15":
            has_start = "start_frame" in sampling_config
            has_clip_vision = "clip_vision" in sampling_config
            print(f"  Hunyuan 1.5: shift={hunyuan_shift}, frames={num_frames}, has_start_frame={has_start}, has_clip_vision={has_clip_vision}")
        elif config_type in ["FLUX", "FLUX2", "FLUX_KONTEXT"]:
            has_refs = "reference_images" in sampling_config
            print(f"  {config_type}: guidance={flux_guidance}, has_refs={has_refs}")
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
