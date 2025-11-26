"""
Advanced Model Compare Sampler - Cross-preset comparison with auto-detection.
Supports comparing models across different architectures (FLUX vs QWEN vs WAN vs Hunyuan).
All sampling parameters exposed - auto-detects which to use per model.
"""

import gc
import torch
import folder_paths
import comfy.sd
import comfy.utils
import comfy.sample
import comfy.samplers
import comfy.model_management
from typing import List, Dict, Tuple, Any, Optional
from comfy_extras.nodes_model_advanced import ModelSamplingSD3, ModelSamplingAuraFlow, RescaleCFG, ModelSamplingFlux

class SamplerCompareAdvanced:
    """
    Advanced sampler for cross-model comparison.
    Exposes ALL possible sampling parameters and auto-detects which to use per model.
    Supports: FLUX, FLUX2, QWEN, WAN 2.1/2.2, Hunyuan 1.0/1.5, SDXL, SD
    """
    
    RETURN_TYPES = ("IMAGE", "MODEL_COMPARE_CONFIG", "STRING")
    RETURN_NAMES = ("images", "config", "labels")
    FUNCTION = "sample_all_combinations"
    CATEGORY = "sampling"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "model": ("MODEL",),
                "vae": ("VAE",),
                "positive_cond": ("CONDITIONING",),
                "negative_cond": ("CONDITIONING",),
                "latent": ("LATENT",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
            "optional": {
                # === FLUX Parameters ===
                "flux_guidance": ("FLOAT", {
                    "default": 3.5, "min": 0.0, "max": 100.0, "step": 0.1,
                    "tooltip": "FLUX guidance scale (used for FLUX/FLUX2 models)"
                }),
                
                # === QWEN Parameters ===
                "qwen_shift": ("FLOAT", {
                    "default": 8.0, "min": 0.0, "max": 20.0, "step": 0.1,
                    "tooltip": "QWEN shift parameter for AuraFlow sampling"
                }),
                "cfg_norm": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Enable CFG normalization for QWEN models (RescaleCFG)"
                }),
                "cfg_norm_multiplier": ("FLOAT", {
                    "default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "CFG normalization multiplier (0.7 recommended)"
                }),
                
                # === WAN Parameters ===
                "wan_shift": ("FLOAT", {
                    "default": 8.0, "min": 0.0, "max": 20.0, "step": 0.1,
                    "tooltip": "WAN 2.1 shift parameter"
                }),
                "wan22_start_step": ("INT", {
                    "default": 0, "min": 0, "max": 10000,
                    "tooltip": "WAN 2.2 High noise start step"
                }),
                "wan22_end_step": ("INT", {
                    "default": 16, "min": 0, "max": 10000,
                    "tooltip": "WAN 2.2 High noise end step (Low noise continues from here)"
                }),
                
                # === Hunyuan Parameters ===
                "hunyuan_shift": ("FLOAT", {
                    "default": 7.0, "min": 0.0, "max": 20.0, "step": 0.1,
                    "tooltip": "Hunyuan Video shift parameter"
                }),
                
                # === Video Latent Input ===
                "video_latent": ("LATENT", {
                    "tooltip": "Optional video latent for Hunyuan/WAN video models"
                }),
                
                # === Image-to-Video Inputs ===
                "start_image": ("IMAGE", {
                    "tooltip": "Start frame for WAN Image-to-Video"
                }),
                "end_image": ("IMAGE", {
                    "tooltip": "End frame for WAN First-Last-Frame-to-Video"
                }),
            }
        }

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

    def sample_all_combinations(
        self,
        config: Dict,
        model,
        vae,
        positive_cond,
        negative_cond,
        latent: Dict,
        seed: int,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        denoise: float,
        # Optional parameters
        flux_guidance: float = 3.5,
        qwen_shift: float = 8.0,
        cfg_norm: bool = True,
        cfg_norm_multiplier: float = 0.7,
        wan_shift: float = 8.0,
        wan22_start_step: int = 0,
        wan22_end_step: int = 16,
        hunyuan_shift: float = 7.0,
        video_latent: Optional[Dict] = None,
        start_image: Optional[torch.Tensor] = None,
        end_image: Optional[torch.Tensor] = None,
    ):
        """Sample all combinations with auto-detected model-specific settings."""
        
        from nodes import common_ksampler
        
        combinations = config.get("combinations", [])
        if not combinations:
            return (torch.zeros(1, 1, 1, 3), config, "No combinations")
        
        all_images = []
        all_labels = []
        
        # Get latent info
        latent_image = latent["samples"]
        latent_channels = latent_image.shape[1]
        latent_height = latent_image.shape[2] * 8
        latent_width = latent_image.shape[3] * 8
        
        print(f"\n[SamplerCompareAdvanced] Processing {len(combinations)} combinations")
        print(f"[SamplerCompareAdvanced] Latent shape: {latent_image.shape}")
        
        # Smart offloading tracking
        prev_model_idx = None
        prev_vae_name = None
        prev_clip_key = None
        prev_lora_key = None
        
        def get_combo_key(combo):
            model_idx = combo.get("model_index", 0)
            vae_name = combo.get("vae_name", "")
            clip_var = combo.get("clip_variation", {})
            clip_key = clip_var.get("model", "") if clip_var.get("type") == "single" else f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", ())
            lora_key = str(list(zip(lora_names, lora_strengths)))
            return (model_idx, vae_name, clip_key, lora_key)
        
        for idx, combo in enumerate(combinations):
            print(f"\n[SamplerCompareAdvanced] === Combination {idx + 1}/{len(combinations)} ===")
            
            # Smart offloading
            current_key = get_combo_key(combo)
            prev_key = (prev_model_idx, prev_vae_name, prev_clip_key, prev_lora_key)
            needs_offload = idx == 0 or current_key != prev_key
            
            if needs_offload:
                if idx > 0:
                    print(f"[SamplerCompareAdvanced] Model config changed - offloading")
                comfy.model_management.unload_all_models()
                comfy.model_management.cleanup_models()
                comfy.model_management.soft_empty_cache()
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    free_mem = torch.cuda.mem_get_info()[0] / (1024**3)
                    total_mem = torch.cuda.mem_get_info()[1] / (1024**3)
                    print(f"[SamplerCompareAdvanced] GPU Memory: {free_mem:.2f}GB free / {total_mem:.2f}GB total")
            else:
                print(f"[SamplerCompareAdvanced] Same config - skipping offload")
            
            # Get model entry
            model_idx = combo.get("model_index", 0)
            model_entry = config["model_variations"][model_idx]
            model_obj = model_entry.get("model_obj")
            
            # Get model type from clip_variation's clip_type (most reliable source)
            # Falls back to auto-detection if clip_type not available
            clip_var = combo.get("clip_variation")
            clip_type_str = clip_var.get("clip_type", "") if clip_var else ""
            
            # Map clip_type to model_type
            clip_type_to_model_type = {
                "flux": "flux",
                "flux2": "flux2", 
                "wan": "wan21",
                "wan22": "wan22",
                "hunyuan_video": "hunyuan",
                "hunyuan_video_15": "hunyuan15",
                "qwen": "qwen",
                "sdxl": "sdxl",
                "sd": "sd",
                "sd3": "sd3",
            }
            
            if clip_type_str and clip_type_str in clip_type_to_model_type:
                model_type = clip_type_to_model_type[clip_type_str]
                print(f"[SamplerCompareAdvanced] Model type from clip_type '{clip_type_str}': {model_type}")
            else:
                # Fallback to auto-detection
                model_type = self.detect_model_type(model_obj)
                print(f"[SamplerCompareAdvanced] Auto-detected model type: {model_type}")
            
            # Get VAE
            current_vae = vae
            if model_entry.get("baked_vae"):
                current_vae = model_entry["baked_vae"]
            else:
                vae_name = combo.get("vae_name")
                if vae_name and "vae_map" in config and vae_name in config["vae_map"]:
                    current_vae = config["vae_map"][vae_name]
            
            # Prepare latent based on model type
            current_latent = latent
            is_video_model = model_type in ['hunyuan', 'hunyuan15', 'wan21', 'wan22']
            num_frames = 1  # Default for image models
            
            # FLUX2 needs 128-channel latent with 16x compression
            if model_type == 'flux2' and latent_channels != 128:
                device = comfy.model_management.intermediate_device()
                flux2_latent = torch.zeros(
                    [latent_image.shape[0], 128, latent_image.shape[2] // 2, latent_image.shape[3] // 2],
                    device=device
                )
                current_latent = {"samples": flux2_latent}
                print(f"[SamplerCompareAdvanced] Created FLUX2 latent: {flux2_latent.shape}")
            
            # Video models should use video_latent if provided
            elif is_video_model and video_latent is not None:
                current_latent = video_latent
                video_samples = video_latent.get("samples", video_latent)
                if isinstance(video_samples, torch.Tensor):
                    # Video latents are typically [B, C, T, H, W] or [B, C, H, W] 
                    if video_samples.dim() == 5:
                        num_frames = video_samples.shape[2]  # T dimension
                        print(f"[SamplerCompareAdvanced] Using video latent: {video_samples.shape}, {num_frames} frames")
                    else:
                        print(f"[SamplerCompareAdvanced] Using video latent: {video_samples.shape}")
            elif is_video_model:
                print(f"[SamplerCompareAdvanced] WARNING: Video model detected but no video_latent provided. Using standard latent.")
            
            # Prepare working model
            working_model = model_obj
            if hasattr(working_model, 'clone'):
                working_model = working_model.clone()
            
            # Apply model-specific patches
            working_model = self._apply_model_patches(
                working_model, model_type,
                qwen_shift=qwen_shift,
                wan_shift=wan_shift,
                hunyuan_shift=hunyuan_shift,
                cfg_norm=cfg_norm,
                cfg_norm_multiplier=cfg_norm_multiplier,
                latent_width=latent_width,
                latent_height=latent_height
            )
            
            # Prepare conditioning
            current_positive = positive_cond
            current_negative = negative_cond
            
            clip_var = combo.get("clip_variation")
            if clip_var:
                clip_obj = clip_var.get("clip_obj")
                if clip_obj:
                    pos_text = combo.get("prompt_positive", "")
                    neg_text = combo.get("prompt_negative", "")
                    
                    try:
                        tokens = clip_obj.tokenize(pos_text)
                        if model_type in ['flux', 'flux2']:
                            current_positive = clip_obj.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
                        else:
                            current_positive = clip_obj.encode_from_tokens_scheduled(tokens)
                        
                        tokens = clip_obj.tokenize(neg_text)
                        if model_type in ['flux', 'flux2']:
                            current_negative = clip_obj.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
                        else:
                            current_negative = clip_obj.encode_from_tokens_scheduled(tokens)
                        
                        print(f"[SamplerCompareAdvanced] Encoded conditioning for {model_type}")
                    except Exception as e:
                        print(f"[SamplerCompareAdvanced] Conditioning error: {e}")
            
            # Apply LoRAs
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", ())
            if lora_names:
                working_model = self._apply_loras(working_model, lora_names, lora_strengths)
            
            # Sample based on model type
            try:
                if model_type == 'wan22':
                    # WAN 2.2 two-phase sampling
                    sampled_latent = self._sample_wan22(
                        working_model, model_entry.get("model_low_obj"),
                        seed, steps, cfg, sampler_name, scheduler,
                        current_positive, current_negative, current_latent,
                        denoise, wan22_start_step, wan22_end_step
                    )
                else:
                    # Standard sampling for all other models
                    print(f"[SamplerCompareAdvanced] Standard sampling for {model_type}")
                    (latent_out,) = common_ksampler(
                        model=working_model,
                        seed=seed,
                        steps=steps,
                        cfg=cfg,
                        sampler_name=sampler_name,
                        scheduler=scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent=current_latent,
                        denoise=denoise
                    )
                    sampled_latent = latent_out
                
                # Decode
                print(f"[SamplerCompareAdvanced] Decoding...")
                image = self._decode_latent(sampled_latent, current_vae, is_video=is_video_model, num_frames=num_frames)
                all_images.append(image)
                
                # Log video output info
                if is_video_model and image.shape[0] > 1:
                    print(f"[SamplerCompareAdvanced] Video output: {image.shape[0]} frames")
                
            except Exception as e:
                print(f"[SamplerCompareAdvanced] Sampling error: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Generate label
            label = model_entry.get("display_name", model_entry.get("name", f"Model {model_idx}"))
            all_labels.append(f"{label} ({model_type})")
            print(f"[SamplerCompareAdvanced] Label: {label} ({model_type})")
            
            # Update tracking
            prev_model_idx, prev_vae_name, prev_clip_key, prev_lora_key = current_key
            
            # Smart cleanup
            next_needs_offload = True
            if idx + 1 < len(combinations):
                next_key = get_combo_key(combinations[idx + 1])
                next_needs_offload = next_key != current_key
            
            if next_needs_offload:
                try:
                    del working_model
                    if 'sampled_latent' in locals():
                        del sampled_latent
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    gc.collect()
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception as e:
                    print(f"[SamplerCompareAdvanced] Cleanup warning: {e}")
        
        # Combine images
        if not all_images:
            return (torch.zeros(1, 1, 1, 3), config, "No images")
        
        # Resize if needed
        target_h, target_w = all_images[0].shape[1], all_images[0].shape[2]
        resized_images = []
        for img in all_images:
            if img.shape[1] != target_h or img.shape[2] != target_w:
                img_p = img.permute(0, 3, 1, 2)
                img_r = torch.nn.functional.interpolate(img_p, size=(target_h, target_w), mode='bilinear')
                img = img_r.permute(0, 2, 3, 1)
            resized_images.append(img)
        
        images_tensor = torch.cat(resized_images, dim=0)
        labels_str = "\n".join(all_labels)
        
        return (images_tensor, config, labels_str)
    
    def _apply_model_patches(self, model, model_type: str, **kwargs):
        """Apply model-specific patches based on detected type."""
        
        if model_type == 'qwen':
            # Apply AuraFlow shift
            shift = kwargs.get('qwen_shift', 8.0)
            model = ModelSamplingAuraFlow().patch(model, shift)[0]
            
            # Apply CFG normalization
            if kwargs.get('cfg_norm', True):
                mult = kwargs.get('cfg_norm_multiplier', 0.7)
                model = RescaleCFG().patch(model, mult)[0]
            print(f"[SamplerCompareAdvanced] Applied QWEN patches (shift={shift})")
        
        elif model_type == 'wan21':
            shift = kwargs.get('wan_shift', 8.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
            print(f"[SamplerCompareAdvanced] Applied WAN 2.1 shift={shift}")
        
        elif model_type in ['hunyuan', 'hunyuan15']:
            shift = kwargs.get('hunyuan_shift', 7.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
            print(f"[SamplerCompareAdvanced] Applied Hunyuan shift={shift}")
        
        elif model_type in ['flux', 'flux2']:
            # FLUX models get shift patching
            latent_width = kwargs.get('latent_width', 1024)
            latent_height = kwargs.get('latent_height', 1024)
            model = ModelSamplingFlux().patch(model, max_shift=1.15, base_shift=0.5, 
                                              width=latent_width, height=latent_height)[0]
            print(f"[SamplerCompareAdvanced] Applied FLUX patches")
        
        return model
    
    def _sample_wan22(self, model_high, model_low, seed, steps, cfg, sampler_name, scheduler,
                      positive, negative, latent, denoise, start_step, end_step):
        """WAN 2.2 two-phase sampling."""
        from nodes import common_ksampler
        
        print(f"[SamplerCompareAdvanced] WAN 2.2 Phase 1: steps {start_step}-{end_step}")
        
        # Phase 1: High noise model
        samples_1 = common_ksampler(
            model=model_high, seed=seed, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            positive=positive, negative=negative, latent=latent,
            denoise=denoise, start_step=start_step, end_step=end_step
        )[0]
        
        if model_low is None:
            return samples_1
        
        # Phase 2: Low noise model
        print(f"[SamplerCompareAdvanced] WAN 2.2 Phase 2: steps {end_step}-{steps}")
        samples_2 = common_ksampler(
            model=model_low, seed=seed, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            positive=positive, negative=negative, latent=samples_1,
            denoise=denoise, start_step=end_step, end_step=steps
        )[0]
        
        return samples_2
    
    @staticmethod
    def _apply_loras(model, lora_names: List[str], strengths: Tuple[float, ...]):
        """Apply LoRAs to the model."""
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
        
        # Handle 5D video output [B, F, H, W, C] or [B, C, F, H, W]
        if image.dim() == 5:
            if is_video and num_frames > 1:
                # Video model - return all frames
                # Typical decoded shape is [B, F, H, W, C]
                if image.shape[1] == num_frames:  # [B, F, H, W, C]
                    # Squeeze batch and return [F, H, W, C]
                    image = image.squeeze(0)
                elif image.shape[2] == num_frames:  # Maybe [B, C, F, H, W]?
                    # Permute and squeeze
                    image = image.permute(0, 2, 3, 4, 1).squeeze(0)
                else:
                    # Unknown format, try to preserve frames
                    print(f"[SamplerCompareAdvanced] Warning: Unexpected video shape {image.shape}, attempting best effort")
                    image = image.squeeze(0)
                    if image.dim() == 4:
                        # Assume [F, H, W, C] or similar
                        pass
            else:
                # Image model or single frame - take first frame only
                image = image[:, 0:1, :, :, :]
                image = image.squeeze(1)
        
        return image


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompareAdvanced": SamplerCompareAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompareAdvanced": "Sampler Compare Advanced",
}
