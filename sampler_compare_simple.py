"""
Simple Model Compare Sampler - Works like standard KSampler but handles multiple model comparisons.
Supports FLUX, QWEN, WAN, and Checkpoints.
"""

import torch
import folder_paths
import comfy.sd
import comfy.utils
import comfy.sample
import comfy.samplers
import comfy.model_management
from typing import List, Dict, Tuple, Any
from comfy_extras.nodes_model_advanced import ModelSamplingSD3, ModelSamplingAuraFlow, RescaleCFG, ModelSamplingFlux

class SamplerCompareSimple:
    """
    Simple sampler for model comparison.
    Takes a config with multiple LoRA/Model combinations and samples each one.
    Supports WAN 2.2 High/Low noise sampling.
    """
    
    RETURN_TYPES = ("IMAGE", "STRING", "MODEL_COMPARE_CONFIG")
    RETURN_NAMES = ("images", "labels", "config")
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
                "model": ("MODEL",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent": ("LATENT",),
                "vae": ("VAE",),
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
            "optional": {}
        }

    def sample_all_combinations(
        self,
        config: Dict[str, Any],
        model,
        positive,
        negative,
        latent,
        vae,
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
    ) -> Tuple[torch.Tensor, str]:
        """
        Sample each combination in config.
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
                # Apply ModelSamplingSD3
                # High noise uses 'shift', Low noise uses 'shift_low'
                s = shift_low if is_low_noise else shift
                patched_model = ModelSamplingSD3().patch(patched_model, s)[0]
                
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
        
        for idx, combo in enumerate(combinations):
            print(f"\n[SamplerCompareSimple] === Combination {idx} ===")
            
            # 1. Retrieve Models & VAEs
            model_idx = combo.get("model_index", 0)
            model_entry = config["model_variations"][model_idx]
            
            # Determine which VAE to use
            current_vae = vae # Default to input VAE
            
            if model_entry.get("baked_vae"):
                current_vae = model_entry["baked_vae"]
                print(f"[SamplerCompareSimple] Using Baked VAE from model")
            else:
                vae_name = combo.get("vae_name")
                if vae_name and "vae_map" in config and vae_name in config["vae_map"]:
                    current_vae = config["vae_map"][vae_name]
                    print(f"[SamplerCompareSimple] Using VAE: {vae_name}")
            
            # Determine if this model is FLUX2 (needs different latent sizing)
            # FLUX2 uses 16x compression vs 8x for FLUX/SDXL
            is_flux2_model = False
            model_obj = model_entry.get("model_obj")
            if model_obj:
                try:
                    latent_format = model_obj.get_model_object("latent_format")
                    if latent_format and latent_format.latent_channels == 128:
                        is_flux2_model = True
                        print(f"[SamplerCompareSimple] Detected FLUX2 model (128 latent channels)")
                except:
                    pass
            
            # Create appropriate latent for this model
            # For FLUX2: halve the spatial dimensions since it uses 16x compression
            current_latent = latent
            if is_flux2_model and latent_channels != 128:
                # Input latent is standard (4 or 16 channels with 8x compression)
                # Need to create FLUX2-compatible latent at half spatial resolution
                device = comfy.model_management.intermediate_device()
                flux2_latent = torch.zeros(
                    [latent_image.shape[0], 128, latent_image.shape[2] // 2, latent_image.shape[3] // 2],
                    device=device
                )
                current_latent = {"samples": flux2_latent}
                print(f"[SamplerCompareSimple] Created FLUX2 latent: {flux2_latent.shape} for {latent_width}x{latent_height} output")
            elif not is_flux2_model and latent_channels == 128:
                # Input latent is FLUX2 (128 channels with 16x compression)
                # Need to create standard latent at double spatial resolution
                device = comfy.model_management.intermediate_device()
                std_latent = torch.zeros(
                    [latent_image.shape[0], 4, latent_image.shape[2] * 2, latent_image.shape[3] * 2],
                    device=device
                )
                current_latent = {"samples": std_latent}
                print(f"[SamplerCompareSimple] Created standard latent: {std_latent.shape} for {latent_width}x{latent_height} output")
            
            # 2. Prepare Models (Clone & Apply LoRAs)
            
            # Base/High Model
            working_model = model_entry["model_obj"]
            if hasattr(working_model, 'clone'): working_model = working_model.clone()
            
            # Apply Patches (Shift, etc.)
            working_model = apply_model_patches(working_model, preset, latent_width=latent_width, latent_height=latent_height)
            
            # 2B. Handle CLIP Variations & Prompt Variations
            # Always re-encode conditioning with THIS combo's CLIP object
            # This is critical when comparing different model types (e.g., FLUX2 vs FLUX)
            # as they have incompatible CLIP architectures
            current_positive = positive
            current_negative = negative
            
            # Get CLIP variation info
            clip_var = combo.get("clip_variation")
            if clip_var:
                clip_type = clip_var.get("type", "unknown")
                if clip_type == "pair":
                    clip_label = f"{clip_var.get('a', 'unknown')} + {clip_var.get('b', 'unknown')}"
                else:
                    clip_label = clip_var.get("model", "unknown")
                print(f"[SamplerCompareSimple] Using CLIP: {clip_label}")
                
                # ALWAYS re-encode conditioning with THIS combo's CLIP object
                # Each model variation has its own CLIP and they may have different architectures
                clip_obj = clip_var.get("clip_obj")
                if clip_obj:
                    # Use prompt text directly from the combo (populated by loaders)
                    pos_text = combo.get("prompt_positive", "")
                    neg_text = combo.get("prompt_negative", "")
                    
                    try:
                        # Re-encode with this combo's CLIP
                        tokens = clip_obj.tokenize(pos_text)
                        # Add guidance for FLUX models
                        if preset in ["FLUX", "FLUX2"]:
                            current_positive = clip_obj.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
                        else:
                            current_positive = clip_obj.encode_from_tokens_scheduled(tokens)
                        
                        tokens = clip_obj.tokenize(neg_text)
                        if preset in ["FLUX", "FLUX2"]:
                            current_negative = clip_obj.encode_from_tokens_scheduled(tokens, add_dict={"guidance": flux_guidance})
                        else:
                            current_negative = clip_obj.encode_from_tokens_scheduled(tokens)
                        
                        # Safe truncation for debug message
                        prompt_preview = pos_text[:50] if pos_text else "(empty)"
                        print(f"[SamplerCompareSimple] Encoded conditioning with combo's CLIP (prompt: '{prompt_preview}...')")
                    except Exception as e:
                        print(f"[SamplerCompareSimple] Warning: Failed to encode with combo CLIP: {e}")
                        import traceback
                        traceback.print_exc()
                else:
                    print(f"[SamplerCompareSimple] Warning: No clip_obj in clip_variation, using pre-encoded conditioning")
            else:
                print(f"[SamplerCompareSimple] Using pre-encoded conditioning (no clip_variation)")
            # Apply LoRAs
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", ())
            if lora_names:
                working_model = self._apply_loras(working_model, lora_names, lora_strengths)

            # Low Model (WAN 2.2 only)
            working_model_low = None
            if is_wan_2_2:
                working_model_low = model_entry.get("model_low_obj")
                if working_model_low:
                    if hasattr(working_model_low, 'clone'): working_model_low = working_model_low.clone()
                    
                    # Apply Patches to Low Model
                    working_model_low = apply_model_patches(working_model_low, preset, is_low_noise=True, latent_width=latent_width, latent_height=latent_height)
                    
                    l_names_low = combo.get("lora_names_low", [])
                    l_strengths_low = combo.get("lora_strengths_low", ())
                    if l_names_low:
                        working_model_low = self._apply_loras(working_model_low, l_names_low, l_strengths_low)
                else:
                    print("[SamplerCompareSimple] WARNING: WAN 2.2 preset selected but no Low Noise model found!")

            # 3. Sampling
            
            sampled_latent = None
            
            if is_wan_2_2 and working_model_low:
                # WAN 2.2 2-Stage Sampling
                # Stage 1: High noise model (coarse detail) from start to midpoint
                # Stage 2: Low noise model (fine detail) from midpoint to end
                
                # Use absolute steps directly
                start_step_1 = wan_high_start
                end_step_1 = wan_high_end
                start_step_2 = wan_low_start
                end_step_2 = wan_low_end
                
                print(f"[SamplerCompareSimple] WAN 2.2 Sampling: High ({start_step_1}-{end_step_1}) -> Low ({start_step_2}-{end_step_2})")
                print(f"  Total steps: {steps}, Denoise: {denoise}")
                
                try:
                    # For WAN 2.2, we need to use KSamplerAdvanced for proper control
                    # Import KSamplerAdvanced  
                    from nodes import KSamplerAdvanced
                    
                    # Stage 1: High Noise Model (from start to midpoint)
                    print(f"  Stage 1: High Noise Model (steps {start_step_1} to {end_step_1})")
                    
                    # KSamplerAdvanced parameters: model, seed, steps, cfg, sampler, scheduler, positive, negative, latent, 
                    #                               add_noise, noise_seed, start_at_step, end_at_step
                    k_sampler = KSamplerAdvanced()
                    samples_1_tuple = k_sampler.sample(
                        model=working_model,
                        seed=seed,
                        steps=steps,
                        cfg=cfg,
                        sampler_name=sampler_name,
                        scheduler=scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent_image=current_latent,
                        add_noise="enable",
                        noise_seed=seed,
                        start_at_step=start_step_1,
                        end_at_step=end_step_1
                    )
                    samples_1 = samples_1_tuple[0]
                    print(f"  Stage 1 complete: output shape {samples_1['samples'].shape}")
                    
                    # Stage 2: Low Noise Model (from midpoint to end)
                    # Use output from Stage 1 as input, don't add noise
                    print(f"  Stage 2: Low Noise Model (steps {start_step_2} to {end_step_2})")
                    samples_2_tuple = k_sampler.sample(
                        model=working_model_low,
                        seed=seed,
                        steps=steps,
                        cfg=cfg,
                        sampler_name=sampler_name,
                        scheduler=scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent_image=samples_1,  # Use Stage 1 output
                        add_noise="disable",  # Don't add new noise
                        noise_seed=seed,
                        start_at_step=start_step_2,
                        end_at_step=end_step_2
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
            image = self._decode_latent(sampled_latent, current_vae)
            all_images.append(image)
            
            # 5. Labeling
            label_parts = []
            is_grouped = config.get("is_grouped", False)
            
            # Use display_name if available, otherwise fall back to name
            model_display = model_entry.get("display_name", model_entry["name"])
            
            if is_grouped:
                # In grouped mode, just show the model name as the primary identifier
                # VAE and CLIP are implied by the group
                label_parts.append(clean_name(model_display))
            else:
                # In non-grouped mode, show all varying parts
                if len(config.get("model_variations", [])) > 1:
                    label_parts.append(clean_name(model_display))
                
                if len(config.get("vae_variations", [])) > 1 and not model_entry.get("baked_vae"):
                    label_parts.append(clean_name(combo.get("vae_name", "")))
                    
                clip_var = combo.get("clip_variation")
                if len(config.get("clip_variations", [])) > 1 and clip_var:
                    # Use new dict structure with type/a/b/model keys
                    clip_type = clip_var.get("type", "unknown")
                    if clip_type == "pair":
                        label_parts.append(f"{clean_name(clip_var.get('a'))}+{clean_name(clip_var.get('b'))}")
                    else:
                        label_parts.append(clean_name(clip_var.get("model")))
            
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", [])
            if lora_names:
                # Show last varied LoRA
                idx_l = len(lora_names) - 1
                label_parts.append(f"{lora_names[idx_l]}({lora_strengths[idx_l]:.2f})")
            
            # For grouped mode, don't add prompt to label - grid handles prompt display
            # For non-grouped mode, add short prompt indicator
            prompt_variations = config.get("prompt_variations", [])
            if len(prompt_variations) > 1 and not is_grouped:
                prompt_idx = combo.get("prompt_index", 1)
                label_parts.append(f"P{prompt_idx}")
            
            label = " - ".join(label_parts) if label_parts else f"Combo {idx}"
            all_labels.append(label)
            print(f"[SamplerCompareSimple] Label: {label}")
        
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
        
        return (images_tensor, labels_str, config)
    
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
    
    @staticmethod
    def _decode_latent(latent_dict, vae):
        """Decode latent samples to image using VAE."""
        samples = latent_dict["samples"] if isinstance(latent_dict, dict) else latent_dict
        image = vae.decode(samples)
        if image.dim() == 5: image = image[:, 0:1, :, :, :] # Take first frame
        if image.dim() == 5: image = image.squeeze(1)
        return image

# Node class mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompareSimple": SamplerCompareSimple,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompareSimple": "Sampler Compare Simple",
}
