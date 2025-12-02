"""
Advanced Model Compare Sampler - Cross-preset comparison with auto-detection.
Supports comparing models across different architectures (FLUX vs QWEN vs WAN vs Hunyuan).
All sampling parameters exposed - auto-detects which to use per model.

LAZY LOADING: Models are loaded on-demand per combination to minimize VRAM usage.
Smart unloading occurs only when model/VAE/CLIP config changes between combinations.

MULTI-VALUE VARIATIONS: Sampling configs can contain comma-separated values for
samplers, schedulers, steps, cfg, dimensions, and shift parameters. These are
expanded into additional variations automatically.
"""

import gc
import hashlib
import itertools
import torch
import folder_paths
import comfy.sd
import comfy.utils
import comfy.sample
import comfy.samplers
import comfy.model_management
from typing import List, Dict, Tuple, Any, Optional
from comfy_extras.nodes_model_advanced import ModelSamplingSD3, ModelSamplingAuraFlow, RescaleCFG, ModelSamplingFlux

# Import variation expander for multi-value support
try:
    from .variation_expander import (
        expand_sampling_config, count_variations, check_variation_warning,
        WARNING_THRESHOLD
    )
    VARIATION_SUPPORT = True
except ImportError:
    VARIATION_SUPPORT = False
    WARNING_THRESHOLD = 20
    print("[SamplerCompareAdvanced] Warning: variation_expander not found, multi-value support disabled")

# Import tracker for progress updates
try:
    from .compare_tracker import (
        update_tracker_state, add_tracker_warning, _force_reset_tracker_state,
        start_iteration, record_step_complete, complete_iteration
    )
    TRACKER_SUPPORT = True
except ImportError:
    TRACKER_SUPPORT = False
    def update_tracker_state(**kwargs): pass
    def add_tracker_warning(warning): pass
    def _force_reset_tracker_state(): pass
    def start_iteration(combo_idx, total_steps): pass
    def record_step_complete(step): pass
    def complete_iteration(combo_idx): pass

