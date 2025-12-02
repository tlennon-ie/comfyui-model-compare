"""
Sampling Config Chain Node

Allows users to configure sampling parameters per-model-variation.
Each chain node matches a model variation from the loader and provides
model-specific sampling parameters.

All parameters are "convertible widgets" - they can be used as regular widgets
OR converted to inputs to receive values from other nodes/chains.

Multi-Value Support:
Many fields now support comma-separated values for variation expansion.
- Samplers: "euler, dpmpp_2m, ddim" → samples with each
- Schedulers: "normal, karras" → samples with each
- Steps: "15, 20, 30" → samples with each step count
- CFG: "1.0, 1.5, 2.0" → samples with each CFG value
- Dimensions: "1024, 768" → samples with each width/height

Flow:
ModelCompareLoaders -> ConfigChain1 -> ConfigChain2 -> ... -> SamplerCompareAdvanced
"""

import time
import comfy.samplers

# Import variation expander for multi-value support
try:
    from .variation_expander import (
        parse_samplers, parse_schedulers, parse_steps, parse_cfg,
        parse_denoise, parse_dimensions, parse_shift, parse_frames, parse_fps,
        parse_numeric_list, count_variations, check_variation_warning
    )
    VARIATION_SUPPORT = True
except ImportError:
    VARIATION_SUPPORT = False
    print("[SamplingConfigChain] Warning: variation_expander not found, multi-value support disabled")


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
                    "control_after_generate": False,  # Disable auto-randomize - we have explicit seed_control
                    "tooltip": "Random seed for this variation. Use seed_control to set behavior.",
                }),
                "seed_control": (["fixed", "randomize", "increment", "decrement"], {
                    "default": "fixed",
                    "tooltip": "Seed behavior: fixed=exact value, randomize=new random each run, increment=+1 each combo, decrement=-1 each combo",
                }),
                "steps": ("STRING", {
                    "default": "20",
                    "tooltip": "Number of sampling steps. Comma-separated for variations (e.g., '15, 20, 30')",
                }),
                "cfg": ("STRING", {
                    "default": "7.0",
                    "tooltip": "Classifier-free guidance scale. Comma-separated for variations (e.g., '1.0, 1.5, 2.0')",
                }),
                "sampler_name": ("STRING", {
                    "default": "euler",
                    "tooltip": "Sampling algorithm(s). Comma-separated for variations. Valid: euler, euler_ancestral, heun, dpm_2, dpm_2_ancestral, lms, dpm_fast, dpm_adaptive, dpmpp_2s_ancestral, dpmpp_sde, dpmpp_2m, dpmpp_2m_sde, dpmpp_3m_sde, ddpm, lcm, ipndm, ipndm_v, deis, ddim, uni_pc, uni_pc_bh2",
                }),
                "scheduler": ("STRING", {
                    "default": "normal",
                    "tooltip": "Noise schedule(s). Comma-separated for variations. Valid: normal, karras, exponential, sgm_uniform, simple, ddim_uniform, beta, linear_quadratic, kl_optimal",
                }),
                "denoise": ("FLOAT", {
                    "default": 1.0, 
                    "min": 0.0, 
                    "max": 1.0, 
                    "step": 0.01,
                    "tooltip": "Denoising strength (connectable)",
                }),
                
                # === Latent Size Parameters (all types) ===
                "width": ("STRING", {
                    "default": "1024",
                    "tooltip": "Output width in pixels. Comma-separated for variations (e.g., '1024, 768, 512')",
                }),
                "height": ("STRING", {
                    "default": "1024",
                    "tooltip": "Output height in pixels. Comma-separated for variations (e.g., '1024, 768, 512')",
                }),
                
                # === Video Frame Count (video presets only) ===
                "num_frames": ("INT", {
                    "default": 81, 
                    "min": 1, 
                    "max": 1000,
                    "tooltip": "[Video Models] Number of frames to generate (connectable)",
                }),
                
                # === QWEN Parameters ===
                "qwen_shift": ("STRING", {
                    "default": "1.15",
                    "tooltip": "[QWEN/QWEN_EDIT] AuraFlow shift. Comma-separated for variations (e.g., '1.0, 1.15, 1.5')",
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
                "wan_shift": ("STRING", {
                    "default": "8.0",
                    "tooltip": "[WAN 2.1] Shift. Comma-separated for variations (e.g., '6.0, 8.0, 10.0')",
                }),
                "wan22_shift": ("STRING", {
                    "default": "8.0",
                    "tooltip": "[WAN 2.2] Shift. Comma-separated for variations (e.g., '6.0, 8.0, 10.0')",
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
                "hunyuan_shift": ("STRING", {
                    "default": "7.0",
                    "tooltip": "[Hunyuan] Shift. Comma-separated for variations (e.g., '5.0, 7.0, 9.0')",
                }),
                
                # === Z_IMAGE/Lumina2 Parameters ===
                "lumina_shift": ("STRING", {
                    "default": "3.0",
                    "tooltip": "[Z_IMAGE/Lumina2] Shift. Comma-separated for variations (e.g., '2.0, 3.0, 4.0')",
                }),
                
                # === FLUX Parameters ===
                "flux_guidance": ("STRING", {
                    "default": "3.5",
                    "tooltip": "[FLUX/FLUX2/FLUX_KONTEXT] Guidance. Comma-separated for variations (e.g., '2.5, 3.5, 4.5')",
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
        # Now STRING types for multi-value support
        seed: int = 0,
        seed_control: str = "fixed",
        steps: str = "20",
        cfg: str = "7.0",
        sampler_name: str = "euler",
        scheduler: str = "normal",
        denoise: float = 1.0,
        # Latent size parameters
        width: str = "1024",
        height: str = "1024",
        num_frames: int = 81,
        # QWEN parameters
        qwen_shift: str = "1.15",
        qwen_cfg_norm: bool = True,
        qwen_cfg_norm_multiplier: float = 0.7,
        # WAN parameters
        wan_shift: str = "8.0",
        wan22_shift: str = "8.0",
        wan22_high_start: int = 0,
        wan22_high_end: int = 10,
        wan22_low_start: int = 10,
        wan22_low_end: int = 20,
        # Hunyuan parameters
        hunyuan_shift: str = "7.0",
        # Z_IMAGE/Lumina2 parameters
        lumina_shift: str = "3.0",
        # FLUX parameters
        flux_guidance: str = "3.5",
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
        
        Multi-value fields (comma-separated) are parsed into lists for expansion.
        """
        import copy
        
        # Deep copy to avoid mutating the original
        new_config = copy.deepcopy(config) if config else {}
        
        # Initialize sampling_configs if not present
        if "sampling_configs" not in new_config:
            new_config["sampling_configs"] = {}
        
        # Zero-indexed internally (user sees 1-indexed)
        idx = variation_index - 1
        
        # Parse multi-value fields into lists
        if VARIATION_SUPPORT:
            samplers_list = parse_samplers(sampler_name)
            schedulers_list = parse_schedulers(scheduler)
            steps_list = parse_steps(steps)
            cfg_list = parse_cfg(cfg)
            width_list = parse_dimensions(width)
            height_list = parse_dimensions(height)
            qwen_shift_list = parse_shift(qwen_shift, 1.15)
            wan_shift_list = parse_shift(wan_shift, 8.0)
            wan22_shift_list = parse_shift(wan22_shift, 8.0)
            hunyuan_shift_list = parse_shift(hunyuan_shift, 7.0)
            lumina_shift_list = parse_shift(lumina_shift, 3.0)
            flux_guidance_list = parse_numeric_list(flux_guidance, float, 3.5, 0.0, 100.0)
        else:
            # Fallback: single values
            samplers_list = [sampler_name]
            schedulers_list = [scheduler]
            steps_list = [int(steps) if isinstance(steps, str) else steps]
            cfg_list = [float(cfg) if isinstance(cfg, str) else cfg]
            width_list = [int(width) if isinstance(width, str) else width]
            height_list = [int(height) if isinstance(height, str) else height]
            qwen_shift_list = [float(qwen_shift) if isinstance(qwen_shift, str) else qwen_shift]
            wan_shift_list = [float(wan_shift) if isinstance(wan_shift, str) else wan_shift]
            wan22_shift_list = [float(wan22_shift) if isinstance(wan22_shift, str) else wan22_shift]
            hunyuan_shift_list = [float(hunyuan_shift) if isinstance(hunyuan_shift, str) else hunyuan_shift]
            lumina_shift_list = [float(lumina_shift) if isinstance(lumina_shift, str) else lumina_shift]
            flux_guidance_list = [float(flux_guidance) if isinstance(flux_guidance, str) else flux_guidance]
        
        # Build the sampling config for this variation
        # Store BOTH single values (first item, for backward compat) AND full lists
        sampling_config = {
            "config_type": config_type,
            "seed": seed,
            "seed_control": seed_control,  # fixed, randomize, increment, decrement
            # Single values (first from each list) for backward compatibility
            "steps": steps_list[0],
            "cfg": cfg_list[0],
            "sampler_name": samplers_list[0],
            "scheduler": schedulers_list[0],
            "denoise": denoise,
            "fps": fps,
            "width": width_list[0],
            "height": height_list[0],
            # Full lists for expansion
            "steps_list": steps_list,
            "cfg_list": cfg_list,
            "sampler_names": samplers_list,
            "schedulers": schedulers_list,
            "width_list": width_list,
            "height_list": height_list,
        }
        
        # Calculate variation count for this config
        variation_count = (
            len(samplers_list) * len(schedulers_list) * len(steps_list) * 
            len(cfg_list) * len(width_list) * len(height_list)
        )
        sampling_config["_variation_count"] = variation_count
        
        # Add video frame count for video models
        if config_type in ["WAN2.1", "WAN2.2", "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15"]:
            sampling_config["num_frames"] = num_frames
        
        # Add type-specific parameters (with lists)
        if config_type in ["QWEN", "QWEN_EDIT"]:
            sampling_config.update({
                "qwen_shift": qwen_shift_list[0],
                "qwen_shift_list": qwen_shift_list,
                "qwen_cfg_norm": qwen_cfg_norm,
                "qwen_cfg_norm_multiplier": qwen_cfg_norm_multiplier,
            })
            variation_count *= len(qwen_shift_list)
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
                "wan_shift": wan_shift_list[0],
                "wan_shift_list": wan_shift_list,
            })
            variation_count *= len(wan_shift_list)
            # WAN2.1 I2V support
            if start_frame is not None:
                sampling_config["start_frame"] = start_frame
        elif config_type == "WAN2.2":
            sampling_config.update({
                "wan22_shift": wan22_shift_list[0],
                "wan22_shift_list": wan22_shift_list,
                "wan22_high_start": wan22_high_start,
                "wan22_high_end": wan22_high_end,
                "wan22_low_start": wan22_low_start,
                "wan22_low_end": wan22_low_end,
            })
            variation_count *= len(wan22_shift_list)
            # WAN2.2 I2V/FLF2V support
            if start_frame is not None:
                sampling_config["start_frame"] = start_frame
            if end_frame is not None:
                sampling_config["end_frame"] = end_frame
        elif config_type == "HUNYUAN_VIDEO":
            sampling_config.update({
                "hunyuan_shift": hunyuan_shift_list[0],
                "hunyuan_shift_list": hunyuan_shift_list,
            })
            variation_count *= len(hunyuan_shift_list)
        elif config_type == "HUNYUAN_VIDEO_15":
            sampling_config.update({
                "hunyuan_shift": hunyuan_shift_list[0],
                "hunyuan_shift_list": hunyuan_shift_list,
            })
            variation_count *= len(hunyuan_shift_list)
            # Hunyuan 1.5 I2V support
            if start_frame is not None:
                sampling_config["start_frame"] = start_frame
            if clip_vision is not None:
                sampling_config["clip_vision"] = clip_vision
        elif config_type in ["FLUX", "FLUX2", "FLUX_KONTEXT"]:
            sampling_config.update({
                "flux_guidance": flux_guidance_list[0],
                "flux_guidance_list": flux_guidance_list,
            })
            variation_count *= len(flux_guidance_list)
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
            # NO CFG normalization by default (unlike QWEN)
            sampling_config.update({
                "lumina_shift": lumina_shift_list[0],
                "lumina_shift_list": lumina_shift_list,
            })
            variation_count *= len(lumina_shift_list)
        
        # Update final variation count
        sampling_config["_variation_count"] = variation_count
        
        # Check for warning threshold
        warning_msg = None
        if VARIATION_SUPPORT:
            warning_msg = check_variation_warning(variation_count)
        
        # Store by variation index
        new_config["sampling_configs"][idx] = sampling_config
        
        # Also update the model variation's FPS if it exists
        model_variations = new_config.get("model_variations", [])
        if idx < len(model_variations):
            model_variations[idx]["fps"] = fps
            # Store the config_type on the model entry too for reference
            model_variations[idx]["sampling_config_type"] = config_type
        
        # Return only config
        return (new_config,)
    
    @classmethod
    def IS_CHANGED(cls, config, variation_index, config_type, **kwargs):
        """Hash the config to enable caching."""
        import hashlib
        
        # Get values with defaults for optional params
        seed = kwargs.get("seed", 0)
        steps = kwargs.get("steps", 20)
        cfg = kwargs.get("cfg", 7.0)
        sampler_name = kwargs.get("sampler_name", "euler")
        scheduler = kwargs.get("scheduler", "normal")
        denoise = kwargs.get("denoise", 1.0)
        
        hash_input = f"{variation_index}|{config_type}|{seed}|{steps}|{cfg}|{sampler_name}|{scheduler}|{denoise}"
        
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
