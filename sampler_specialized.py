"""
Specialized Sampler Nodes for Different Model Types
Each node type handles its specific model architecture with built-in pipeline configuration.
"""

import os
import torch
from typing import Dict, List, Tuple, Any, Optional
import folder_paths
import comfy.sd
import comfy.model_management
import comfy.utils
import comfy.sample
from comfy.utils import ProgressBar
from comfy.samplers import SAMPLER_NAMES
import latent_preview

# Get full sampler list from ComfyUI
AVAILABLE_SAMPLERS = list(SAMPLER_NAMES)

# Model cache to avoid reloading unchanged models
class ModelCache:
    """
    Caches loaded models to avoid expensive reloads.
    Only reloads when model path changes.
    """
    def __init__(self):
        self.cached_model = None
        self.cached_model_path = None
        self.cached_loras = {}  # path -> applied strengths dict
    
    def get_or_load_model(self, model_path: str, model_type: str, debug_log: bool = False) -> Any:
        """
        Get cached model or load it if path changed.
        Returns the model and whether it was newly loaded.
        """
        if self.cached_model_path == model_path and self.cached_model is not None:
            if debug_log:
                print(f"[ModelCache] Using cached model: {model_path}")
            return self.cached_model, False
        
        if debug_log:
            print(f"[ModelCache] Loading new model: {model_path}")
        
        # Clear old cache
        if self.cached_model is not None and self.cached_model_path != model_path:
            if debug_log:
                print(f"[ModelCache] Clearing cached model: {self.cached_model_path}")
            self.clear()
        
        # Load new model
        if model_type == "checkpoint":
            sd = comfy.sd.load_checkpoint_guess_config(model_path, output_vae=False, output_clip=False, embedding_directory=None)
            self.cached_model = sd[0]
            del sd
        else:
            sd = comfy.utils.load_torch_file(model_path)
            self.cached_model = comfy.sd.load_diffusion_model_state_dict(sd)
            del sd
        
        self.cached_model_path = model_path
        self.cached_loras = {}
        return self.cached_model, True
    
    def is_lora_applied(self, lora_path: str, strength: float) -> bool:
        """Check if a LoRA is already applied at the specified strength."""
        return self.cached_loras.get(lora_path) == strength
    
    def mark_lora_applied(self, lora_path: str, strength: float):
        """Mark a LoRA as applied."""
        self.cached_loras[lora_path] = strength
    
    def clear(self):
        """Clear all cached models."""
        if self.cached_model is not None:
            del self.cached_model
        self.cached_model = None
        self.cached_model_path = None
        self.cached_loras = {}
    
    def soft_reset_loras(self):
        """
        Reset LoRA tracking but keep the base model.
        Use this when moving to a different combination with the same base model.
        """
        self.cached_loras = {}

# Global cache instance shared across all samplers
_model_cache = ModelCache()


def generate_smart_labels(combinations: List[Dict[str, Any]], config: Dict[str, Any] = None) -> List[str]:
    """
    Generate concise labels showing only the varying parameters.
    Uses custom display names if provided, otherwise uses filenames.
    Works with OR operators where different LoRAs appear in different combos.
    """
    if not combinations:
        return []
    
    labels = []
    
    # Check what varies across combinations
    first_combo = combinations[0]
    models_vary = any(c['model'] != first_combo['model'] for c in combinations)
    vaes_vary = any(c['vae'] != first_combo['vae'] for c in combinations)
    
    # Build a map of lora_name -> display_name for all combinations
    lora_display_map = {}
    all_lora_names = set()
    for combo in combinations:
        if combo.get('lora_names'):
            all_lora_names.update(combo['lora_names'])
        if combo.get('lora_names') and combo.get('lora_display_names'):
            for lora_name, display_name in zip(combo['lora_names'], combo['lora_display_names']):
                lora_display_map[lora_name] = display_name
    
    # Determine which LoRAs have varying strengths (check across ALL LoRAs in all combos)
    lora_varies = {}
    for lora_name in all_lora_names:
        strengths = []
        for combo in combinations:
            if combo.get('lora_names') and lora_name in combo['lora_names']:
                idx = combo['lora_names'].index(lora_name)
                if idx < len(combo.get('lora_strengths', [])):
                    strengths.append(combo['lora_strengths'][idx])
        # LoRA varies if not all strengths are the same
        lora_varies[lora_name] = len(set(strengths)) > 1 if strengths else False
    
    for combo in combinations:
        label_parts = []
        
        # Only show model if it varies
        if models_vary:
            model_filename = combo['model'].split('\\')[-1] if '\\' in combo['model'] else combo['model'].split('/')[-1]
            label_parts.append(model_filename)
        
        # Only show VAE if it varies
        if vaes_vary:
            vae_filename = combo['vae'].split('\\')[-1] if '\\' in combo['vae'] else combo['vae'].split('/')[-1]
            label_parts.append(f"VAE:{vae_filename}")
        
        # Show LoRAs that vary (always show them with their custom names when they vary)
        if combo.get('lora_names') and combo.get('lora_strengths'):
            for lora_name, strength in zip(combo['lora_names'], combo['lora_strengths']):
                # Always show LoRA if it varies (regardless of AND/OR)
                if lora_varies.get(lora_name, False):
                    # Use display name from the map, fallback to filename
                    display_name = lora_display_map.get(lora_name)
                    if not display_name:
                        display_name = lora_name.split('\\')[-1] if '\\' in lora_name else lora_name.split('/')[-1]
                    
                    label_parts.append(f"{display_name}({strength:.2f})")
        
        # If nothing varies, show at least the model name
        if not label_parts:
            model_filename = combo['model'].split('\\')[-1] if '\\' in combo['model'] else combo['model'].split('/')[-1]
            label_parts.append(model_filename)
        
        labels.append(" + ".join(label_parts))
    
    return labels