class SamplerCompareAdvanced:
    """
    Advanced sampler for cross-model comparison with LAZY LOADING.
    Models are loaded on-demand per combination, then unloaded when config changes.
    Supports: FLUX, FLUX2, QWEN, WAN 2.1/2.2, Hunyuan 1.0/1.5, SDXL, SD
    
    PER-COMBINATION CACHING:
    Results are cached per combination. When only some combinations change,
    only those will be re-sampled while unchanged combinations use cached results.
    """
    
    RETURN_TYPES = ("IMAGE", "MODEL_COMPARE_CONFIG", "STRING")
    RETURN_NAMES = ("images", "config", "labels")
    FUNCTION = "sample_all_combinations"
    CATEGORY = "Model Compare/Sampling"
    OUTPUT_NODE = True
    
    # Class-level cache for per-combination results
    # Key: hash of combination config, Value: (image, label, frame_count)
    _combination_cache = {}
    _cache_max_size = 50  # Max number of cached combinations
    
    # Available global parameter types
    GLOBAL_PARAM_TYPES = [
        "NONE",
        "seed",
        "steps",
        "cfg",
        "denoise",
        "sampler_name",
        "scheduler",
    ]
    
    # Seed control modes (matching ComfyUI's standard behavior)
    SEED_CONTROL_MODES = ["fixed", "increment", "decrement", "randomize"]

    @classmethod
    def INPUT_TYPES(cls):
        inputs = {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                # Dynamic global fields slider
                "num_global_fields": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 8,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of global parameters to set (override per-variation configs)"
                }),
            },
            "optional": {
                # Global dimension overrides
                "global_width": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 8192,
                    "step": 8,
                    "tooltip": "Global width override (0 = use config chain values). Overrides all variations."
                }),
                "global_height": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 8192,
                    "step": 8,
                    "tooltip": "Global height override (0 = use config chain values). Overrides all variations."
                }),
                "global_num_frames": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 1000,
                    "tooltip": "Global frame count override for video models (0 = use config chain values)."
                }),
            }
        }
        
        # Add dynamic global parameter fields (8 slots)
        for i in range(8):
            # Parameter type selector
            inputs["optional"][f"global_param_type_{i}"] = (cls.GLOBAL_PARAM_TYPES, {
                "default": "NONE",
                "tooltip": f"Global {i+1}: Select which parameter to set globally"
            })
            
            # Seed value - STRING to support comma-separated multi-values
            inputs["optional"][f"global_value_seed_{i}"] = ("STRING", {
                "default": "0",
                "tooltip": f"Global {i+1}: Seed value(s) - comma-separated for variations (e.g., '123, 456, 789')"
            })
            
            # Steps value - STRING to support comma-separated multi-values
            inputs["optional"][f"global_value_steps_{i}"] = ("STRING", {
                "default": "20",
                "tooltip": f"Global {i+1}: Step count(s) - comma-separated for variations (e.g., '15, 20, 30')"
            })
            
            # CFG value - STRING to support comma-separated multi-values
            inputs["optional"][f"global_value_cfg_{i}"] = ("STRING", {
                "default": "7.0",
                "tooltip": f"Global {i+1}: CFG value(s) - comma-separated for variations (e.g., '1.0, 1.5, 2.0')"
            })
            
            # Denoise value - STRING to support comma-separated multi-values
            inputs["optional"][f"global_value_denoise_{i}"] = ("STRING", {
                "default": "1.0",
                "tooltip": f"Global {i+1}: Denoise value(s) - comma-separated for variations (e.g., '0.5, 0.75, 1.0')"
            })
            
            # Sampler selector - STRING to support comma-separated multi-values
            inputs["optional"][f"global_value_sampler_{i}"] = ("STRING", {
                "default": "euler",
                "tooltip": f"Global {i+1}: Sampler name(s) - comma-separated for variations (e.g., 'euler, dpmpp_2m, ddim')"
            })
            
            # Scheduler selector - STRING to support comma-separated multi-values
            inputs["optional"][f"global_value_scheduler_{i}"] = ("STRING", {
                "default": "normal",
                "tooltip": f"Global {i+1}: Scheduler name(s) - comma-separated for variations (e.g., 'normal, karras, beta')"
            })
            
            # Seed control mode (only used when param_type is 'seed')
            inputs["optional"][f"global_seed_control_{i}"] = (cls.SEED_CONTROL_MODES, {
                "default": "fixed",
                "tooltip": f"Global {i+1}: Seed control mode (fixed/increment/decrement/randomize)"
            })
        
        return inputs
    
    def _build_global_config(self, num_global_fields: int, kwargs: Dict) -> Dict:
        """
        Build global config from dynamic fields.
        
        Stores RAW STRING values for multi-value fields so they can be expanded later.
        The expansion happens in _expand_combinations_with_global_variations.
        """
        config = {
            "seed": None,
            "seed_control": "fixed",
            "steps": None,
            "cfg": None,
            "denoise": None,
            "sampler_name": None,
            "scheduler": None,
        }
        
        for i in range(num_global_fields):
            param_type = kwargs.get(f"global_param_type_{i}", "NONE")
            
            if param_type == "NONE":
                continue
            
            # Store raw string values - parsing/expansion happens later
            if param_type == "seed":
                config["seed"] = kwargs.get(f"global_value_seed_{i}", "0")
                config["seed_control"] = kwargs.get(f"global_seed_control_{i}", "fixed")
            elif param_type == "steps":
                config["steps"] = kwargs.get(f"global_value_steps_{i}", "20")
            elif param_type == "cfg":
                config["cfg"] = kwargs.get(f"global_value_cfg_{i}", "7.0")
            elif param_type == "denoise":
                config["denoise"] = kwargs.get(f"global_value_denoise_{i}", "1.0")
            elif param_type == "sampler_name":
                config["sampler_name"] = kwargs.get(f"global_value_sampler_{i}", "euler")
            elif param_type == "scheduler":
                config["scheduler"] = kwargs.get(f"global_value_scheduler_{i}", "normal")
        
        return config

    def detect_model_type(self, model_obj) -> str:
        """
        Auto-detect model type from model object.
        Returns: 'flux', 'flux2', 'qwen', 'wan21', 'wan22', 'hunyuan', 'hunyuan15', 'sdxl', 'sd'
        """
        if not model_obj:
            return 'sd'
        
        try:
            # Check latent format for FLUX2 (128 channels)
            latent_format = model_obj.get_model_object("latent_format")
            if latent_format:
                if hasattr(latent_format, 'latent_channels') and latent_format.latent_channels == 128:
                    return 'flux2'
            
            # Check model config
            model_config = getattr(model_obj, 'model_config', None)
            if model_config:
                unet_config = getattr(model_config, 'unet_config', {})
                
                # Check for FLUX (16 channels, not 128)
                if unet_config.get('in_channels') == 16:
                    return 'flux'
                
                # Check for Hunyuan 1.5 (has vision_in_dim)
                if unet_config.get('vision_in_dim') == 1152:
                    return 'hunyuan15'
                
                # Check for Hunyuan (has specific config)
                if 'hunyuan' in str(type(model_config)).lower():
                    return 'hunyuan'
                
                # Check for WAN
                if 'wan' in str(type(model_config)).lower():
                    # WAN 2.2 typically uses different architecture
                    return 'wan21'  # Default, would need more info for 2.2
                
                # Check for QWEN
                if 'qwen' in str(type(model_config)).lower():
                    return 'qwen'
                
                # Check for SDXL (in_channels == 4, specific size)
                if unet_config.get('in_channels') == 4:
                    if unet_config.get('context_dim') == 2048:
                        return 'sdxl'
        except Exception as e:
            print(f"[SamplerCompareAdvanced] Model detection error: {e}")
        
        return 'sd'  # Default fallback

    # ===== LAZY LOADING HELPERS =====
    
    def _get_clip_type_enum(self, clip_type_str: str):
        """Convert clip_type string to CLIPType enum."""
        import comfy.sd
        mapping = {
            "sd": comfy.sd.CLIPType.STABLE_DIFFUSION,
            "sdxl": getattr(comfy.sd.CLIPType, "STABLE_DIFFUSION", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "sd3": getattr(comfy.sd.CLIPType, "SD3", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux": getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux2": getattr(comfy.sd.CLIPType, "FLUX2", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux_kontext": getattr(comfy.sd.CLIPType, "FLUX2", comfy.sd.CLIPType.STABLE_DIFFUSION),  # FLUX_KONTEXT uses FLUX2 CLIP type
            "wan": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "wan22": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "hunyuan_video": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "hunyuan_video_15": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO_15", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "qwen": getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "qwen_edit": getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION),  # QWEN_EDIT uses same CLIP type as QWEN
            "lumina2": getattr(comfy.sd.CLIPType, "LUMINA2", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "z_image": getattr(comfy.sd.CLIPType, "LUMINA2", comfy.sd.CLIPType.STABLE_DIFFUSION),  # Z_IMAGE uses LUMINA2 CLIP type
        }
        key = clip_type_str.upper().replace("_", "")
        if hasattr(comfy.sd.CLIPType, key):
            return getattr(comfy.sd.CLIPType, key)
        return mapping.get(clip_type_str, comfy.sd.CLIPType.STABLE_DIFFUSION)
    
    def _create_latent_for_type(self, model_type: str, width: int, height: int, num_frames: int = 1, batch_size: int = 1) -> Dict:
        """
        Create an appropriate latent tensor based on model type.
        
        Latent channel counts:
        - SD/SDXL: 4 channels (standard VAE)
        - FLUX: 16 channels
        - FLUX2/FLUX_KONTEXT: 128 channels (with spatial compression)
        - QWEN: 16 channels (uses Wan21 latent format)
        - Lumina2: 16 channels (Flux format)
        - WAN2.1/2.2: 16 channels, 5D tensor for video
        - Hunyuan: 16 channels, 5D tensor for video
        
        Args:
            model_type: Type of model (sd, sdxl, flux, flux2, qwen, wan21, etc.)
            width: Output width in pixels
            height: Output height in pixels
            num_frames: Number of frames for video models (default 1 for images)
            batch_size: Batch size (default 1)
        
        Returns:
            Dict with "samples" key containing the latent tensor
        """
        device = comfy.model_management.intermediate_device()
        
        # Calculate latent dimensions (VAE compression factor is 8)
        latent_h = height // 8
        latent_w = width // 8
        
        is_video_model = model_type in ['wan21', 'wan22', 'hunyuan', 'hunyuan15']
        
        if model_type == 'flux2' or model_type == 'flux_kontext':
            # FLUX2/FLUX_KONTEXT uses 128 channels with additional spatial compression
            channels = 128
            latent = torch.zeros(
                [batch_size, channels, latent_h // 2, latent_w // 2],
                device=device
            )
        elif model_type in ['flux', 'qwen', 'qwen_edit', 'lumina2', 'z_image']:
            # FLUX, QWEN, Lumina2, Z_IMAGE use 16 channels
            channels = 16
            latent = torch.zeros(
                [batch_size, channels, latent_h, latent_w],
                device=device
            )
        elif model_type == 'wan22':
            # WAN 2.2 uses 48 channels (new VAE format)
            channels = 48
            latent = torch.zeros(
                [batch_size, channels, num_frames, latent_h, latent_w],
                device=device
            )
        elif model_type in ['wan21', 'hunyuan', 'hunyuan15']:
            # WAN 2.1, Hunyuan: 5D tensor [B, C, F, H, W] with 16 channels
            channels = 16
            latent = torch.zeros(
                [batch_size, channels, num_frames, latent_h, latent_w],
                device=device
            )
        else:
            # SD/SDXL: 4 channels
            channels = 4
            latent = torch.zeros(
                [batch_size, channels, latent_h, latent_w],
                device=device
            )
        
        return {"samples": latent}
    
    def _get_combination_hash(self, combo: Dict, sampling_cfg: Dict, global_config: Dict, latent_shape: tuple, model_entry: Dict = None, variation_label: str = "") -> str:
        """
        Generate a unique hash for a combination including all parameters that affect output.
        This is used for per-combination caching.
        
        Args:
            combo: The combination dict (model_index, vae_name, prompts, etc.)
            sampling_cfg: The resolved sampling configuration (with _sampling_override applied!)
            global_config: Global config overrides
            latent_shape: Shape tuple (width, height, frames)
            model_entry: The model variation entry (contains display_name, model_path, etc.)
            variation_label: The variation label from multi-value expansion (e.g., "S:euler | Sch:normal")
        """
        # Get model display name from model_entry if provided
        model_display_name = ""
        if model_entry:
            model_display_name = model_entry.get("display_name", model_entry.get("name", ""))
        
        hash_parts = [
            str(combo.get("model_index", 0)),
            str(model_display_name),  # Include model display name/label for cache invalidation
            str(combo.get("vae_name", "")),
            str(combo.get("prompt_positive", "")),
            str(combo.get("prompt_negative", "")),
            str(combo.get("clip_variation", {})),
            str(combo.get("lora_config", {})),
            str(sampling_cfg),  # Now includes _sampling_override values merged in
            str(global_config),
            str(latent_shape),
            str(variation_label),  # Include variation label for uniqueness
        ]
        hash_input = "|".join(hash_parts)
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    def _get_cached_result(self, combo_hash: str) -> Optional[Tuple[Any, str, int]]:
        """Get cached result for a combination if available."""
        return self._combination_cache.get(combo_hash)
    
    def _cache_result(self, combo_hash: str, image: Any, label: str, frame_count: int):
        """Cache the result for a combination."""
        # Simple LRU: if cache is full, remove oldest entries
        if len(self._combination_cache) >= self._cache_max_size:
            # Remove first (oldest) entry
            oldest_key = next(iter(self._combination_cache))
            del self._combination_cache[oldest_key]
        
        self._combination_cache[combo_hash] = (image, label, frame_count)
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached results."""
        cls._combination_cache.clear()
    
    def _load_model(self, model_entry: Dict) -> Tuple[Any, Any]:
        """
        Lazy load a model from stored path.
        Returns (model_obj, model_low_obj) tuple.
        """
        import sys
        model_obj = None
        model_low_obj = None
        
        model_path = model_entry.get("model_path")
        model_type = model_entry.get("model_type")
        
        if not model_path:
            print(f"[SamplerCompareAdvanced] ERROR: No model path in entry")
            return None, None
        
        sys.stdout.flush()
        
        try:
            if model_type == "checkpoint":
                out = comfy.sd.load_checkpoint_guess_config(
                    model_path, 
                    output_vae=True, 
                    output_clip=True, 
                    embedding_directory=folder_paths.get_folder_paths("embeddings")
                )
                model_obj = out[0]
                # Store baked VAE/CLIP if use_baked is True
                if model_entry.get("use_baked_vae_clip"):
                    model_entry["_baked_clip"] = out[1]
                    model_entry["_baked_vae"] = out[2]
            elif model_type == "diffusion":
                model_obj = comfy.sd.load_diffusion_model(model_path, model_options={})
            
            # Load low noise model if WAN 2.2
            model_low_path = model_entry.get("model_low_path")
            if model_low_path:
                model_low_obj = comfy.sd.load_diffusion_model(model_low_path, model_options={})
        except Exception as e:
            print(f"[SamplerCompareAdvanced] ERROR loading model: {e}", flush=True)
            import traceback
            traceback.print_exc()
            sys.stdout.flush()
            return None, None
        
        return model_obj, model_low_obj
    
    def _load_vae(self, vae_name: str, config: Dict, model_entry: Dict) -> Any:
        """
        Lazy load a VAE.
        Returns VAE object.
        """
        if vae_name == "__baked__":
            # Use baked VAE from checkpoint
            baked_vae = model_entry.get("_baked_vae")
            if baked_vae:
                return baked_vae
            else:
                return None
        
        if vae_name == "NONE" or not vae_name:
            return None
        
        vae_paths = config.get("vae_paths", {})
        vae_path = vae_paths.get(vae_name)
        
        if not vae_path:
            return None
        
        vae = comfy.sd.VAE(sd=comfy.utils.load_torch_file(vae_path))
        return vae
    
    def _load_clip(self, clip_var: Dict, config: Dict, model_entry: Dict) -> Any:
        """
        Lazy load a CLIP.
        Returns CLIP object.
        """
        if not clip_var:
            return None
        
        clip_type = clip_var.get("type")
        clip_type_str = clip_var.get("clip_type", "sd")
        device = clip_var.get("device", "default")
        
        # Build model options for device
        model_options = {}
        if device == "cpu":
            model_options["load_device"] = torch.device("cpu")
            model_options["offload_device"] = torch.device("cpu")
        
        if clip_type == "baked":
            # Use baked CLIP from checkpoint
            baked_clip = model_entry.get("_baked_clip")
            if baked_clip:
                return baked_clip
            else:
                return None
        
        elif clip_type == "pair":
            # Dual CLIP (FLUX, Hunyuan)
            path_a = clip_var.get("a_path")
            path_b = clip_var.get("b_path")
            if path_a and path_b:
                clip_obj = comfy.sd.load_clip(
                    ckpt_paths=[path_a, path_b],
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    clip_type=self._get_clip_type_enum(clip_type_str),
                    model_options=model_options
                )
                return clip_obj
        
        elif clip_type == "single":
            path = clip_var.get("model_path")
            if path:
                clip_obj = comfy.sd.load_clip(
                    ckpt_paths=[path],
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    clip_type=self._get_clip_type_enum(clip_type_str),
                    model_options=model_options
                )
                return clip_obj
        
        return None
    
    def _encode_qwen_edit_conditioning(self, clip, vae, prompt: str, reference_images: List[torch.Tensor]) -> Tuple[Any, Any]:
        """
        Encode conditioning for QWEN Image Edit models.
        
        Based on TextEncodeQwenImageEditPlus from ComfyUI:
        - Images scaled to 384x384 for tokenization (CLIP vision)
        - Images scaled to 1024x1024 for VAE encoding (reference latents)
        - Uses special LLAMA template for image editing
        
        Args:
            clip: CLIP model
            vae: VAE for encoding reference images
            prompt: Text prompt
            reference_images: List of reference images (up to 3)
        
        Returns:
            Tuple of (positive_conditioning, negative_conditioning)
        """
        import math
        import node_helpers
        
        ref_latents = []
        images_vl = []
        llama_template = "<|im_start|>system\nDescribe the key features of the input image (color, shape, size, texture, objects, background), then explain how the user's text instruction should alter or modify the image. Generate a new image that meets the user's requirements while maintaining consistency with the original input where appropriate.<|im_end|>\n<|im_start|>user\n{}<|im_end|>\n<|im_start|>assistant\n"
        image_prompt = ""
        
        for i, image in enumerate(reference_images):
            if image is not None:
                samples = image.movedim(-1, 1)
                
                # Scale to 384x384 for CLIP vision tokenization
                total = int(384 * 384)
                scale_by = math.sqrt(total / (samples.shape[3] * samples.shape[2]))
                width = round(samples.shape[3] * scale_by)
                height = round(samples.shape[2] * scale_by)
                
                s = comfy.utils.common_upscale(samples, width, height, "area", "disabled")
                images_vl.append(s.movedim(1, -1))
                
                if vae is not None:
                    # Scale to 1024x1024 for VAE encoding (reference latents)
                    total = int(1024 * 1024)
                    scale_by = math.sqrt(total / (samples.shape[3] * samples.shape[2]))
                    width = round(samples.shape[3] * scale_by / 8.0) * 8
                    height = round(samples.shape[2] * scale_by / 8.0) * 8
                    
                    s = comfy.utils.common_upscale(samples, width, height, "area", "disabled")
                    ref_latents.append(vae.encode(s.movedim(1, -1)[:, :, :, :3]))
                
                image_prompt += "Picture {}: <|vision_start|><|image_pad|><|vision_end|>".format(i + 1)
        
        # Encode positive conditioning
        tokens = clip.tokenize(image_prompt + prompt, images=images_vl, llama_template=llama_template)
        positive = clip.encode_from_tokens_scheduled(tokens)
        
        if len(ref_latents) > 0:
            positive = node_helpers.conditioning_set_values(positive, {"reference_latents": ref_latents}, append=True)
        
        # Encode negative conditioning (empty for QWEN Edit)
        neg_tokens = clip.tokenize("", images=[])
        negative = clip.encode_from_tokens_scheduled(neg_tokens)
        
        return positive, negative
    
    def _encode_flux_reference_conditioning(self, clip, vae, prompt: str, reference_images: List[torch.Tensor], flux_guidance: float) -> Tuple[Any, Any]:
        """
        Encode conditioning for FLUX2/FLUX_KONTEXT with reference images.
        
        Based on ReferenceLatent pattern from ComfyUI:
        - VAE encode reference images
        - Add reference_latents to conditioning
        - Apply FluxGuidance
        
        Args:
            clip: CLIP model
            vae: VAE for encoding reference images
            prompt: Text prompt
            reference_images: List of reference images
            flux_guidance: FLUX guidance scale
        
        Returns:
            Tuple of (positive_conditioning, negative_conditioning)
        """
        import node_helpers
        
        ref_latents = []
        
        for image in reference_images:
            if image is not None and vae is not None:
                # VAE encode the reference image
                samples = image.movedim(-1, 1)
                ref_latents.append(vae.encode(samples.movedim(1, -1)[:, :, :, :3]))
        
        # Encode positive conditioning with FLUX guidance
        tokens = clip.tokenize(prompt)
        positive = clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
        
        if len(ref_latents) > 0:
            positive = node_helpers.conditioning_set_values(positive, {"reference_latents": ref_latents}, append=True)
        
        # Encode negative conditioning
        neg_tokens = clip.tokenize("")
        negative = clip.encode_from_tokens_scheduled(neg_tokens, add_dict={"guidance": flux_guidance})
        
        return positive, negative
    
    def _prepare_wan_i2v(self, vae, positive, negative, width: int, height: int, num_frames: int,
                         start_frame: Optional[torch.Tensor] = None, 
                         end_frame: Optional[torch.Tensor] = None,
                         clip_vision_start=None, clip_vision_end=None) -> Tuple[Any, Any, Dict]:
        """
        Prepare conditioning and latent for WAN Image-to-Video (I2V) or First-Last-Frame-to-Video (FLF2V).
        
        Based on WanImageToVideo and WanFirstLastFrameToVideo from ComfyUI:
        - Creates video latent with proper shape
        - Encodes start/end frames and creates concat_latent_image and concat_mask
        - Applies CLIP vision outputs if provided
        
        Args:
            vae: VAE for encoding frames
            positive: Positive conditioning
            negative: Negative conditioning
            width: Video width
            height: Video height
            num_frames: Number of video frames
            start_frame: Optional start frame image
            end_frame: Optional end frame image (for FLF2V)
            clip_vision_start: Optional CLIP vision output for start frame
            clip_vision_end: Optional CLIP vision output for end frame
        
        Returns:
            Tuple of (positive_cond, negative_cond, latent_dict)
        """
        import node_helpers
        import comfy.clip_vision
        
        batch_size = 1
        spacial_scale = 8  # Standard VAE compression
        latent_frames = ((num_frames - 1) // 4) + 1
        
        # Create empty video latent
        latent = torch.zeros(
            [batch_size, 16, latent_frames, height // spacial_scale, width // spacial_scale],
            device=comfy.model_management.intermediate_device()
        )
        
        if start_frame is not None or end_frame is not None:
            # Prepare frames and mask
            if start_frame is not None:
                start_frame = comfy.utils.common_upscale(
                    start_frame[:num_frames].movedim(-1, 1), width, height, "bilinear", "center"
                ).movedim(1, -1)
            if end_frame is not None:
                end_frame = comfy.utils.common_upscale(
                    end_frame[-num_frames:].movedim(-1, 1), width, height, "bilinear", "center"
                ).movedim(1, -1)
            
            # Create image sequence and mask
            image = torch.ones((num_frames, height, width, 3)) * 0.5
            mask = torch.ones((1, 1, latent_frames * 4, latent.shape[-2], latent.shape[-1]))
            
            if start_frame is not None:
                image[:start_frame.shape[0]] = start_frame
                mask[:, :, :start_frame.shape[0] + 3] = 0.0
            
            if end_frame is not None:
                image[-end_frame.shape[0]:] = end_frame
                mask[:, :, -end_frame.shape[0]:] = 0.0
            
            # Encode to latent
            concat_latent_image = vae.encode(image[:, :, :, :3])
            mask = mask.view(1, mask.shape[2] // 4, 4, mask.shape[3], mask.shape[4]).transpose(1, 2)
            
            positive = node_helpers.conditioning_set_values(positive, {"concat_latent_image": concat_latent_image, "concat_mask": mask})
            negative = node_helpers.conditioning_set_values(negative, {"concat_latent_image": concat_latent_image, "concat_mask": mask})
        
        # Handle CLIP vision outputs
        clip_vision_output = None
        if clip_vision_start is not None:
            clip_vision_output = clip_vision_start
        
        if clip_vision_end is not None:
            if clip_vision_output is not None:
                # Combine start and end CLIP vision outputs
                states = torch.cat([clip_vision_output.penultimate_hidden_states, clip_vision_end.penultimate_hidden_states], dim=-2)
                clip_vision_output = comfy.clip_vision.Output()
                clip_vision_output.penultimate_hidden_states = states
            else:
                clip_vision_output = clip_vision_end
        
        if clip_vision_output is not None:
            positive = node_helpers.conditioning_set_values(positive, {"clip_vision_output": clip_vision_output})
            negative = node_helpers.conditioning_set_values(negative, {"clip_vision_output": clip_vision_output})
        
        return positive, negative, {"samples": latent}
    
    def _prepare_hunyuan_i2v(self, vae, positive, width: int, height: int, num_frames: int,
                              start_frame: Optional[torch.Tensor] = None,
                              guidance_type: str = "v1 (concat)") -> Tuple[Any, Dict]:
        """
        Prepare conditioning and latent for Hunyuan Image-to-Video.
        
        Based on HunyuanImageToVideo from ComfyUI:
        - Creates video latent with proper shape
        - Encodes start frame based on guidance_type
        
        Args:
            vae: VAE for encoding frames
            positive: Positive conditioning
            width: Video width
            height: Video height
            num_frames: Number of video frames
            start_frame: Optional start frame image
            guidance_type: One of "v1 (concat)", "v2 (replace)", "custom"
        
        Returns:
            Tuple of (positive_cond, latent_dict)
        """
        import node_helpers
        
        batch_size = 1
        latent_frames = ((num_frames - 1) // 4) + 1
        
        # Create empty video latent
        latent = torch.zeros(
            [batch_size, 16, latent_frames, height // 8, width // 8],
            device=comfy.model_management.intermediate_device()
        )
        out_latent = {}
        
        if start_frame is not None:
            start_frame = comfy.utils.common_upscale(
                start_frame[:num_frames, :, :, :3].movedim(-1, 1), width, height, "bilinear", "center"
            ).movedim(1, -1)
            
            concat_latent_image = vae.encode(start_frame)
            mask = torch.ones(
                (1, 1, latent.shape[2], concat_latent_image.shape[-2], concat_latent_image.shape[-1]),
                device=start_frame.device, dtype=start_frame.dtype
            )
            mask[:, :, :((start_frame.shape[0] - 1) // 4) + 1] = 0.0
            
            if guidance_type == "v1 (concat)":
                cond = {"concat_latent_image": concat_latent_image, "concat_mask": mask}
            elif guidance_type == "v2 (replace)":
                cond = {'guiding_frame_index': 0}
                latent[:, :, :concat_latent_image.shape[2]] = concat_latent_image
                out_latent["noise_mask"] = mask
            elif guidance_type == "custom":
                cond = {"ref_latent": concat_latent_image}
            else:
                cond = {"concat_latent_image": concat_latent_image, "concat_mask": mask}
            
            positive = node_helpers.conditioning_set_values(positive, cond)
        
        out_latent["samples"] = latent
        
        return positive, out_latent
    
    def _unload_current(self, config: Dict = None):
        """Unload all models and free VRAM AND RAM aggressively."""
        # Clear baked resources from model entries to allow GC
        if config:
            model_variations = config.get("model_variations", [])
            for entry in model_variations:
                entry.pop("_baked_clip", None)
                entry.pop("_baked_vae", None)
        
        # CRITICAL: Access ComfyUI's global loaded models list and FULLY unload
        # The standard unload_all_models() only moves to RAM, it doesn't free RAM
        try:
            # First unload from VRAM
            comfy.model_management.unload_all_models()
        except Exception:
            pass
        
        # Now aggressively remove ALL models from the loaded list (including RAM)
        try:
            loaded_models = comfy.model_management.current_loaded_models
            # Pop all models and properly detach them
            while len(loaded_models) > 0:
                loaded_model = loaded_models.pop()
                try:
                    # Detach the model patcher (releases references)
                    if hasattr(loaded_model, 'model') and loaded_model.model is not None:
                        loaded_model.model.detach(unpatch_all=True)
                    # Detach the finalizer
                    if hasattr(loaded_model, 'model_finalizer') and loaded_model.model_finalizer is not None:
                        loaded_model.model_finalizer.detach()
                except Exception:
                    pass
                del loaded_model
        except Exception:
            pass
        
        try:
            comfy.model_management.cleanup_models()
        except Exception:
            pass
        
        try:
            comfy.model_management.soft_empty_cache()
        except Exception:
            pass
        
        # Run GC multiple times to ensure all cycles are collected
        for _ in range(3):
            gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            
            # Additional aggressive cleanup
            try:
                torch.cuda.ipc_collect()
            except Exception:
                pass
    
    def _get_combo_key(self, combo: Dict, config: Dict) -> str:
        """
        Generate a unique key for a combination based on model/VAE/CLIP/LoRA.
        Prompt changes don't change the key (so models stay loaded).
        """
        model_idx = combo.get("model_index", 0)
        vae_name = combo.get("vae_name", "")
        clip_var = combo.get("clip_variation", {})
        
        # CLIP key based on type
        if clip_var.get("type") == "pair":
            clip_key = f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
        else:
            clip_key = clip_var.get("model", "")
        
        # LoRA key from new lora_config structure
        lora_config = combo.get("lora_config", {})
        lora_list = lora_config.get("loras", [])
        lora_key_parts = []
        for lora in lora_list:
            lora_key_parts.append(f"{lora.get('name', '')}:{lora.get('strength', 1.0)}")
            if lora.get("mode") == "HIGH_LOW_PAIR" and lora.get("low_name"):
                lora_key_parts.append(f"{lora.get('low_name', '')}:{lora.get('low_strength', 1.0)}")
        lora_key = "|".join(lora_key_parts)
        
        return f"{model_idx}|{vae_name}|{clip_key}|{lora_key}"
    
    def _apply_loras(self, model, clip, lora_config: Dict, model_type: str):
        """
        Apply LoRAs from the lora_config to model and clip.
        
        Args:
            model: The model patcher to apply LoRAs to
            clip: The CLIP model to apply LoRAs to (can be None)
            lora_config: Dict with "loras" list from LoRA Compare node
            model_type: Model type string for determining HIGH/LOW application
        
        Returns:
            Tuple of (model, model_low, clip) with LoRAs applied
        """
        if not lora_config:
            return model, None, clip
        
        loras = lora_config.get("loras", [])
        if not loras:
            return model, None, clip
        
        model_low = None
        is_wan22 = model_type == "wan22"
        
        for lora in loras:
            lora_path = lora.get("path")
            strength = lora.get("strength", 1.0)
            label = lora.get("label", lora.get("name", ""))
            
            if not lora_path:
                continue
            
            try:
                # Load LoRA
                lora_data = comfy.utils.load_torch_file(lora_path, safe_load=True)
                
                # Apply to model
                model, clip = comfy.sd.load_lora_for_models(
                    model, clip, lora_data, strength, strength
                )
                
                # Handle HIGH_LOW_PAIR mode for WAN 2.2
                if lora.get("mode") == "HIGH_LOW_PAIR" and lora.get("low_path"):
                    low_path = lora.get("low_path")
                    low_strength = lora.get("low_strength", strength)
                    low_label = lora.get("low_label", lora.get("low_name", ""))
                    
                    # Load low LoRA for the low noise model
                    low_lora_data = comfy.utils.load_torch_file(low_path, safe_load=True)
                    
                    # Store low LoRA info for WAN 2.2 two-phase sampling
                    if not hasattr(model, '_low_loras'):
                        model._low_loras = []
                    model._low_loras.append({
                        "data": low_lora_data,
                        "strength": low_strength,
                        "label": low_label
                    })
                    
            except Exception as e:
                print(f"[SamplerCompareAdvanced] ERROR loading LoRA {label}: {e}")
                continue
        
        return model, model_low, clip

    def _get_sampling_config_for_type(self, config: Dict, model_type: str, defaults: Dict, global_config: Dict = None, combo_idx: int = 0) -> Tuple[Dict, str]:
        """
        Get sampling configuration for a specific combination.
        
        Priority (later overrides earlier):
        1. Node defaults (lowest)
        2. Config chain settings (matched by combo_idx, which maps to variation_index-1)
        3. Global config (from sampler's dynamic fields) - highest priority
        
        Args:
            combo_idx: The 0-indexed combination index. Config chains with variation_index=N
                       are stored at key N-1, so combo_idx=0 matches variation_index=1, etc.
        
        Returns:
            Tuple of (sampling_config_dict, resolved_model_type)
            The resolved_model_type is derived from the config chain's config_type if found,
            which allows proper handling of QWEN_EDIT, Z_IMAGE, etc.
        """
        sampling_configs = config.get("sampling_configs", {}) if config else {}
        
        # Map config_type to internal model_type (reverse mapping)
        config_type_to_model_type = {
            "STANDARD": "sd",
            "SDXL": "sdxl",
            "PONY": "sdxl",
            "WAN2.1": "wan21",
            "WAN2.2": "wan22",
            "HUNYUAN_VIDEO": "hunyuan",
            "HUNYUAN_VIDEO_15": "hunyuan15",
            "QWEN": "qwen",
            "QWEN_EDIT": "qwen_edit",
            "FLUX": "flux",
            "FLUX2": "flux2",
            "FLUX_KONTEXT": "flux_kontext",
            "Z_IMAGE": "z_image",  # Z_IMAGE has its own tokenizer, not same as Lumina2
        }
        
        # Start with node defaults
        result = dict(defaults)
        resolved_model_type = model_type  # Start with detected model_type
        
        # Look for matching config by combo_idx (maps to variation_index-1)
        # Config chain with variation_index=1 is stored at key 0, variation_index=2 at key 1, etc.
        if isinstance(sampling_configs, dict) and combo_idx in sampling_configs:
            cfg = sampling_configs[combo_idx]
            chain_config_type = cfg.get("config_type", "STANDARD")
            
            # Override model_type from config chain's config_type
            # This is critical for QWEN_EDIT, Z_IMAGE, FLUX_KONTEXT detection
            if chain_config_type in config_type_to_model_type:
                resolved_model_type = config_type_to_model_type[chain_config_type]
            
            # Chain config overrides defaults
            for key, value in cfg.items():
                if key != "config_type" and value is not None:
                    result[key] = value
        
        # Apply global config values (highest priority - overrides chain)
        if global_config:
            for key, value in global_config.items():
                if value is not None:
                    result[key] = value
        
        return result, resolved_model_type

    def _expand_global_config(self, global_config: Dict) -> Tuple[List[Dict], List[str]]:
        """
        Expand global config multi-value fields into individual configs.
        
        Args:
            global_config: Dict with potential comma-separated string values
        
        Returns:
            Tuple of (list of expanded configs, list of variation labels)
        """
        if not VARIATION_SUPPORT or not global_config:
            return [global_config] if global_config else [{}], [""]
        
        # Import parsers
        from .variation_expander import (
            parse_samplers, parse_schedulers, parse_steps, parse_cfg,
            parse_denoise, parse_numeric_list
        )
        
        # Parse multi-value fields
        parsed = {}
        for key, value in global_config.items():
            if value is None:
                continue
            
            if key == "sampler_name" and isinstance(value, str):
                parsed["sampler_name"] = parse_samplers(value)
            elif key == "scheduler" and isinstance(value, str):
                parsed["scheduler"] = parse_schedulers(value)
            elif key == "steps" and isinstance(value, str):
                parsed["steps"] = parse_steps(value)
            elif key == "cfg" and isinstance(value, str):
                parsed["cfg"] = parse_cfg(value)
            elif key == "denoise" and isinstance(value, str):
                parsed["denoise"] = parse_denoise(value)
            elif key == "seed" and isinstance(value, str):
                # Parse seeds as integers
                parsed["seed"] = parse_numeric_list(value, int, 0, min_val=0)
            else:
                # Non-expandable field, keep as single value
                parsed[key] = [value]
        
        # Find fields with multiple values
        expansion_fields = []
        expansion_values = []
        for key, values in parsed.items():
            if isinstance(values, list) and len(values) > 1:
                expansion_fields.append(key)
                expansion_values.append(values)
        
        # If no multi-value fields, return single config
        if not expansion_fields:
            # Convert parsed lists back to single values
            single_config = {}
            for key, values in parsed.items():
                if isinstance(values, list) and len(values) > 0:
                    single_config[key] = values[0]
                else:
                    single_config[key] = values
            return [single_config], [""]
        
        # Generate cartesian product of all expansions
        import itertools
        expanded_configs = []
        variation_labels = []
        
        # Format helpers
        def format_label(field):
            return {"sampler_name": "S", "scheduler": "Sch", "steps": "st", "cfg": "cfg", "seed": "sd", "denoise": "dn"}.get(field, field)
        def format_value(val):
            if isinstance(val, float):
                return f"{val:.2f}".rstrip('0').rstrip('.')
            return str(val)
        
        for combo_values in itertools.product(*expansion_values):
            # Build config for this combination
            new_config = {}
            label_parts = []
            
            # Copy non-expansion fields
            for key, values in parsed.items():
                if key not in expansion_fields:
                    new_config[key] = values[0] if isinstance(values, list) else values
            
            # Set expansion field values
            for field, value in zip(expansion_fields, combo_values):
                new_config[field] = value
                label_parts.append(f"{format_label(field)}:{format_value(value)}")
            
            expanded_configs.append(new_config)
            variation_labels.append(" | ".join(label_parts))
        
        return expanded_configs, variation_labels

    def _expand_combinations_with_sampling_variations(self, combinations: List[Dict], config: Dict, node_defaults: Dict, global_config: Dict) -> Tuple[List[Dict], int]:
        """
        Expand combinations to include sampling parameter variations.
        
        PRIORITY (highest to lowest):
        1. Global config multi-values (from sampler node) - OVERRIDE everything
        2. Chain config multi-values (from SamplingConfigChain)
        3. Node defaults
        
        If global config has multi-values for a field, chain values for that field are IGNORED.
        
        Args:
            combinations: Original list of model/vae/clip/lora/prompt combos
            config: Full config dict with sampling_configs
            node_defaults: Default sampling parameters
            global_config: Global overrides (may have multi-value strings)
        
        Returns:
            Tuple of (expanded_combinations, total_count)
            Each expanded combo has a "_sampling_override" dict with specific values
        """
        if not VARIATION_SUPPORT:
            return combinations, len(combinations)
        
        sampling_configs = config.get("sampling_configs", {}) if config else {}
        
        # First, expand global config multi-values
        global_expansions, global_labels = self._expand_global_config(global_config)
        
        # Determine which fields are controlled globally (have values)
        global_fields = set()
        for gc in global_expansions:
            global_fields.update(k for k, v in gc.items() if v is not None and k != "seed_control")
        
        expanded_combos = []
        
        # For each global expansion...
        for global_exp, global_label in zip(global_expansions, global_labels):
            # For each original combo...
            for original_combo in combinations:
                combo_idx = original_combo.get("model_index", 0)
                
                # Get chain config for this combo
                chain_cfg = sampling_configs.get(combo_idx, {})
                
                # Expand chain config (but only for non-global fields)
                # First, mask global fields in chain config
                filtered_chain_cfg = {k: v for k, v in chain_cfg.items() if k not in global_fields}
                
                # Expand the filtered chain config
                chain_expansions, chain_labels = expand_sampling_config(filtered_chain_cfg) if filtered_chain_cfg else ([{}], [""])
                
                # For each chain expansion...
                for chain_exp, chain_label in zip(chain_expansions, chain_labels):
                    new_combo = dict(original_combo)
                    
                    # Build final sampling override: chain first, then global (global wins)
                    sampling_override = {}
                    
                    # Copy original chain config (for non-expanded fields like config_type)
                    for k, v in chain_cfg.items():
                        if v is not None and k not in global_fields:
                            sampling_override[k] = v
                    
                    # Apply chain expansion
                    for k, v in chain_exp.items():
                        if v is not None and k not in global_fields:
                            sampling_override[k] = v
                    
                    # Apply global expansion (highest priority)
                    for k, v in global_exp.items():
                        if v is not None:
                            sampling_override[k] = v
                    
                    new_combo["_sampling_override"] = sampling_override
                    
                    # Build combined label
                    label_parts = []
                    if global_label:
                        label_parts.append(f"[G]{global_label}")
                    if chain_label:
                        label_parts.append(chain_label)
                    new_combo["_variation_label"] = " ".join(label_parts)
                    
                    expanded_combos.append(new_combo)
        
        return expanded_combos, len(expanded_combos)

    def sample_all_combinations(
        self,
        config: Dict,
        num_global_fields: int = 0,
        # Global dimension overrides
        global_width: int = 0,
        global_height: int = 0,
        global_num_frames: int = 0,
        **kwargs,  # Captures dynamic global_param_type_N, global_value_*_N fields
    ):
        """
        Sample all combinations with LAZY LOADING.
        Models are loaded on-demand and unloaded when config changes.
        
        Latents are now generated internally based on config chain width/height/num_frames.
        Global overrides can set width/height/num_frames for all variations.
        
        MULTI-VALUE SUPPORT: If sampling configs contain comma-separated values for
        samplers, schedulers, steps, cfg, etc., they are expanded into additional
        combinations automatically.
        """
        from nodes import common_ksampler
        
        combinations = config.get("combinations", []) if config else []
        if not combinations:
            return (torch.zeros(1, 1, 1, 3), config, "No combinations")
        
        # Build global config from dynamic fields
        global_config = self._build_global_config(num_global_fields, kwargs)
        
        # Hardcoded defaults (used only if no config chain provided)
        node_defaults = {
            "seed": 0,
            "steps": 20,
            "cfg": 7.0,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1.0,
            # Model-specific defaults
            "flux_guidance": 3.5,
            "qwen_shift": 1.15,  # QWEN default (from ComfyUI supported_models.py)
            "cfg_norm": True,
            "cfg_norm_multiplier": 0.7,
            "wan_shift": 8.0,
            "wan22_start_step": 0,
            "wan22_end_step": 16,
            "hunyuan_shift": 7.0,
        }
        
        # Expand combinations with sampling config variations
        original_count = len(combinations)
        combinations, expanded_count = self._expand_combinations_with_sampling_variations(
            combinations, config, node_defaults, global_config
        )
        
        # CRITICAL: Sort combinations by model_index to minimize model switching
        # This ensures all variations for model 0 are processed before moving to model 1, etc.
        # Use stable sort to preserve relative order of variations within each model group
        original_indices = {id(c): i for i, c in enumerate(combinations)}
        combinations = sorted(combinations, key=lambda c: (
            c.get("model_index", 0),  # Primary: group by model
            c.get("_sampling_override", {}).get("variation_index", 0),  # Secondary: by chain/variation index
            original_indices.get(id(c), 0)  # Tertiary: preserve original order within group
        ))
        
        all_images = []
        all_labels = []
        
        # Global dimension overrides (0 means use config chain values)
        use_global_width = global_width if global_width > 0 else None
        use_global_height = global_height if global_height > 0 else None
        use_global_num_frames = global_num_frames if global_num_frames > 0 else None
        
        # Log milestone: processing start
        print(f"[SamplerCompareAdvanced] Processing {len(combinations)} combinations")
        
        # Track currently loaded resources for smart unloading
        current_model = None
        current_model_low = None  
        current_vae = None
        current_clip = None
        current_key = None
        current_model_entry = None
        
        # Track cache hits/misses for logging
        cache_hits = 0
        cache_misses = 0
        
        # Initialize progress tracker
        model_variations = config.get("model_variations", [])
        total_models = len(model_variations)
        sampling_configs = config.get("sampling_configs", {})
        chain_indices = set()
        for idx_tmp in range(len(combinations)):
            chain_cfg = sampling_configs.get(combinations[idx_tmp].get("model_index", 0), {})
            chain_indices.add(chain_cfg.get("variation_index", 1))
        total_chains = len(chain_indices) if chain_indices else 1
        
        # Reset and initialize tracker state - force reset since this is a NEW job
        _force_reset_tracker_state()
        update_tracker_state(
            total_combinations=len(combinations),
            completed_combinations=0,
            total_models=total_models,
            total_chains=total_chains,
            status="sampling",
        )
        
        # Add warnings to tracker
        if len(combinations) > WARNING_THRESHOLD:
            add_tracker_warning(f"⚠️ High combination count: {len(combinations)} combinations")
        
        # Seed control: track running seed and control mode
        # Note: seed_control can also come from per-variation config chains,
        # so we check global first, then override per-variation in the loop if needed
        global_seed_control_mode = global_config.get("seed_control", "fixed")
        seed_control_mode = global_seed_control_mode  # Will be updated per-variation if config chain specifies
        initial_seed = global_config.get("seed")
        running_seed = initial_seed  # Will be updated after each combination based on control mode
        
        for idx, combo in enumerate(combinations):
            
            # Get model entry early for progress tracking and cache hash
            model_idx = combo.get("model_index", 0)
            early_model_entry = config.get("model_variations", [])[model_idx] if model_idx < len(config.get("model_variations", [])) else {}
            current_model_name = early_model_entry.get("display_name", early_model_entry.get("name", f"Model {model_idx + 1}"))
            
            # Get chain index for tracking
            base_combo_idx = combo.get("model_index", 0)
            chain_cfg = sampling_configs.get(base_combo_idx, {})
            current_chain_idx = chain_cfg.get("variation_index", 1)
            
            # Get expected steps for timing (from override > chain > default)
            sampling_override = combo.get("_sampling_override", {})
            expected_steps = sampling_override.get("steps") or chain_cfg.get("steps") or node_defaults.get("steps", 20)
            
            # Start timing for this iteration
            start_iteration(idx, expected_steps)
            
            # Update progress tracker
            update_tracker_state(
                completed_combinations=idx,
                current_model=current_model_name,
                current_model_index=model_idx,
                current_chain=current_chain_idx,
                current_label=combo.get("_variation_label", ""),
                status="sampling",
            )
            
            # Update global_config with running seed (for seed control modes)
            if running_seed is not None:
                global_config["seed"] = running_seed
            
            # Get model type early for cache hash
            clip_var = combo.get("clip_variation")
            clip_type_str = clip_var.get("clip_type", "") if clip_var else ""
            clip_type_to_model_type = {
                "flux": "flux", "flux2": "flux2", "flux_kontext": "flux_kontext",
                "wan": "wan21", "wan22": "wan22",
                "hunyuan_video": "hunyuan", "hunyuan_video_15": "hunyuan15",
                "qwen": "qwen", "qwen_edit": "qwen_edit",
                "sdxl": "sdxl", "sd": "sd", "sd3": "sd3",
                "lumina2": "lumina2",
            }
            early_model_type = clip_type_to_model_type.get(clip_type_str, "sd")
            
            # Compute sampling config for cache hash (without loading model)
            # Use the original model_index from combo, not the loop idx (which may be different after expansion)
            early_sampling_cfg, _ = self._get_sampling_config_for_type(config, early_model_type, node_defaults, global_config, base_combo_idx)
            
            # CRITICAL: Apply _sampling_override to early_sampling_cfg for cache hash
            # This ensures expanded variations (different samplers, schedulers, etc.) have different cache keys
            sampling_override = combo.get("_sampling_override", {})
            if sampling_override:
                early_sampling_cfg = dict(early_sampling_cfg)  # Copy to avoid modifying original
                for key, value in sampling_override.items():
                    if value is not None and not key.startswith("_"):
                        early_sampling_cfg[key] = value
            
            # Determine dimensions for cache hash (override takes precedence)
            cache_width = use_global_width if use_global_width else early_sampling_cfg.get("width", 1024)
            cache_height = use_global_height if use_global_height else early_sampling_cfg.get("height", 1024)
            cache_frames = use_global_num_frames if use_global_num_frames else early_sampling_cfg.get("num_frames", 1)
            
            # Also include variation label in cache hash for uniqueness
            variation_label = combo.get("_variation_label", "")
            
            # Generate cache hash for this combination (using dimensions instead of latent shape)
            # Pass model_entry so cache invalidates when model label/name changes
            combo_hash = self._get_combination_hash(combo, early_sampling_cfg, global_config, (cache_width, cache_height, cache_frames), early_model_entry, variation_label)
            
            # Check cache for existing result
            cached = self._get_cached_result(combo_hash)
            if cached is not None:
                image, label, frame_count = cached
                all_images.append(image)
                combo["output_frame_count"] = frame_count
                all_labels.append(label)
                cache_hits += 1
                
                # Update running seed even on cache hit (to stay consistent with control mode)
                if running_seed is not None:
                    if seed_control_mode == "increment":
                        running_seed += 1
                    elif seed_control_mode == "decrement":
                        running_seed = max(0, running_seed - 1)
                    elif seed_control_mode == "randomize":
                        import random
                        running_seed = random.randint(0, 0xffffffffffffffff)
                
                # Complete timing for cache hit
                complete_iteration(idx)
                continue
            
            cache_misses += 1
            
            # Check if we need to reload models (smart unloading)
            new_key = self._get_combo_key(combo, config)
            needs_reload = current_key is None or new_key != current_key
            
            if needs_reload:
                if current_key is not None:
                    # Clear ALL references before unloading to help GC
                    # This includes working_model which holds patched model clones
                    current_model = None
                    current_model_low = None
                    current_vae = None
                    current_clip = None
                    working_model = None  # Critical: release patched model clone
                    
                    # Force garbage collection before unload
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    
                    self._unload_current(config)
                
                # Get model entry
                model_idx = combo.get("model_index", 0)
                current_model_entry = config["model_variations"][model_idx]
                
                # LAZY LOAD: Model
                current_model, current_model_low = self._load_model(current_model_entry)
                if current_model is None:
                    print(f"[SamplerCompareAdvanced] ERROR: Failed to load model")
                    continue
                
                # LAZY LOAD: VAE
                vae_name = combo.get("vae_name", "NONE")
                current_vae = self._load_vae(vae_name, config, current_model_entry)
                if current_vae is None:
                    print(f"[SamplerCompareAdvanced] WARNING: No VAE loaded for '{vae_name}'")
                
                # LAZY LOAD: CLIP
                clip_var = combo.get("clip_variation")
                current_clip = self._load_clip(clip_var, config, current_model_entry)
                
                # APPLY LoRAs from combo's lora_config
                lora_config = combo.get("lora_config", {})
                if lora_config and lora_config.get("loras"):
                    # Get model type first for LoRA application
                    clip_type_str = clip_var.get("clip_type", "") if clip_var else ""
                    temp_model_type = clip_type_str if clip_type_str else "sd"
                    current_model, _, current_clip = self._apply_loras(
                        current_model, current_clip, lora_config, temp_model_type
                    )
                
                current_key = new_key
            else:
                model_idx = combo.get("model_index", 0)
            
            # Get model type from clip_variation's clip_type
            clip_var = combo.get("clip_variation")
            clip_type_str = clip_var.get("clip_type", "") if clip_var else ""
            
            clip_type_to_model_type = {
                "flux": "flux", "flux2": "flux2", "flux_kontext": "flux_kontext",
                "wan": "wan21", "wan22": "wan22",
                "hunyuan_video": "hunyuan", "hunyuan_video_15": "hunyuan15",
                "qwen": "qwen", "qwen_edit": "qwen_edit",
                "sdxl": "sdxl", "sd": "sd", "sd3": "sd3",
                "lumina2": "lumina2",
            }
            
            if clip_type_str and clip_type_str in clip_type_to_model_type:
                model_type = clip_type_to_model_type[clip_type_str]
            else:
                model_type = self.detect_model_type(current_model)
            
            # Prepare latent based on model type
            is_video_model = model_type in ['hunyuan', 'hunyuan15', 'wan21', 'wan22']
            
            # Get sampling config for this model variation
            # Priority: _sampling_override (from expansion) > global_config (from sampler) > config chain > node_defaults
            # Also get the resolved model_type from config chain (overrides clip_type detection)
            # Use model_index to match config chain (not loop idx, which could be different after expansion)
            base_model_idx = combo.get("model_index", 0)
            sampling_cfg, resolved_model_type = self._get_sampling_config_for_type(config, model_type, node_defaults, global_config, base_model_idx)
            
            # Apply sampling override from expanded variations (highest priority for expanded fields)
            sampling_override = combo.get("_sampling_override")
            if sampling_override:
                for key, value in sampling_override.items():
                    if value is not None and not key.startswith("_"):
                        sampling_cfg[key] = value
            
            # Use resolved model_type from config chain (handles QWEN_EDIT, Z_IMAGE, FLUX_KONTEXT properly)
            if resolved_model_type != model_type:
                model_type = resolved_model_type
                is_video_model = model_type in ['hunyuan', 'hunyuan15', 'wan21', 'wan22']
            
            # Get dimensions from config chain or use global overrides
            latent_width = use_global_width if use_global_width else sampling_cfg.get("width", 1024)
            latent_height = use_global_height if use_global_height else sampling_cfg.get("height", 1024)
            num_frames = use_global_num_frames if use_global_num_frames else sampling_cfg.get("num_frames", 81)
            
            # For QWEN_EDIT and FLUX_KONTEXT with reference images, derive latent dimensions from first reference
            # This matches ComfyUI's TextEncodeQwenImageEdit behavior (scale to ~1024x1024 total pixels)
            reference_images = sampling_cfg.get("reference_images", [])
            if model_type in ['qwen_edit', 'flux_kontext'] and reference_images and not use_global_width and not use_global_height:
                import math
                ref_img = reference_images[0]
                # ref_img shape is [B, H, W, C]
                ref_h, ref_w = ref_img.shape[1], ref_img.shape[2]
                total = int(1024 * 1024)  # Target ~1024x1024 total pixels
                scale_by = math.sqrt(total / (ref_w * ref_h))
                latent_width = round(ref_w * scale_by / 8.0) * 8
                latent_height = round(ref_h * scale_by / 8.0) * 8
            
            # For non-video models, ensure num_frames is 1
            if not is_video_model:
                num_frames = 1
            
            # Get I2V frames from sampling config if available
            start_frame = sampling_cfg.get("start_frame")
            end_frame = sampling_cfg.get("end_frame")
            clip_vision = sampling_cfg.get("clip_vision")
            
            # Create appropriate latent for this model type
            current_latent = self._create_latent_for_type(model_type, latent_width, latent_height, num_frames)
            
            # Extract sampling parameters (already merged by _get_sampling_config_for_type)
            # Seed control can come from config chain or global config
            # Per-variation seed_control takes priority over global
            variation_seed_control = sampling_cfg.get("seed_control")
            if variation_seed_control and variation_seed_control != global_seed_control_mode:
                seed_control_mode = variation_seed_control
            else:
                seed_control_mode = global_seed_control_mode  # Reset to global default
            
            use_seed = sampling_cfg.get("seed", 0)
            
            use_steps = sampling_cfg.get("steps", 20)
            use_cfg = sampling_cfg.get("cfg", 7.0)
            use_sampler = sampling_cfg.get("sampler_name", "euler")
            use_scheduler = sampling_cfg.get("scheduler", "normal")
            use_denoise = sampling_cfg.get("denoise", 1.0)
            
            # Model-specific parameters (from config chain or defaults)
            use_flux_guidance = sampling_cfg.get("flux_guidance", 3.5)
            use_qwen_shift = sampling_cfg.get("qwen_shift", 1.15)  # QWEN default (from ComfyUI supported_models.py)
            use_cfg_norm = sampling_cfg.get("qwen_cfg_norm", True)  # Fixed: correct key name from config chain
            use_cfg_norm_mult = sampling_cfg.get("qwen_cfg_norm_multiplier", 0.7)  # Fixed: correct key name from config chain
            use_wan_shift = sampling_cfg.get("wan_shift", 8.0)
            use_wan22_shift = sampling_cfg.get("wan22_shift", 8.0)  # Added: WAN 2.2 shift
            # WAN 2.2 step ranges: high=0-high_end, low=high_end-low_end
            use_wan22_high_end = sampling_cfg.get("wan22_high_end", 10)
            use_wan22_low_end = sampling_cfg.get("wan22_low_end", 20)
            use_hunyuan_shift = sampling_cfg.get("hunyuan_shift", 7.0)
            use_lumina_shift = sampling_cfg.get("lumina_shift", 3.0)  # Added: Z_IMAGE/Lumina2 shift
            
            # Clone and patch model
            working_model = current_model
            if hasattr(working_model, 'clone'):
                working_model = working_model.clone()
            
            working_model = self._apply_model_patches(
                working_model, model_type,
                qwen_shift=use_qwen_shift, 
                wan_shift=use_wan_shift, 
                wan22_shift=use_wan22_shift,
                hunyuan_shift=use_hunyuan_shift,
                lumina_shift=use_lumina_shift,
                cfg_norm=use_cfg_norm, 
                cfg_norm_multiplier=use_cfg_norm_mult,
                latent_width=latent_width, 
                latent_height=latent_height
            )
            
            # Encode conditioning with CLIP
            current_positive = [[torch.zeros((1, 77, 768)), {}]]
            current_negative = [[torch.zeros((1, 77, 768)), {}]]
            
            if current_clip:
                pos_text = combo.get("prompt_positive", "")
                neg_text = combo.get("prompt_negative", "")
                
                # Get reference images from sampling config if available
                reference_images = sampling_cfg.get("reference_images", [])
                
                try:
                    # Different tokenization for different model types
                    if model_type == 'qwen_edit':
                        # QWEN Edit - use reference images if provided, otherwise empty latent mode
                        if reference_images:
                            # With reference images: use special encoding with reference latents
                            current_positive, current_negative = self._encode_qwen_edit_conditioning(
                                current_clip, current_vae, pos_text, reference_images
                            )
                        else:
                            # Without reference images: standard QWEN encoding (empty latent mode)
                            # This matches ComfyUI's TextEncodeQwenImageEdit with image=None
                            tokens = current_clip.tokenize(pos_text, images=[])
                            current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                            tokens = current_clip.tokenize("", images=[])
                            current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                    elif model_type in ['flux2', 'flux_kontext']:
                        # FLUX2/FLUX_KONTEXT with reference images
                        if reference_images:
                            current_positive, current_negative = self._encode_flux_reference_conditioning(
                                current_clip, current_vae, pos_text, reference_images, use_flux_guidance
                            )
                        else:
                            # Standard FLUX encoding
                            tokens = current_clip.tokenize(pos_text)
                            current_positive = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": use_flux_guidance})
                            tokens = current_clip.tokenize(neg_text)
                            current_negative = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": use_flux_guidance})
                    elif model_type == 'flux':
                        # FLUX uses guidance in encode
                        tokens = current_clip.tokenize(pos_text)
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": use_flux_guidance})
                        tokens = current_clip.tokenize(neg_text)
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": use_flux_guidance})
                    elif model_type == 'qwen':
                        # QWEN needs images=[] for text-only mode and uses special template
                        tokens = current_clip.tokenize(pos_text, images=[])
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                        # QWEN typically doesn't use negative prompts in the same way
                        # But we'll encode it anyway for compatibility
                        if neg_text:
                            tokens = current_clip.tokenize(neg_text, images=[])
                            current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                        else:
                            # Use empty conditioning for negative
                            tokens = current_clip.tokenize("", images=[])
                            current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                    elif model_type == 'z_image':
                        # Z_IMAGE uses ZImageTokenizer which applies its own llama template internally:
                        # "<|im_start|>user\n{text}<|im_end|>\n<|im_start|>assistant\n"
                        # Just pass the text directly - tokenizer handles formatting
                        tokens = current_clip.tokenize(pos_text)
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                        tokens = current_clip.tokenize(neg_text if neg_text else "")
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                    elif model_type == 'lumina2':
                        # Lumina2 (NOT Z_IMAGE) uses special system prompt format
                        # Based on CLIPTextEncodeLumina2 from ComfyUI
                        system_prompt = "You are an assistant designed to generate superior images with the superior degree of image-text alignment based on textual prompts or user prompts."
                        full_prompt = f'{system_prompt} <Prompt Start> {pos_text}'
                        tokens = current_clip.tokenize(full_prompt)
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                        # Negative can be empty or with system prompt
                        if neg_text:
                            full_neg = f'{system_prompt} <Prompt Start> {neg_text}'
                            tokens = current_clip.tokenize(full_neg)
                        else:
                            tokens = current_clip.tokenize("")
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                    else:
                        # Standard tokenization for other models
                        tokens = current_clip.tokenize(pos_text)
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                        tokens = current_clip.tokenize(neg_text)
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                except Exception as e:
                    print(f"[SamplerCompareAdvanced] Conditioning error: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Apply I2V conditioning for video models with start_frame
            if is_video_model and start_frame is not None and current_vae is not None:
                if model_type in ['wan21', 'wan22']:
                    # WAN I2V or FLF2V
                    current_positive, current_negative, current_latent = self._prepare_wan_i2v(
                        current_vae, current_positive, current_negative,
                        latent_width, latent_height, num_frames,
                        start_frame=start_frame, end_frame=end_frame
                    )
                elif model_type in ['hunyuan', 'hunyuan15']:
                    # Hunyuan I2V - use v1 (concat) by default
                    current_positive, current_latent = self._prepare_hunyuan_i2v(
                        current_vae, current_positive,
                        latent_width, latent_height, num_frames,
                        start_frame=start_frame
                    )
            
            # Apply LoRAs (legacy path for old combo structure)
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", ())
            if lora_names:
                working_model = self._apply_loras_legacy(working_model, lora_names, lora_strengths)
            
            # Sample based on model type (using config chain settings)
            try:
                if model_type == 'wan22':
                    # WAN 2.2 two-phase sampling (use current_model_low from lazy loading)
                    # WAN 2.2 uses shift=8.0 (same as WAN 2.1) from config chain
                    wan22_shift = sampling_cfg.get("wan22_shift", 8.0)
                    sampled_latent = self._sample_wan22(
                        working_model, current_model_low,
                        use_seed, use_steps, use_cfg, use_sampler, use_scheduler,
                        current_positive, current_negative, current_latent,
                        use_denoise, use_wan22_high_end, use_wan22_low_end, wan_shift=wan22_shift
                    )
                else:
                    # Standard sampling for all other models
                    (latent_out,) = common_ksampler(
                        model=working_model,
                        seed=use_seed,
                        steps=use_steps,
                        cfg=use_cfg,
                        sampler_name=use_sampler,
                        scheduler=use_scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent=current_latent,
                        denoise=use_denoise
                    )
                    sampled_latent = latent_out
                
                # Decode
                if current_vae is None:
                    print(f"[SamplerCompareAdvanced] ERROR: No VAE loaded for decoding")
                    continue
                image = self._decode_latent(sampled_latent, current_vae, is_video=is_video_model, num_frames=num_frames)
                
                all_images.append(image)
                
                # Store actual frame count and dimensions for this combination
                actual_frame_count = image.shape[0]
                combo["output_frame_count"] = actual_frame_count
                combo["output_width"] = image.shape[2]  # W dimension
                combo["output_height"] = image.shape[1]  # H dimension
            
            except comfy.model_management.InterruptProcessingException:
                # Re-raise interrupt so job can be properly cancelled
                current_model = None
                current_model_low = None
                current_vae = None
                current_clip = None
                working_model = None
                self._unload_current(config)
                raise
                
            except Exception as e:
                print(f"[SamplerCompareAdvanced] ERROR: Sampling failed: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Generate label (use user's custom label without model_type suffix)
            label = current_model_entry.get("display_name", current_model_entry.get("name", f"Model {model_idx}"))
            
            # Append variation label if this is an expanded combo
            variation_label = combo.get("_variation_label", "")
            if variation_label:
                label = f"{label} | {variation_label}"
            
            all_labels.append(label)
            
            # Cache the result for future runs
            # Use all_images[-1] since we just appended
            if all_images:
                actual_frame_count = combo.get("output_frame_count", 1)
                self._cache_result(combo_hash, all_images[-1], label, actual_frame_count)
            
            # Mark iteration complete for timing stats
            complete_iteration(idx)
            
            # Update running seed based on control mode (for next iteration)
            if running_seed is not None:
                if seed_control_mode == "increment":
                    running_seed += 1
                elif seed_control_mode == "decrement":
                    running_seed = max(0, running_seed - 1)
                elif seed_control_mode == "randomize":
                    import random
                    running_seed = random.randint(0, 0xffffffffffffffff)
                # "fixed" mode: running_seed stays the same
            
            # Per-iteration cleanup - clear intermediate tensors to help GC
            # Note: 'image' is moved to CPU and stored in all_images, 
            # but clear local refs to GPU tensors
            if 'sampled_latent' in dir():
                del sampled_latent
            if 'current_latent' in dir():
                del current_latent
            if 'current_positive' in dir():
                del current_positive
            if 'current_negative' in dir():
                del current_negative
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        
        # Update tracker to complete status
        update_tracker_state(
            completed_combinations=len(combinations),
            status="complete",
        )
        
        # Final cleanup - clear all references and unload
        current_model = None
        current_model_low = None
        current_vae = None
        current_clip = None
        working_model = None
        self._unload_current(config)
        
        # Combine images
        if not all_images:
            return (torch.zeros(1, 1, 1, 3), config, "No images")
        
        # Check if all images have the same dimensions
        shapes = [(img.shape[1], img.shape[2]) for img in all_images]
        all_same_size = all(s == shapes[0] for s in shapes)
        
        if all_same_size:
            # All same size - can concatenate directly
            images_tensor = torch.cat(all_images, dim=0)
        else:
            # Different sizes - pad to largest dimensions instead of resizing
            # This preserves the original resolution of each image
            max_h = max(img.shape[1] for img in all_images)
            max_w = max(img.shape[2] for img in all_images)
            
            padded_images = []
            for img in all_images:
                h, w = img.shape[1], img.shape[2]
                if h == max_h and w == max_w:
                    padded_images.append(img)
                else:
                    # Pad with white (1.0) to max dimensions
                    # img shape is [B, H, W, C]
                    padded = torch.ones((img.shape[0], max_h, max_w, img.shape[3]), dtype=img.dtype, device=img.device)
                    # Center the original image in the padded tensor
                    y_offset = (max_h - h) // 2
                    x_offset = (max_w - w) // 2
                    padded[:, y_offset:y_offset+h, x_offset:x_offset+w, :] = img
                    padded_images.append(padded)
            
            images_tensor = torch.cat(padded_images, dim=0)
        
        labels_str = "\n".join(all_labels)
        
        # CRITICAL: Update config with expanded combinations so GridCompare can access _sampling_override
        # This allows the grid to properly detect varying dimensions
        config = dict(config) if config else {}
        config["combinations"] = combinations  # Now includes _sampling_override for each combo
        
        return (images_tensor, config, labels_str)
    
    def _apply_model_patches(self, model, model_type: str, **kwargs):
        """Apply model-specific patches based on detected type."""
        
        if model_type == 'qwen':
            # QWEN uses shift=1.15 by default (NOT 8.0!)
            # From comfy/supported_models.py: sampling_settings = {"multiplier": 1.0, "shift": 1.15}
            shift = kwargs.get('qwen_shift', 1.15)
            model = ModelSamplingAuraFlow().patch_aura(model, shift)[0]
            
            # Apply CFG normalization
            if kwargs.get('cfg_norm', True):
                mult = kwargs.get('cfg_norm_multiplier', 0.7)
                model = RescaleCFG().patch(model, mult)[0]
        
        elif model_type == 'qwen_edit':
            # QWEN Edit uses same AuraFlow sampling as QWEN
            shift = kwargs.get('qwen_shift', 1.15)
            model = ModelSamplingAuraFlow().patch_aura(model, shift)[0]
            
            # Apply CFG normalization
            if kwargs.get('cfg_norm', True):
                mult = kwargs.get('cfg_norm_multiplier', 0.7)
                model = RescaleCFG().patch(model, mult)[0]
        
        elif model_type == 'lumina2':
            # Lumina2 uses AuraFlow sampling with shift parameter
            # Default shift=6.0 for Lumina2
            shift = kwargs.get('lumina_shift', 6.0)
            model = ModelSamplingAuraFlow().patch_aura(model, shift)[0]
        
        elif model_type == 'z_image':
            # Z_IMAGE uses AuraFlow sampling with shift parameter
            # Default shift=3.0 for Z_IMAGE (different from Lumina2's 6.0)
            # NO CFG normalization (unlike QWEN)
            # CRITICAL: Use patch_aura() which sets multiplier=1.0 (not patch() which defaults to 1000)
            shift = kwargs.get('lumina_shift', 3.0)
            model = ModelSamplingAuraFlow().patch_aura(model, shift)[0]
        
        elif model_type == 'wan21':
            shift = kwargs.get('wan_shift', 8.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
        
        elif model_type == 'wan22':
            # WAN 2.2 uses shift=8.0 (same as WAN 2.1)
            # This is applied to BOTH high and low noise models
            shift = kwargs.get('wan22_shift', 8.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
        
        elif model_type in ['hunyuan', 'hunyuan15']:
            shift = kwargs.get('hunyuan_shift', 7.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
        
        elif model_type in ['flux', 'flux2', 'flux_kontext']:
            # FLUX, FLUX2, FLUX_KONTEXT models get shift patching
            # FLUX_KONTEXT uses same shift as FLUX2 (shift=2.02 base)
            latent_width = kwargs.get('latent_width', 1024)
            latent_height = kwargs.get('latent_height', 1024)
            model = ModelSamplingFlux().patch(model, max_shift=1.15, base_shift=0.5, 
                                              width=latent_width, height=latent_height)[0]
        
        return model
    
    def _sample_wan22(self, model_high, model_low, seed, steps, cfg, sampler_name, scheduler,
                      positive, negative, latent, denoise, high_end_step, low_end_step, wan_shift=8.0):
        """WAN 2.2 two-phase sampling.
        
        Based on reference workflow:
        - Phase 1 (High Noise): add_noise=enable, return_with_leftover_noise=enable
        - Phase 2 (Low Noise): add_noise=disable, return_with_leftover_noise=disable
        - Split point is controlled by high_end_step (where phase 1 ends / phase 2 starts)
        - Shift = 8.0 for BOTH models (same as WAN 2.1)
        
        Args:
            high_end_step: Step where high noise phase ends (e.g., 12 for "high=0-12")
            low_end_step: Step where low noise phase ends (e.g., 20 for "low=12-20")
        
        IMPORTANT: HIGH and LOW LoRAs must be applied to their respective models.
        The HIGH LoRA is already applied to model_high by _apply_loras().
        The LOW LoRA data is stored in model_high._low_loras and applied here.
        """
        from nodes import common_ksampler
        from comfy_extras.nodes_model_advanced import ModelSamplingSD3
        
        # Use config chain settings for step split
        # high_end_step is where phase 1 ends (and phase 2 starts)
        # low_end_step is where phase 2 ends (typically = steps)
        # If high_end_step is 0 or not set, default to 50% split
        if high_end_step <= 0:
            high_end_step = steps // 2
        if low_end_step <= 0:
            low_end_step = steps
        
        # Phase 1: High noise model (already has HIGH LoRA applied)
        # add_noise=enable -> disable_noise=False
        # return_with_leftover_noise=enable -> force_full_denoise=False
        samples_1 = common_ksampler(
            model=model_high, seed=seed, steps=low_end_step, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            positive=positive, negative=negative, latent=latent,
            denoise=denoise,
            disable_noise=False,
            start_step=0,
            last_step=high_end_step,
            force_full_denoise=False
        )[0]
        
        if model_low is None:
            return samples_1
        
        # Clone low model before patching
        if hasattr(model_low, 'clone'):
            model_low_working = model_low.clone()
        else:
            model_low_working = model_low
        
        # Apply LOW LoRAs to the low noise model (stored in model_high._low_loras)
        if hasattr(model_high, '_low_loras') and model_high._low_loras:
            for low_lora in model_high._low_loras:
                lora_data = low_lora["data"]
                strength = low_lora["strength"]
                model_low_working, _ = comfy.sd.load_lora_for_models(
                    model_low_working, None, lora_data, strength, strength
                )
        
        # Apply shift to low noise model (same as high noise model)
        model_low_patched = ModelSamplingSD3().patch(model_low_working, wan_shift)[0]
        
        # Phase 2: Low noise model
        # add_noise=disable -> disable_noise=True
        # return_with_leftover_noise=disable -> force_full_denoise=True
        samples_2 = common_ksampler(
            model=model_low_patched, seed=seed, steps=low_end_step, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            positive=positive, negative=negative, latent=samples_1,
            denoise=denoise,
            disable_noise=True,
            start_step=high_end_step,
            last_step=low_end_step,
            force_full_denoise=True
        )[0]
        
        # IMPORTANT: Clean up cloned models to prevent memory leak
        # The clones hold references to the original model's tensors
        del model_low_working
        del model_low_patched
        del samples_1
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        
        return samples_2
    
    @staticmethod
    def _apply_loras_legacy(model, lora_names: List[str], strengths: Tuple[float, ...]):
        """Apply LoRAs to the model (legacy method for old combo structure)."""
        working_model = model
        for lora_name, strength in zip(lora_names, strengths):
            if strength == 0.0:
                continue
            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
            lora_data = comfy.utils.load_torch_file(lora_path, safe_load=True)
            working_model, _ = comfy.sd.load_lora_for_models(working_model, None, lora_data, strength, strength)
        return working_model
    
    @staticmethod
    def _decode_latent(latent_dict, vae, is_video=False, num_frames=1):
        """Decode latent samples to image using VAE.
        
        For video models, returns all frames as [F, H, W, C] tensor.
        For image models, returns [B, H, W, C] tensor.
        """
        samples = latent_dict["samples"] if isinstance(latent_dict, dict) else latent_dict
        image = vae.decode(samples)
        
        # Handle 5D video output
        # Common shapes after VAE decode:
        # - [B, F, H, W, C] where C=3 (most common for video VAEs)
        # - [B, C, F, H, W] where C=3 (less common)
        if image.dim() == 5:
            # Check if last dimension is channels (C=3)
            if image.shape[-1] == 3:  # [B, F, H, W, C]
                if is_video:
                    # Video model - squeeze batch and return [F, H, W, C]
                    image = image.squeeze(0)
                else:
                    # Image model - take first frame
                    image = image[:, 0, :, :, :]  # [B, H, W, C]
            elif image.shape[1] == 3:  # [B, C, F, H, W]
                # Permute to [B, F, H, W, C] first
                image = image.permute(0, 2, 3, 4, 1)
                if is_video:
                    image = image.squeeze(0)  # [F, H, W, C]
                else:
                    image = image[:, 0, :, :, :]  # [B, H, W, C]
            else:
                # Unknown format - try best effort
                image = image.squeeze(0)
        
        return image
    
    @classmethod
    def IS_CHANGED(cls, config, num_global_fields=0, global_width=0, global_height=0, global_num_frames=0, **kwargs):
        """
        Compute a hash to determine if re-execution is needed.
        This prevents unnecessary re-runs when workflow is queued without changes.
        """
        # Hash the config combinations (model paths, not objects)
        combos = config.get("combinations", []) if config else []
        combo_str = str([(c.get("model_index"), c.get("vae_name"), c.get("prompt_positive", "")) for c in combos])
        
        # Hash sampling configs from chain (may be dict or list)
        sampling_configs = config.get("sampling_configs", {}) if config else {}
        if isinstance(sampling_configs, dict):
            sampling_str = str([(sc.get("config_type"), sc.get("steps"), sc.get("cfg"), sc.get("sampler_name"), sc.get("width"), sc.get("height"), sc.get("num_frames")) for sc in sampling_configs.values()])
        else:
            sampling_str = str([(sc.get("config_type"), sc.get("steps"), sc.get("cfg"), sc.get("sampler_name"), sc.get("width"), sc.get("height"), sc.get("num_frames")) for sc in sampling_configs])
        
        # Hash global dimension overrides
        dims_str = f"{global_width}x{global_height}x{global_num_frames}"
        
        # Combine and hash
        hash_input = f"{combo_str}|{sampling_str}|{num_global_fields}|{dims_str}"
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if isinstance(val, (str, int, float, bool)):
                hash_input += f"|{key}:{val}"
        
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompareAdvanced": SamplerCompareAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompareAdvanced": "Sampler Compare Advanced",
}
