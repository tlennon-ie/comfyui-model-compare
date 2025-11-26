"""
Simple Model Compare Sampler - Works like standard KSampler but handles multiple model comparisons.
Supports FLUX, QWEN, WAN, and Checkpoints.

LAZY LOADING: Models are loaded on-demand per combination to minimize VRAM usage.
"""

import gc
import hashlib
import torch
import folder_paths
import comfy.sd
import comfy.utils
import comfy.sample
import comfy.samplers
import comfy.model_management
from typing import List, Dict, Tuple, Any, Optional
from comfy_extras.nodes_model_advanced import ModelSamplingSD3, ModelSamplingAuraFlow, RescaleCFG, ModelSamplingFlux

class SamplerCompareSimple:
    """
    Simple sampler for model comparison with LAZY LOADING.
    Models are loaded on-demand and unloaded when config changes.
    """
    
    RETURN_TYPES = ("IMAGE", "MODEL_COMPARE_CONFIG", "STRING")
    RETURN_NAMES = ("images", "config", "labels")
    FUNCTION = "sample_all_combinations"
    CATEGORY = "sampling"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        samplers = comfy.samplers.KSampler.SAMPLERS
        schedulers = comfy.samplers.KSampler.SCHEDULERS
        
        sampler_list = list(samplers.keys()) if isinstance(samplers, dict) else list(samplers)
        scheduler_list = list(schedulers.keys()) if isinstance(schedulers, dict) else list(schedulers)
        
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "latent": ("LATENT",),
                "preset": (["STANDARD", "SDXL", "PONY", "WAN2.1", "WAN2.2", "HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "QWEN", "FLUX", "FLUX2"], {
                    "default": "STANDARD",
                    "tooltip": "Sampler preset - controls visibility of specific fields"
                }),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (sampler_list,),
                "scheduler": (scheduler_list,),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                # WAN 2.2 Specific
                "wan_high_start": ("INT", {"default": 0, "min": 0, "max": 1000, "step": 1, "tooltip": "Start step for High Noise model"}),
                "wan_high_end": ("INT", {"default": 15, "min": 0, "max": 1000, "step": 1, "tooltip": "End step for High Noise model"}),
                "wan_low_start": ("INT", {"default": 15, "min": 0, "max": 1000, "step": 1, "tooltip": "Start step for Low Noise model"}),
                "wan_low_end": ("INT", {"default": 30, "min": 0, "max": 1000, "step": 1, "tooltip": "End step for Low Noise model"}),
                # Hunyuan / WAN Shift
                "shift": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1, "tooltip": "Shift for Hunyuan (7.0) or WAN (8.0)"}),
                "shift_low": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.1, "tooltip": "Shift for WAN 2.2 Low Noise model"}),
                # QWEN
                "qwen_shift": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 100.0, "step": 0.1, "tooltip": "Shift for Qwen (ModelSamplingAuraFlow)"}),
                "qwen_cfg_norm": ("FLOAT", {"default": 3.0, "min": 0.0, "max": 100.0, "step": 0.1, "tooltip": "CFG Norm for Qwen"}),
                # Flux
                "flux_guidance": ("FLOAT", {"default": 4.0, "min": 0.0, "max": 100.0, "step": 0.1, "tooltip": "Guidance for Flux/Flux2"}),
            },
            "optional": {
                "video_latent": ("LATENT", {
                    "tooltip": "Optional video latent for video models"
                }),
            }
        }

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
            "wan": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "wan22": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "hunyuan_video": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "hunyuan_video_15": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO_15", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "qwen": getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION),
        }
        key = clip_type_str.upper().replace("_", "")
        if hasattr(comfy.sd.CLIPType, key):
            return getattr(comfy.sd.CLIPType, key)
        return mapping.get(clip_type_str, comfy.sd.CLIPType.STABLE_DIFFUSION)
    
    def _load_model(self, model_entry: Dict) -> Tuple[Any, Any]:
        """Lazy load a model from stored path."""
        model_obj = None
        model_low_obj = None
        
        model_path = model_entry.get("model_path")
        model_type = model_entry.get("model_type")
        
        if not model_path:
            return None, None
        
        print(f"[SamplerCompareSimple] Loading model: {model_path}")
        
        if model_type == "checkpoint":
            out = comfy.sd.load_checkpoint_guess_config(
                model_path, output_vae=True, output_clip=True,
                embedding_directory=folder_paths.get_folder_paths("embeddings")
            )
            model_obj = out[0]
            if model_entry.get("use_baked_vae_clip"):
                model_entry["_baked_clip"] = out[1]
                model_entry["_baked_vae"] = out[2]
        elif model_type == "diffusion":
            model_obj = comfy.sd.load_diffusion_model(model_path, model_options={})
        
        model_low_path = model_entry.get("model_low_path")
        if model_low_path:
            print(f"[SamplerCompareSimple] Loading low noise model: {model_low_path}")
            model_low_obj = comfy.sd.load_diffusion_model(model_low_path, model_options={})
        
        return model_obj, model_low_obj
    
    def _load_vae(self, vae_name: str, config: Dict, model_entry: Dict) -> Any:
        """Lazy load a VAE."""
        if vae_name == "__baked__":
            return model_entry.get("_baked_vae")
        if vae_name == "NONE" or not vae_name:
            return None
        
        vae_paths = config.get("vae_paths", {})
        vae_path = vae_paths.get(vae_name)
        if not vae_path:
            return None
        
        print(f"[SamplerCompareSimple] Loading VAE: {vae_path}")
        return comfy.sd.VAE(sd=comfy.utils.load_torch_file(vae_path))
    
    def _load_clip(self, clip_var: Dict, config: Dict, model_entry: Dict) -> Any:
        """Lazy load a CLIP."""
        if not clip_var:
            return None
        
        clip_type = clip_var.get("type")
        clip_type_str = clip_var.get("clip_type", "sd")
        device = clip_var.get("device", "default")
        
        model_options = {}
        if device == "cpu":
            model_options["load_device"] = torch.device("cpu")
            model_options["offload_device"] = torch.device("cpu")
        
        if clip_type == "baked":
            return model_entry.get("_baked_clip")
        elif clip_type == "pair":
            path_a = clip_var.get("a_path")
            path_b = clip_var.get("b_path")
            if path_a and path_b:
                return comfy.sd.load_clip(
                    ckpt_paths=[path_a, path_b],
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    clip_type=self._get_clip_type_enum(clip_type_str),
                    model_options=model_options
                )
        elif clip_type == "single":
            path = clip_var.get("model_path")
            if path:
                return comfy.sd.load_clip(
                    ckpt_paths=[path],
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    clip_type=self._get_clip_type_enum(clip_type_str),
                    model_options=model_options
                )
        return None
    
    def _unload_current(self):
        """Unload all models and free VRAM."""
        comfy.model_management.unload_all_models()
        comfy.model_management.cleanup_models()
        comfy.model_management.soft_empty_cache()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    
    def _get_combo_key(self, combo: Dict) -> str:
        """Generate unique key for combination based on model/VAE/CLIP/LoRA."""
        model_idx = combo.get("model_index", 0)
        vae_name = combo.get("vae_name", "")
        clip_var = combo.get("clip_variation", {})
        clip_key = clip_var.get("model", "") if clip_var.get("type") == "single" else f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
        lora_names = combo.get("lora_names", [])
        lora_strengths = combo.get("lora_strengths", ())
        lora_key = str(list(zip(lora_names, lora_strengths)))
        return f"{model_idx}|{vae_name}|{clip_key}|{lora_key}"

    def _decode_latent(self, latent_out: Dict, vae) -> torch.Tensor:
        """Decode latent to image using VAE."""
        from nodes import VAEDecode
        vae_decode = VAEDecode()
        (image,) = vae_decode.decode(vae, latent_out)
        return image

    def sample_all_combinations(
        self,
        config: Dict[str, Any],
        latent,
        preset: str,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        seed: int,
        denoise: float,
        wan_high_start: int = 0,
        wan_high_end: int = 15,
        wan_low_start: int = 15,
        wan_low_end: int = 30,
        shift: float = 7.0,
        shift_low: float = 8.0,
        qwen_shift: float = 3.0,
        qwen_cfg_norm: float = 3.0,
        flux_guidance: float = 3.5,
        video_latent: Optional[Dict] = None,
    ) -> Tuple[torch.Tensor, str]:
        """
        Sample each combination with LAZY LOADING.
        """
        from nodes import common_ksampler
        
        combinations = config.get("combinations", [])
        if not combinations:
            raise ValueError("No combinations in config")
        
        all_images = []
        all_labels = []
        
        # Use config preset if available, but sampler preset overrides for logic if needed?
        config_preset = config.get("preset", "STANDARD")
        is_wan_2_2 = config_preset == "WAN2.2"
        
        # Get latent dimensions for FLUX and other models
        latent_image = latent["samples"]
        
        # Determine compression ratio based on latent channels
        # FLUX2: 128 channels, 16x compression
        # FLUX/SD/SDXL: 4 or 16 channels, 8x compression
        latent_channels = latent_image.shape[1] if latent_image.ndim >= 4 else 4
        if latent_channels == 128:
            # FLUX2 latent - uses 16x compression
            compression_ratio = 16
            print(f"[SamplerCompareSimple] Detected FLUX2 latent (128 channels, 16x compression)")
        else:
            # Standard latent - uses 8x compression
            compression_ratio = 8
            print(f"[SamplerCompareSimple] Detected standard latent ({latent_channels} channels, 8x compression)")
        
        # Handle both image latents [B, C, H, W] and video latents [B, C, F, H, W]
        if latent_image.ndim == 4:
            # Image latent: [batch, channels, height, width]
            latent_height = latent_image.shape[2] * compression_ratio
            latent_width = latent_image.shape[3] * compression_ratio
            print(f"[SamplerCompareSimple] Image latent shape: {latent_image.shape}")
        elif latent_image.ndim == 5:
            # Video latent: [batch, channels, frames, height, width]
            latent_height = latent_image.shape[3] * compression_ratio
            latent_width = latent_image.shape[4] * compression_ratio
            print(f"[SamplerCompareSimple] Video latent shape: {latent_image.shape}")
        else:
            # Fallback
            latent_height = latent_image.shape[-2] * compression_ratio
            latent_width = latent_image.shape[-1] * compression_ratio
            print(f"[SamplerCompareSimple] Unknown latent shape: {latent_image.shape}")
        
        print(f"[SamplerCompareSimple] Latent dimensions: {latent_width}x{latent_height}")
        
        # Helper for cleaning names
        def clean_name(name: str) -> str:
            if not name: return "unknown"
            if "[Diffusion]" in name: name = name.replace("[Diffusion]", "").strip()
            if "[Checkpoint]" in name: name = name.replace("[Checkpoint]", "").strip()
            if name.endswith(".safetensors"): name = name[:-12]
            return name

        # Helper to apply patches
        def apply_model_patches(model_obj, preset_name, is_low_noise=False, latent_width=None, latent_height=None):
            patched_model = model_obj
            
            if preset_name in ["HUNYUAN_VIDEO", "HUNYUAN_VIDEO_15", "WAN2.1"]:
                 # Apply ModelSamplingSD3
                 # Hunyuan default 7.0, WAN default 8.0 (passed as shift)
                 patched_model = ModelSamplingSD3().patch(patched_model, shift)[0]
                 
            elif preset_name == "WAN2.2":
                # Apply ModelSamplingSD3 with shift=5.0 for WAN 2.2
                # WAN 2.2 uses shift=5.0 (NOT 8.0 like WAN 2.1!)
                wan22_shift = 5.0
                patched_model = ModelSamplingSD3().patch(patched_model, wan22_shift)[0]
                
            elif preset_name == "QWEN":
                # Apply ModelSamplingAuraFlow and RescaleCFG
                patched_model = ModelSamplingAuraFlow().patch_aura(patched_model, qwen_shift)[0]
                patched_model = RescaleCFG().patch(patched_model, qwen_cfg_norm)[0]
                
            elif preset_name in ["FLUX", "FLUX2"]:
                # Apply ModelSamplingFlux with width and height from latent
                if latent_width is None or latent_height is None:
                    # Fallback to defaults if not provided
                    latent_width = 1024
                    latent_height = 1024
                patched_model = ModelSamplingFlux().patch(patched_model, max_shift=1.15, base_shift=0.5, width=latent_width, height=latent_height)[0]
                
            return patched_model
        
        # Track currently loaded resources for smart unloading
        current_model = None
        current_model_low = None
        current_vae = None
        current_clip = None
        current_key = None
        current_model_entry = None
        
        for idx, combo in enumerate(combinations):
            print(f"\n[SamplerCompareSimple] === Combination {idx + 1}/{len(combinations)} ===")
            
            # Smart offloading: only cleanup when model/VAE/CLIP/LoRA changes
            new_key = self._get_combo_key(combo)
            needs_reload = current_key is None or new_key != current_key
            
            if needs_reload:
                if current_key is not None:
                    print(f"[SamplerCompareSimple] Model config changed - unloading previous models")
                    self._unload_current()
                
                # Get model entry
                model_idx = combo.get("model_index", 0)
                current_model_entry = config["model_variations"][model_idx]
                
                # LAZY LOAD: Model
                current_model, current_model_low = self._load_model(current_model_entry)
                if current_model is None:
                    print(f"[SamplerCompareSimple] ERROR: Failed to load model")
                    continue
                
                # LAZY LOAD: VAE
                vae_name = combo.get("vae_name", "NONE")
                current_vae = self._load_vae(vae_name, config, current_model_entry)
                
                # LAZY LOAD: CLIP
                clip_var = combo.get("clip_variation")
                current_clip = self._load_clip(clip_var, config, current_model_entry)
                
                current_key = new_key
            else:
                print(f"[SamplerCompareSimple] Same model config - reusing loaded models")
                model_idx = combo.get("model_index", 0)
            
            # Determine if this model is FLUX2 (needs different latent sizing)
            is_flux2_model = False
            try:
                latent_format = current_model.get_model_object("latent_format")
                if latent_format and latent_format.latent_channels == 128:
                    is_flux2_model = True
                    print(f"[SamplerCompareSimple] Detected FLUX2 model (128 latent channels)")
            except:
                pass
            
            # Create appropriate latent for this model
            current_latent = latent
            if is_flux2_model and latent_channels != 128:
                device = comfy.model_management.intermediate_device()
                flux2_latent = torch.zeros(
                    [latent_image.shape[0], 128, latent_image.shape[2] // 2, latent_image.shape[3] // 2],
                    device=device
                )
                current_latent = {"samples": flux2_latent}
                print(f"[SamplerCompareSimple] Created FLUX2 latent: {flux2_latent.shape}")
            elif not is_flux2_model and latent_channels == 128:
                device = comfy.model_management.intermediate_device()
                std_latent = torch.zeros(
                    [latent_image.shape[0], 4, latent_image.shape[2] * 2, latent_image.shape[3] * 2],
                    device=device
                )
                current_latent = {"samples": std_latent}
                print(f"[SamplerCompareSimple] Created standard latent: {std_latent.shape}")
            
            # Clone and apply patches
            working_model = current_model
            if hasattr(working_model, 'clone'):
                working_model = working_model.clone()
            
            working_model = apply_model_patches(working_model, preset, latent_width=latent_width, latent_height=latent_height)
            
            # Encode conditioning with CLIP
            current_positive = [[torch.zeros((1, 77, 768)), {}]]
            current_negative = [[torch.zeros((1, 77, 768)), {}]]
            
            clip_var = combo.get("clip_variation")
            if current_clip and clip_var:
                pos_text = combo.get("prompt_positive", "")
                neg_text = combo.get("prompt_negative", "")
                
                try:
                    tokens = current_clip.tokenize(pos_text)
                    if preset in ["FLUX", "FLUX2"]:
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
                    else:
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                    
                    tokens = current_clip.tokenize(neg_text)
                    if preset in ["FLUX", "FLUX2"]:
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
                    else:
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                    
                    prompt_preview = pos_text[:50] if pos_text else "(empty)"
                    print(f"[SamplerCompareSimple] Encoded conditioning (prompt: '{prompt_preview}...')")
                except Exception as e:
                    print(f"[SamplerCompareSimple] Warning: Failed to encode conditioning: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Apply LoRAs
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", ())
            if lora_names:
                working_model = self._apply_loras(working_model, lora_names, lora_strengths)

            # Low Model (WAN 2.2 only) - use lazy loaded model
            working_model_low = None
            if is_wan_2_2 and current_model_low:
                working_model_low = current_model_low
                if hasattr(working_model_low, 'clone'):
                    working_model_low = working_model_low.clone()
                
                # Apply Patches to Low Model
                working_model_low = apply_model_patches(working_model_low, preset, is_low_noise=True, latent_width=latent_width, latent_height=latent_height)
                
                l_names_low = combo.get("lora_names_low", [])
                l_strengths_low = combo.get("lora_strengths_low", ())
                if l_names_low:
                    working_model_low = self._apply_loras(working_model_low, l_names_low, l_strengths_low)

            # 3. Sampling
            
            sampled_latent = None
            
            if is_wan_2_2 and working_model_low:
                # WAN 2.2 2-Stage Sampling
                # Based on reference workflow:
                # - Phase 1 (High Noise): add_noise=enable, return_with_leftover_noise=enable
                # - Phase 2 (Low Noise): add_noise=disable, return_with_leftover_noise=disable
                # - Split at 50% of steps
                # - Shift = 5.0 for BOTH models (NOT 8.0 like WAN 2.1!)
                
                # Calculate 50% split point
                mid_step = steps // 2
                
                print(f"[SamplerCompareSimple] WAN 2.2 Sampling: High (0-{mid_step}) -> Low ({mid_step}-{steps})")
                print(f"  Total steps: {steps}, Denoise: {denoise}")
                print(f"  NOTE: WAN 2.2 requires shift=5.0, make sure your shift is set correctly!")
                
                try:
                    from nodes import KSamplerAdvanced
                    k_sampler = KSamplerAdvanced()
                    
                    # Stage 1: High Noise Model (steps 0 to mid_step)
                    # add_noise=enable, return_with_leftover_noise=enable
                    print(f"  Stage 1: High Noise Model (steps 0 to {mid_step})")
                    samples_1_tuple = k_sampler.sample(
                        model=working_model,
                        add_noise="enable",
                        noise_seed=seed,
                        steps=steps,
                        cfg=cfg,
                        sampler_name=sampler_name,
                        scheduler=scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent_image=current_latent,
                        start_at_step=0,
                        end_at_step=mid_step,
                        return_with_leftover_noise="enable"
                    )
                    samples_1 = samples_1_tuple[0]
                    print(f"  Stage 1 complete: output shape {samples_1['samples'].shape}")
                    
                    # Stage 2: Low Noise Model (steps mid_step to end)
                    # add_noise=disable, return_with_leftover_noise=disable
                    print(f"  Stage 2: Low Noise Model (steps {mid_step} to {steps})")
                    samples_2_tuple = k_sampler.sample(
                        model=working_model_low,
                        add_noise="disable",
                        noise_seed=seed,
                        steps=steps,
                        cfg=cfg,
                        sampler_name=sampler_name,
                        scheduler=scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent_image=samples_1,
                        start_at_step=mid_step,
                        end_at_step=steps,
                        return_with_leftover_noise="disable"
                    )
                    samples_2 = samples_2_tuple[0]
                    print(f"  Stage 2 complete: output shape {samples_2['samples'].shape}")
                    
                    sampled_latent = samples_2

                except Exception as e:
                    print(f"[SamplerCompareSimple] Error in WAN 2.2 sampling: {e}")
                    import traceback
                    traceback.print_exc()
                    # Fallback to standard
                    sampled = common_ksampler(working_model, seed, steps, cfg, sampler_name, scheduler, current_positive, current_negative, current_latent, denoise=denoise)
                    sampled_latent = sampled[0]

            else:
                # Standard Sampling (WAN 2.1, SDXL, etc.)
                print(f"[SamplerCompareSimple] Standard Sampling")
                try:
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
                except Exception as e:
                    print(f"[SamplerCompareSimple] Error in common_ksampler: {e}")
                    continue
            
            # 4. Decode
            print(f"[SamplerCompareSimple] Decoding...")
            if current_vae is None:
                print(f"[SamplerCompareSimple] ERROR: No VAE loaded for decoding")
                continue
            image = self._decode_latent(sampled_latent, current_vae)
            all_images.append(image)
            
            # 5. Labeling
            label_parts = []
            is_grouped = config.get("is_grouped", False)
            
            # Use display_name if available, otherwise fall back to name
            model_display = current_model_entry.get("display_name", current_model_entry["name"])
            
            if is_grouped:
                label_parts.append(clean_name(model_display))
            else:
                if len(config.get("model_variations", [])) > 1:
                    label_parts.append(clean_name(model_display))
                
                if len(config.get("vae_variations", [])) > 1:
                    label_parts.append(clean_name(combo.get("vae_name", "")))
                    
                clip_var = combo.get("clip_variation")
                if len(config.get("clip_variations", [])) > 1 and clip_var:
                    clip_type = clip_var.get("type", "unknown")
                    if clip_type == "pair":
                        label_parts.append(f"{clean_name(clip_var.get('a'))}+{clean_name(clip_var.get('b'))}")
                    else:
                        label_parts.append(clean_name(clip_var.get("model")))
            
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", [])
            if lora_names:
                idx_l = len(lora_names) - 1
                label_parts.append(f"{lora_names[idx_l]}({lora_strengths[idx_l]:.2f})")
            
            prompt_variations = config.get("prompt_variations", [])
            if len(prompt_variations) > 1 and not is_grouped:
                prompt_idx = combo.get("prompt_index", 1)
                label_parts.append(f"P{prompt_idx}")
            
            label = " - ".join(label_parts) if label_parts else f"Combo {idx}"
            all_labels.append(label)
            print(f"[SamplerCompareSimple] Label: {label}")
        
        # Final cleanup
        self._unload_current()
        
        # Concatenate - handle different image sizes by resizing to match first image
        if not all_images:
             # Return dummy if failed
             return (torch.zeros(1, 1, 1, 3), "No Images", config)
        
        # Get target size from first image
        target_h, target_w = all_images[0].shape[1], all_images[0].shape[2]
        
        # Resize any images that don't match (can happen with different VAE architectures)
        resized_images = []
        for i, img in enumerate(all_images):
            h, w = img.shape[1], img.shape[2]
            if h != target_h or w != target_w:
                print(f"[SamplerCompareSimple] Resizing image {i} from {w}x{h} to {target_w}x{target_h}")
                # img is [B, H, W, C], need [B, C, H, W] for interpolate
                img_permuted = img.permute(0, 3, 1, 2)
                img_resized = torch.nn.functional.interpolate(
                    img_permuted, 
                    size=(target_h, target_w), 
                    mode='bilinear', 
                    align_corners=False
                )
                # Back to [B, H, W, C]
                img = img_resized.permute(0, 2, 3, 1)
            resized_images.append(img)
             
        images_tensor = torch.cat(resized_images, dim=0)
        labels_str = "\n".join(all_labels)
        
        return (images_tensor, config, labels_str)
    
    @staticmethod
    def _apply_loras(model, lora_names: List[str], strengths: Tuple[float, ...]):
        """Apply LoRAs to the model."""
        working_model = model
        for lora_name, strength in zip(lora_names, strengths):
            if strength == 0.0: continue
            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
            lora_data = comfy.utils.load_torch_file(lora_path, safe_load=True)
            working_model, _ = comfy.sd.load_lora_for_models(working_model, None, lora_data, strength, strength)
        return working_model

    @classmethod
    def IS_CHANGED(cls, config, latent, preset, steps, cfg, sampler_name, scheduler, seed, denoise, **kwargs):
        """
        Compute a hash to determine if re-execution is needed.
        """
        # Add defensive checks for None
        combos = config.get("combinations", []) if config else []
        combo_str = str([(c.get("model_index"), c.get("vae_name"), c.get("prompt_positive", "")) for c in combos])
        params = f"{preset}|{seed}|{steps}|{cfg}|{sampler_name}|{scheduler}|{denoise}"
        latent_shape = str(latent.get("samples").shape) if isinstance(latent, dict) and latent else "unknown"
        
        hash_input = f"{combo_str}|{params}|{latent_shape}"
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if isinstance(val, (str, int, float, bool)):
                hash_input += f"|{key}:{val}"
        
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompareSimple": SamplerCompareSimple,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompareSimple": "Sampler Compare Simple",
}