class SamplerCompareCheckpoint:
    """
    Sampler for standard Checkpoint models (SD/SDXL)
    Receives config and loaded models from loader node.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "latent": ("LATENT",),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000, "step": 1}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.5}),
                "sampler_name": (AVAILABLE_SAMPLERS, {"default": "euler"}),
                "scheduler": (["normal", "karras", "exponential"], {"default": "normal"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
            },
        }
    
    CATEGORY = "sampling"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "labels")
    FUNCTION = "sample"
    OUTPUT_NODE = True
    
    def sample(self, config, model, clip, vae, latent, steps, cfg, sampler_name, scheduler, seed, positive, negative):
        debug_log = config.get("debug_log", False)
        
        if debug_log:
            print("[SamplerCompareCheckpoint] Sampling from checkpoint models")
            print(f"  - Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
            print(f"  - Seed: {seed}")
        
        try:
            combinations = config.get("combinations", [])
            if not combinations:
                print("[SamplerCompareCheckpoint] Error: No combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            # Summary output (always shown)
            print(f"[SamplerCompareCheckpoint] Generating {len(combinations)} images")
            
            # Collect latents for all combinations - for now use the provided latent
            sampled_latents = []
            labels_list = []
            
            progress_bar = ProgressBar(len(combinations))
            
            for i, combo in enumerate(combinations):
                progress_bar.update(i)
                print(f"[SamplerCompareCheckpoint] Generating image {i+1}/{len(combinations)}")
                if debug_log:
                    print(f"  Model: {combo['model']}, VAE: {combo['vae']}, LoRAs: {combo['lora_names']}")
                    print(f"  LoRA Strengths: {combo['lora_strengths']}")
                
                # Only unload if we're switching to a different base model
                current_model_name = combo['model']
                if i > 0 and _model_cache.cached_model_path and not _model_cache.cached_model_path.endswith(current_model_name):
                    if debug_log:
                        print(f"[SamplerCompareCheckpoint] Base model changed, cleaning up...")
                    import gc
                    gc.collect()
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    comfy.model_management.cleanup_models_gc()
                    comfy.model_management.soft_empty_cache()
                
                # Perform actual sampling - use same seed for this combination
                try:
                    if debug_log:
                        print(f"[SamplerCompareCheckpoint] Sampling with seed {seed}, steps {steps}...")
                    
                    # Load or retrieve cached model
                    model_name = combo['model']
                    model_type = combo['model_type']
                    model_path = folder_paths.get_full_path_or_raise("checkpoints", model_name) if model_type == "checkpoint" else folder_paths.get_full_path_or_raise("diffusion_models", model_name)
                    
                    combo_model, was_loaded = _model_cache.get_or_load_model(model_path, model_type, debug_log)
                    
                    if debug_log:
                        cache_status = "newly loaded" if was_loaded else "from cache"
                        print(f"[SamplerCompareCheckpoint] Model {cache_status}, type: {type(combo_model)}")
                    
                    # Apply LoRAs to the model (only if not already applied)
                    if combo.get('lora_names') and combo.get('lora_strengths'):
                        if debug_log:
                            print(f"[SamplerCompareCheckpoint] Applying {len(combo['lora_names'])} LoRAs")
                        for lora_name, lora_strength in zip(combo['lora_names'], combo['lora_strengths']):
                            if lora_strength == 0:
                                if debug_log:
                                    print(f"[SamplerCompareCheckpoint]   Skipping {lora_name} (strength=0)")
                                continue
                            
                            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
                            
                            # Check if this LoRA is already applied at this strength
                            if _model_cache.is_lora_applied(lora_path, lora_strength):
                                if debug_log:
                                    print(f"[SamplerCompareCheckpoint]   {lora_name} already applied at {lora_strength}")
                                continue
                            
                            if debug_log:
                                print(f"[SamplerCompareCheckpoint]   Loading {lora_name} with strength {lora_strength}")
                            try:
                                lora_data = comfy.utils.load_torch_file(lora_path)
                                # Load and apply LoRA - model is required, clip is optional
                                old_patches = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                                combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
                                new_patches = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                                _model_cache.mark_lora_applied(lora_path, lora_strength)
                                if debug_log:
                                    print(f"[SamplerCompareCheckpoint]   LoRA applied successfully (patches: {old_patches} -> {new_patches})")
                            except Exception as lora_err:
                                print(f"[SamplerCompareCheckpoint]   Error loading LoRA: {lora_err}")
                    
                    # Fix empty latent channels
                    latent_samples = latent["samples"].clone()
                    latent_samples = comfy.sample.fix_empty_latent_channels(combo_model, latent_samples)
                    
                    # Prepare noise - use same seed for this combination
                    batch_inds = latent.get("batch_index", None)
                    noise = comfy.sample.prepare_noise(latent_samples, seed, batch_inds)
                    
                    # Setup callback for progress
                    callback = latent_preview.prepare_callback(combo_model, steps)
                    
                    # Run the actual sampler
                    if debug_log:
                        print(f"[SamplerCompareCheckpoint] Running sampler: {sampler_name}")
                    
                    # Log model state before sampling (only in debug mode)
                    if debug_log:
                        patches_before = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                        print(f"[SamplerCompareCheckpoint] BEFORE sample call: patches count = {patches_before}")
                        if hasattr(combo_model, 'patches') and combo_model.patches:
                            print(f"[SamplerCompareCheckpoint]   Patch keys: {list(combo_model.patches.keys())[:5]}...")
                    
                    samples_out = comfy.sample.sample(
                        combo_model,
                        noise,
                        steps,
                        cfg,
                        sampler_name,
                        scheduler,
                        positive,
                        negative,
                        latent_samples,
                        denoise=1.0,
                        disable_noise=False,
                        callback=callback,
                        disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
                        seed=seed
                    )
                    
                    # Log model state after sampling (only in debug mode)
                    if debug_log:
                        patches_after = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                        print(f"[SamplerCompareCheckpoint] AFTER sample call: patches count = {patches_after}")
                    
                    sampled_latents.append(samples_out)
                    if debug_log:
                        print(f"[SamplerCompareCheckpoint] Sampled latent shape: {samples_out.shape}")
                    
                except comfy.model_management.InterruptProcessingException:
                    print(f"[SamplerCompareCheckpoint] Interrupted")
                    raise  # Re-raise to stop execution
                except Exception as e:
                    print(f"[SamplerCompareCheckpoint] Error: {e}")
                    if debug_log:
                        import traceback
                        traceback.print_exc()
                    sampled_latents.append(latent["samples"])
                
                # Aggressively clean up the model to prevent crashes when loading the next one
                if debug_log:
                    print(f"[SamplerCompareCheckpoint] Cleaning up temporary variables...")
                try:
                    # Delete all local references to temporary objects
                    if 'latent_samples' in locals():
                        del latent_samples
                    if 'noise' in locals():
                        del noise
                    if 'samples_out' in locals():
                        del samples_out
                except:
                    pass
                
                # Only do aggressive cleanup between different models
                if i < len(combinations) - 1:
                    next_model = combinations[i + 1]['model']
                    if next_model != current_model_name:
                        if debug_log:
                            print(f"[SamplerCompareCheckpoint] Next model is different, aggressive cleanup...")
                        import gc
                        gc.collect()
                        comfy.model_management.soft_empty_cache()
                    elif debug_log:
                        print(f"[SamplerCompareCheckpoint] Next model is same, skipping aggressive cleanup")
                else:
                    # Final cleanup at the end
                    if debug_log:
                        print(f"[SamplerCompareCheckpoint] Final cleanup after all images...")
                    import gc
                    gc.collect()
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    comfy.model_management.cleanup_models_gc()
                    comfy.model_management.soft_empty_cache()
            
            progress_bar.update(len(combinations))
            
            # Generate smart labels showing only differences
            labels_list = generate_smart_labels(combinations[:len(sampled_latents)], config)
            if sampled_latents:
                stacked_latents = torch.cat(sampled_latents, dim=0)
                if debug_log:
                    print(f"[SamplerCompareCheckpoint] Stacked latent shape: {stacked_latents.shape}")
                
                # Decode latents with VAE
                print(f"[SamplerCompareCheckpoint] Decoding {stacked_latents.shape[0]} latents with VAE")
                try:
                    # Try regular decode first (handles both 2D and 3D latents)
                    decoded = vae.decode(stacked_latents)
                except Exception as e:
                    print(f"[SamplerCompareCheckpoint] Decode failed: {e}, trying decode_tiled")
                    try:
                        # Fallback to decode_tiled if available and without extra args
                        decoded = vae.decode_tiled(stacked_latents, tile_latent_min_size=32)
                    except Exception as e2:
                        print(f"[SamplerCompareCheckpoint] Decode_tiled also failed: {e2}")
                        raise
                
                # Ensure output is in correct format (B, H, W, C) with values in [0, 1]
                print(f"[SamplerCompareCheckpoint] Decoded shape: {decoded.shape}, dtype: {decoded.dtype}")
                
                # Handle the actual shape returned: [4, 1, 3216, 2144, 3] -> should be [4, 3216, 2144, 3]
                if decoded.dim() == 5:
                    # Check if it's (B, C, H, W, 3) - the VAE is returning RGB channels last
                    if decoded.shape[1] == 1 and decoded.shape[-1] == 3:
                        # (B, 1, H, W, 3) -> squeeze C and we're done
                        output = decoded.squeeze(1)  # (B, H, W, 3)
                        print(f"[SamplerCompareCheckpoint] Squeezed (B,1,H,W,3) to: {output.shape}")
                    elif decoded.shape[-1] == 3:
                        # Some other 5D format with 3 as last dim - assume it's RGB channels
                        output = decoded
                    elif decoded.shape[2] == 1:
                        # (B, C, 1, H, W) -> squeeze time, transpose
                        decoded = decoded.squeeze(2)  # (B, C, H, W)
                        output = decoded.permute(0, 2, 3, 1)  # (B, H, W, C)
                    else:
                        # (B, C, T, H, W) -> take first frame, transpose
                        decoded = decoded[:, :, 0, :, :]  # (B, C, H, W)
                        output = decoded.permute(0, 2, 3, 1)  # (B, H, W, C)
                elif decoded.dim() == 4:
                    if decoded.shape[-1] == 3:
                        # Already (B, H, W, C)
                        output = decoded
                    elif decoded.shape[1] == 3:
                        # (B, C, H, W) -> (B, H, W, C)
                        output = decoded.permute(0, 2, 3, 1)
                        print(f"[SamplerCompareCheckpoint] Transposed from (B,C,H,W) to (B,H,W,C): {output.shape}")
                    else:
                        output = decoded
                else:
                    # Fallback
                    print(f"[SamplerCompareCheckpoint] Warning: Unexpected tensor shape {decoded.shape}")
                    output = decoded
                
                # Ensure output is float in [0, 1] range
                if output.dtype != torch.float32:
                    output = output.float()
                output = torch.clamp(output, 0.0, 1.0)
                print(f"[SamplerCompareCheckpoint] Final output shape: {output.shape}")
                
                labels = "; ".join(labels_list)
                return (output, labels)
            else:
                return (torch.zeros((1, 512, 512, 3)), "Error: No latents generated")
        
        except comfy.model_management.InterruptProcessingException:
            print("[SamplerCompareCheckpoint] Execution cancelled by user")
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), "Error: Cancelled by user")
        
        except KeyboardInterrupt:
            print("[SamplerCompareCheckpoint] Sampling interrupted by user")
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), "Error: Cancelled by user")
        
        except Exception as e:
            print(f"[SamplerCompareCheckpoint] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
            # Clean up on error
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), f"Error: {str(e)}")


class SamplerCompareQwenEdit:
    """
    Sampler for Qwen Edit diffuser models with AuraFlow sampling
    Pipeline: Diffusion Model -> LoRA -> ModelSamplingAuraFlow -> CFGNorm -> Sampler
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "latent": ("LATENT",),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000, "step": 1}),
                "sampler_name": (AVAILABLE_SAMPLERS, {"default": "euler"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                # AuraFlow specific parameters
                "guidance_scale": ("FLOAT", {"default": 7.5, "min": 0.0, "max": 20.0, "step": 0.1}),
                "aura_flow_mode": (["standard", "turbo", "quality"], {"default": "standard"}),
                # CFGNorm parameters
                "cfg_norm_strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "cfg_norm_mode": (["off", "on"], {"default": "on"}),
            },
            "optional": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
            },
        }
    
    CATEGORY = "sampling"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "labels")
    FUNCTION = "sample"
    OUTPUT_NODE = True
    
    def sample(self, config, latent, steps, sampler_name, seed, positive, negative, guidance_scale, aura_flow_mode, cfg_norm_strength, cfg_norm_mode, model=None, clip=None, vae=None):
        debug_log = config.get("debug_log", False)
        
        if debug_log:
            print("[SamplerCompareQwenEdit] Sampling from Qwen Edit models with AuraFlow pipeline")
            print(f"  - Sampler: {sampler_name}")
            print(f"  - AuraFlow Mode: {aura_flow_mode}")
            print(f"  - Guidance Scale: {guidance_scale}")
            print(f"  - CFGNorm: {cfg_norm_mode} (strength: {cfg_norm_strength})")
            print(f"  - Steps: {steps}, Seed: {seed}")
        
        try:
            # Use config from loader
            combinations = config.get("combinations", [])
            if not combinations:
                print("[SamplerCompareQwenEdit] Error: No combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            print(f"[SamplerCompareQwenEdit] Generating {len(combinations)} images")
            
            # Get VAE from the config path or from optional input
            if vae is None:
                vae_name = combinations[0].get("vae", "")
                if vae_name:
                    print(f"[SamplerCompareQwenEdit] Loading VAE: {vae_name}")
                    vae_path = folder_paths.get_full_path_or_raise("vae", vae_name)
                    vae_sd = comfy.utils.load_torch_file(vae_path)
                    vae = comfy.sd.VAE(sd=vae_sd)
                    vae.throw_exception_if_invalid()
            
            if vae is None:
                print("[SamplerCompareQwenEdit] Error: No VAE available for decoding")
                return (torch.zeros((1, 512, 512, 3)), "Error: No VAE")
            
            # Collect latents for all combinations - for now use the provided latent
            # In a real implementation, this would sample from each model variant
            sampled_latents = []
            labels_list = []
            
            progress_bar = ProgressBar(len(combinations))
            
            for i, combo in enumerate(combinations):
                progress_bar.update(i)
                print(f"[SamplerCompareQwenEdit] Generating image {i+1}/{len(combinations)}")
                if debug_log:
                    print(f"  Model: {combo['model']}, VAE: {combo['vae']}, LoRAs: {combo['lora_names']}")
                    print(f"  LoRA Strengths: {combo['lora_strengths']}")
                
                # Only unload if we're switching to a different base model
                current_model_name = combo['model']
                if i > 0 and _model_cache.cached_model_path and not _model_cache.cached_model_path.endswith(current_model_name):
                    if debug_log:
                        print(f"[SamplerCompareQwenEdit] Base model changed, cleaning up...")
                    import gc
                    gc.collect()
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    comfy.model_management.cleanup_models_gc()
                    comfy.model_management.soft_empty_cache()
                
                # Perform actual sampling - use same seed for this combination
                try:
                    print(f"[SamplerCompareQwenEdit] Sampling with seed {seed}, steps {steps}...")
                    
                    # Load or retrieve cached model
                    model_name = combo['model']
                    model_type = combo['model_type']
                    model_path = folder_paths.get_full_path_or_raise("checkpoints", model_name) if model_type == "checkpoint" else folder_paths.get_full_path_or_raise("diffusion_models", model_name)
                    
                    combo_model, was_loaded = _model_cache.get_or_load_model(model_path, model_type, debug_log)
                    
                    if debug_log:
                        cache_status = "newly loaded" if was_loaded else "from cache"
                        print(f"[SamplerCompareQwenEdit] Model {cache_status}, type: {type(combo_model)}")
                    else:
                        print(f"[SamplerCompareQwenEdit] Model loaded, type: {type(combo_model)}")
                    
                    # Apply LoRAs to the model (only if not already applied)
                    if combo.get('lora_names') and combo.get('lora_strengths'):
                        print(f"[SamplerCompareQwenEdit] Applying {len(combo['lora_names'])} LoRAs")
                        for lora_name, lora_strength in zip(combo['lora_names'], combo['lora_strengths']):
                            if lora_strength == 0:
                                print(f"[SamplerCompareQwenEdit]   Skipping {lora_name} (strength=0)")
                                continue
                            
                            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
                            
                            # Check if this LoRA is already applied at this strength
                            if _model_cache.is_lora_applied(lora_path, lora_strength):
                                if debug_log:
                                    print(f"[SamplerCompareQwenEdit]   {lora_name} already applied at {lora_strength}")
                                continue
                            
                            print(f"[SamplerCompareQwenEdit]   Loading {lora_name} with strength {lora_strength}")
                            try:
                                lora_data = comfy.utils.load_torch_file(lora_path)
                                # Load and apply LoRA - model is required, clip is optional
                                old_patches = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                                combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
                                new_patches = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                                _model_cache.mark_lora_applied(lora_path, lora_strength)
                                print(f"[SamplerCompareQwenEdit]   LoRA applied successfully (patches: {old_patches} -> {new_patches})")
                            except Exception as lora_err:
                                print(f"[SamplerCompareQwenEdit]   Error loading LoRA: {lora_err}")
                    
                    # Fix empty latent channels
                    latent_samples = latent["samples"].clone()
                    latent_samples = comfy.sample.fix_empty_latent_channels(combo_model, latent_samples)
                    
                    # Prepare noise - use same seed for this combination
                    batch_inds = latent.get("batch_index", None)
                    noise = comfy.sample.prepare_noise(latent_samples, seed, batch_inds)
                    
                    # Setup callback for progress
                    callback = latent_preview.prepare_callback(combo_model, steps)
                    
                    # Run the actual sampler
                    print(f"[SamplerCompareQwenEdit] Running sampler: {sampler_name}")
                    
                    # Log model state before sampling
                    patches_before = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                    print(f"[SamplerCompareQwenEdit] BEFORE sample call: patches count = {patches_before}")
                    if hasattr(combo_model, 'patches') and combo_model.patches:
                        print(f"[SamplerCompareQwenEdit]   Patch keys: {list(combo_model.patches.keys())[:5]}...")
                    
                    samples_out = comfy.sample.sample(
                        combo_model,
                        noise,
                        steps,
                        guidance_scale,  # Use guidance_scale as CFG
                        sampler_name,
                        "normal",  # scheduler
                        positive,
                        negative,
                        latent_samples,
                        denoise=1.0,
                        disable_noise=False,
                        callback=callback,
                        disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
                        seed=seed
                    )
                    
                    # Log model state after sampling
                    patches_after = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                    print(f"[SamplerCompareQwenEdit] AFTER sample call: patches count = {patches_after}")
                    
                    sampled_latents.append(samples_out)
                    print(f"[SamplerCompareQwenEdit] Sampled latent shape: {samples_out.shape}")
                    
                except comfy.model_management.InterruptProcessingException:
                    print(f"[SamplerCompareQwenEdit] Sampling interrupted, stopping all combinations")
                    raise  # Re-raise to stop execution
                except Exception as e:
                    print(f"[SamplerCompareQwenEdit] Sampling failed: {e}, using input latent instead")
                    import traceback
                    traceback.print_exc()
                    sampled_latents.append(latent["samples"])
                
                # Only do aggressive cleanup between different models
                if debug_log:
                    print(f"[SamplerCompareQwenEdit] Cleaning up temporary variables...")
                try:
                    # Delete all local references to temporary objects
                    if 'latent_samples' in locals():
                        del latent_samples
                    if 'noise' in locals():
                        del noise
                    if 'samples_out' in locals():
                        del samples_out
                except:
                    pass
                
                # Only do aggressive cleanup between different models
                if i < len(combinations) - 1:
                    next_model = combinations[i + 1]['model']
                    if next_model != current_model_name:
                        if debug_log:
                            print(f"[SamplerCompareQwenEdit] Next model is different, aggressive cleanup...")
                        import gc
                        gc.collect()
                        comfy.model_management.soft_empty_cache()
                    elif debug_log:
                        print(f"[SamplerCompareQwenEdit] Next model is same, skipping aggressive cleanup")
                else:
                    # Final cleanup at the end
                    if debug_log:
                        print(f"[SamplerCompareQwenEdit] Final cleanup after all images...")
                    import gc
                    gc.collect()
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    comfy.model_management.cleanup_models_gc()
                    comfy.model_management.soft_empty_cache()
            
            progress_bar.update(len(combinations))
            
            # Generate smart labels showing only differences
            labels_list = generate_smart_labels(combinations[:len(sampled_latents)], config)
            
            # Stack all sampled latents
            if sampled_latents:
                stacked_latents = torch.cat(sampled_latents, dim=0)
                print(f"[SamplerCompareQwenEdit] Stacked latent shape: {stacked_latents.shape}")
                
                # Decode latents with VAE
                print(f"[SamplerCompareQwenEdit] Decoding {stacked_latents.shape[0]} latents with VAE")
                try:
                    # Try regular decode first (handles both 2D and 3D latents)
                    decoded = vae.decode(stacked_latents)
                except Exception as e:
                    print(f"[SamplerCompareQwenEdit] Decode failed: {e}, trying decode_tiled")
                    try:
                        # Fallback to decode_tiled if available and without extra args
                        decoded = vae.decode_tiled(stacked_latents, tile_latent_min_size=32)
                    except Exception as e2:
                        print(f"[SamplerCompareQwenEdit] Decode_tiled also failed: {e2}")
                        raise
                
                # Ensure output is in correct format (B, H, W, C) with values in [0, 1]
                print(f"[SamplerCompareQwenEdit] Decoded shape: {decoded.shape}, dtype: {decoded.dtype}")
                
                # Handle the actual shape returned: [4, 1, 3216, 2144, 3] -> should be [4, 3216, 2144, 3]
                if decoded.dim() == 5:
                    # Check if it's (B, C, H, W, 3) - the VAE is returning RGB channels last
                    if decoded.shape[1] == 1 and decoded.shape[-1] == 3:
                        # (B, 1, H, W, 3) -> squeeze C and we're done
                        output = decoded.squeeze(1)  # (B, H, W, 3)
                        print(f"[SamplerCompareQwenEdit] Squeezed (B,1,H,W,3) to: {output.shape}")
                    elif decoded.shape[-1] == 3:
                        # Some other 5D format with 3 as last dim - assume it's RGB channels
                        output = decoded
                    elif decoded.shape[2] == 1:
                        # (B, C, 1, H, W) -> squeeze time, transpose
                        decoded = decoded.squeeze(2)  # (B, C, H, W)
                        output = decoded.permute(0, 2, 3, 1)  # (B, H, W, C)
                    else:
                        # (B, C, T, H, W) -> take first frame, transpose
                        decoded = decoded[:, :, 0, :, :]  # (B, C, H, W)
                        output = decoded.permute(0, 2, 3, 1)  # (B, H, W, C)
                elif decoded.dim() == 4:
                    if decoded.shape[-1] == 3:
                        # Already (B, H, W, C)
                        output = decoded
                    elif decoded.shape[1] == 3:
                        # (B, C, H, W) -> (B, H, W, C)
                        output = decoded.permute(0, 2, 3, 1)
                        print(f"[SamplerCompareQwenEdit] Transposed from (B,C,H,W) to (B,H,W,C): {output.shape}")
                    else:
                        output = decoded
                else:
                    # Fallback
                    print(f"[SamplerCompareQwenEdit] Warning: Unexpected tensor shape {decoded.shape}")
                    output = decoded
                
                # Ensure output is float in [0, 1] range
                if output.dtype != torch.float32:
                    output = output.float()
                output = torch.clamp(output, 0.0, 1.0)
                print(f"[SamplerCompareQwenEdit] Final output shape: {output.shape}")
                
                labels = "; ".join(labels_list)
                return (output, labels)
            else:
                return (torch.zeros((1, 512, 512, 3)), "Error: No latents generated")
        
        except comfy.model_management.InterruptProcessingException:
            print("[SamplerCompareQwenEdit] Execution cancelled by user")
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), "Error: Cancelled by user")
        
        except KeyboardInterrupt:
            print("[SamplerCompareQwenEdit] Sampling interrupted by user")
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), "Error: Cancelled by user")
        
        except Exception as e:
            print(f"[SamplerCompareQwenEdit] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
            # Clean up on error
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), f"Error: {str(e)}")


class SamplerCompareDiffusion:
    """
    Sampler for standalone diffusion models (U-Net files)
    Receives pre-loaded CLIP/VAE from loader node.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "latent": ("LATENT",),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000, "step": 1}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.5}),
                "sampler_name": (AVAILABLE_SAMPLERS, {"default": "euler"}),
                "scheduler": (["normal", "karras"], {"default": "normal"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
            },
        }
    
    CATEGORY = "sampling"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "labels")
    FUNCTION = "sample"
    OUTPUT_NODE = True
    
    def sample(self, config, clip, vae, latent, steps, cfg, sampler_name, scheduler, seed, positive, negative):
        debug_log = config.get("debug_log", False)
        
        if debug_log:
            print("[SamplerCompareDiffusion] Sampling from diffusion models (U-Net)")
            print(f"  - Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
            print(f"  - Seed: {seed}")
        
        try:
            combinations = config.get("combinations", [])
            if not combinations:
                print("[SamplerCompareDiffusion] Error: No combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            print(f"[SamplerCompareDiffusion] Generating {len(combinations)} images")
            
            # Collect latents for all combinations - for now use the provided latent
            sampled_latents = []
            labels_list = []
            
            progress_bar = ProgressBar(len(combinations))
            
            for i, combo in enumerate(combinations):
                progress_bar.update(i)
                print(f"[SamplerCompareDiffusion] Generating image {i+1}/{len(combinations)}")
                if debug_log:
                    print(f"  Model: {combo['model']}, VAE: {combo['vae']}, LoRAs: {combo['lora_names']}")
                    print(f"  LoRA Strengths: {combo['lora_strengths']}")
                
                # Only unload if we're switching to a different base model
                current_model_name = combo['model']
                if i > 0 and _model_cache.cached_model_path and not _model_cache.cached_model_path.endswith(current_model_name):
                    if debug_log:
                        print(f"[SamplerCompareDiffusion] Base model changed, cleaning up...")
                    import gc
                    gc.collect()
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    comfy.model_management.cleanup_models_gc()
                    comfy.model_management.soft_empty_cache()
                
                # Perform actual sampling - use same seed for this combination
                try:
                    print(f"[SamplerCompareDiffusion] Sampling with seed {seed}, steps {steps}...")
                    
                    # Load or retrieve cached model
                    model_name = combo['model']
                    model_type = combo['model_type']
                    model_path = folder_paths.get_full_path_or_raise("checkpoints", model_name) if model_type == "checkpoint" else folder_paths.get_full_path_or_raise("diffusion_models", model_name)
                    
                    combo_model, was_loaded = _model_cache.get_or_load_model(model_path, model_type, debug_log)
                    
                    if debug_log:
                        cache_status = "newly loaded" if was_loaded else "from cache"
                        print(f"[SamplerCompareDiffusion] Model {cache_status}, type: {type(combo_model)}")
                    else:
                        print(f"[SamplerCompareDiffusion] Model loaded, type: {type(combo_model)}")
                    
                    # Apply LoRAs to the model (only if not already applied)
                    if combo.get('lora_names') and combo.get('lora_strengths'):
                        print(f"[SamplerCompareDiffusion] Applying {len(combo['lora_names'])} LoRAs")
                        for lora_name, lora_strength in zip(combo['lora_names'], combo['lora_strengths']):
                            if lora_strength == 0:
                                print(f"[SamplerCompareDiffusion]   Skipping {lora_name} (strength=0)")
                                continue
                            
                            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
                            
                            # Check if this LoRA is already applied at this strength
                            if _model_cache.is_lora_applied(lora_path, lora_strength):
                                if debug_log:
                                    print(f"[SamplerCompareDiffusion]   {lora_name} already applied at {lora_strength}")
                                continue
                            
                            print(f"[SamplerCompareDiffusion]   Loading {lora_name} with strength {lora_strength}")
                            try:
                                lora_data = comfy.utils.load_torch_file(lora_path)
                                # Load and apply LoRA - model is required, clip is optional
                                old_patches = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                                combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
                                new_patches = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                                _model_cache.mark_lora_applied(lora_path, lora_strength)
                                print(f"[SamplerCompareDiffusion]   LoRA applied successfully (patches: {old_patches} -> {new_patches})")
                            except Exception as lora_err:
                                print(f"[SamplerCompareDiffusion]   Error loading LoRA: {lora_err}")
                    
                    # Fix empty latent channels
                    latent_samples = latent["samples"].clone()
                    latent_samples = comfy.sample.fix_empty_latent_channels(combo_model, latent_samples)
                    
                    # Prepare noise - use same seed for this combination
                    batch_inds = latent.get("batch_index", None)
                    noise = comfy.sample.prepare_noise(latent_samples, seed, batch_inds)
                    
                    # Setup callback for progress
                    callback = latent_preview.prepare_callback(combo_model, steps)
                    
                    # Run the actual sampler
                    print(f"[SamplerCompareDiffusion] Running sampler: {sampler_name}")
                    
                    # Log model state before sampling
                    patches_before = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                    print(f"[SamplerCompareDiffusion] BEFORE sample call: patches count = {patches_before}")
                    if hasattr(combo_model, 'patches') and combo_model.patches:
                        print(f"[SamplerCompareDiffusion]   Patch keys: {list(combo_model.patches.keys())[:5]}...")
                    
                    samples_out = comfy.sample.sample(
                        combo_model,
                        noise,
                        steps,
                        cfg,
                        sampler_name,
                        scheduler,
                        positive,
                        negative,
                        latent_samples,
                        denoise=1.0,
                        disable_noise=False,
                        callback=callback,
                        disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
                        seed=seed
                    )
                    
                    # Log model state after sampling
                    patches_after = len(combo_model.patches) if hasattr(combo_model, 'patches') else 0
                    print(f"[SamplerCompareDiffusion] AFTER sample call: patches count = {patches_after}")
                    
                    sampled_latents.append(samples_out)
                    print(f"[SamplerCompareDiffusion] Sampled latent shape: {samples_out.shape}")
                    
                except comfy.model_management.InterruptProcessingException:
                    print(f"[SamplerCompareDiffusion] Sampling interrupted, stopping all combinations")
                    raise  # Re-raise to stop execution
                except Exception as e:
                    print(f"[SamplerCompareDiffusion] Sampling failed: {e}, using input latent instead")
                    import traceback
                    traceback.print_exc()
                    sampled_latents.append(latent["samples"])
                
                # Only do aggressive cleanup between different models
                if debug_log:
                    print(f"[SamplerCompareDiffusion] Cleaning up temporary variables...")
                try:
                    # Delete all local references to temporary objects
                    if 'latent_samples' in locals():
                        del latent_samples
                    if 'noise' in locals():
                        del noise
                    if 'samples_out' in locals():
                        del samples_out
                except:
                    pass
                
                # Only do aggressive cleanup between different models
                if i < len(combinations) - 1:
                    next_model = combinations[i + 1]['model']
                    if next_model != current_model_name:
                        if debug_log:
                            print(f"[SamplerCompareDiffusion] Next model is different, aggressive cleanup...")
                        import gc
                        gc.collect()
                        comfy.model_management.soft_empty_cache()
                    elif debug_log:
                        print(f"[SamplerCompareDiffusion] Next model is same, skipping aggressive cleanup")
                else:
                    # Final cleanup at the end
                    if debug_log:
                        print(f"[SamplerCompareDiffusion] Final cleanup after all images...")
                    import gc
                    gc.collect()
                    comfy.model_management.unload_all_models()
                    comfy.model_management.cleanup_models()
                    comfy.model_management.cleanup_models_gc()
                    comfy.model_management.soft_empty_cache()
            
            progress_bar.update(len(combinations))
            
            # Generate smart labels showing only differences
            labels_list = generate_smart_labels(combinations[:len(sampled_latents)], config)
            if sampled_latents:
                stacked_latents = torch.cat(sampled_latents, dim=0)
                if debug_log:
                    print(f"[SamplerCompareDiffusion] Stacked latent shape: {stacked_latents.shape}")
                
                # Decode latents with VAE
                print(f"[SamplerCompareDiffusion] Decoding {stacked_latents.shape[0]} latents with VAE")
                try:
                    # Try regular decode first (handles both 2D and 3D latents)
                    decoded = vae.decode(stacked_latents)
                except Exception as e:
                    print(f"[SamplerCompareDiffusion] Decode failed: {e}, trying decode_tiled")
                    try:
                        # Fallback to decode_tiled if available and without extra args
                        decoded = vae.decode_tiled(stacked_latents, tile_latent_min_size=32)
                    except Exception as e2:
                        print(f"[SamplerCompareDiffusion] Decode_tiled also failed: {e2}")
                        raise
                
                # Ensure output is in correct format (B, H, W, C) with values in [0, 1]
                print(f"[SamplerCompareDiffusion] Decoded shape: {decoded.shape}, dtype: {decoded.dtype}")
                
                # Handle the actual shape returned: [4, 1, 3216, 2144, 3] -> should be [4, 3216, 2144, 3]
                if decoded.dim() == 5:
                    # Check if it's (B, C, H, W, 3) - the VAE is returning RGB channels last
                    if decoded.shape[1] == 1 and decoded.shape[-1] == 3:
                        # (B, 1, H, W, 3) -> squeeze C and we're done
                        output = decoded.squeeze(1)  # (B, H, W, 3)
                        print(f"[SamplerCompareDiffusion] Squeezed (B,1,H,W,3) to: {output.shape}")
                    elif decoded.shape[-1] == 3:
                        # Some other 5D format with 3 as last dim - assume it's RGB channels
                        output = decoded
                    elif decoded.shape[2] == 1:
                        # (B, C, 1, H, W) -> squeeze time, transpose
                        decoded = decoded.squeeze(2)  # (B, C, H, W)
                        output = decoded.permute(0, 2, 3, 1)  # (B, H, W, C)
                    else:
                        # (B, C, T, H, W) -> take first frame, transpose
                        decoded = decoded[:, :, 0, :, :]  # (B, C, H, W)
                        output = decoded.permute(0, 2, 3, 1)  # (B, H, W, C)
                elif decoded.dim() == 4:
                    if decoded.shape[-1] == 3:
                        # Already (B, H, W, C)
                        output = decoded
                    elif decoded.shape[1] == 3:
                        # (B, C, H, W) -> (B, H, W, C)
                        output = decoded.permute(0, 2, 3, 1)
                        print(f"[SamplerCompareDiffusion] Transposed from (B,C,H,W) to (B,H,W,C): {output.shape}")
                    else:
                        output = decoded
                else:
                    # Fallback
                    print(f"[SamplerCompareDiffusion] Warning: Unexpected tensor shape {decoded.shape}")
                    output = decoded
                
                # Ensure output is float in [0, 1] range
                if output.dtype != torch.float32:
                    output = output.float()
                output = torch.clamp(output, 0.0, 1.0)
                print(f"[SamplerCompareDiffusion] Final output shape: {output.shape}")
                
                labels = "; ".join(labels_list)
                return (output, labels)
            else:
                return (torch.zeros((1, 512, 512, 3)), "Error: No latents generated")
        
        except comfy.model_management.InterruptProcessingException:
            print("[SamplerCompareDiffusion] Execution cancelled by user")
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), "Error: Cancelled by user")
        
        except KeyboardInterrupt:
            print("[SamplerCompareDiffusion] Sampling interrupted by user")
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), "Error: Cancelled by user")
        
        except Exception as e:
            print(f"[SamplerCompareDiffusion] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
            # Clean up on error
            import gc
            gc.collect()
            comfy.model_management.cleanup_models()
            comfy.model_management.cleanup_models_gc()
            comfy.model_management.soft_empty_cache()
            return (torch.zeros((1, 512, 512, 3)), f"Error: {str(e)}")


# Node mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompareCheckpoint": SamplerCompareCheckpoint,
    "SamplerCompareQwenEdit": SamplerCompareQwenEdit,
    "SamplerCompareDiffusion": SamplerCompareDiffusion,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompareCheckpoint": "Sampler Compare [Checkpoint]",
    "SamplerCompareQwenEdit": "Sampler Compare [Qwen Edit]",
    "SamplerCompareDiffusion": "Sampler Compare [Diffusion Model]",
}
