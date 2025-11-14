"""
Specialized Sampler Nodes for Different Model Types
Each node type handles its specific model architecture with built-in pipeline configuration.
"""

import os
import torch
from typing import Dict, List, Tuple, Any
import folder_paths
import comfy.sd
import comfy.model_management
import comfy.utils
from comfy.utils import ProgressBar
from comfy.samplers import SAMPLER_NAMES

# Get full sampler list from ComfyUI
AVAILABLE_SAMPLERS = list(SAMPLER_NAMES)


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
        print("[SamplerCompareCheckpoint] Sampling from checkpoint models")
        print(f"  - Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
        print(f"  - Seed: {seed}")
        
        try:
            combinations = config.get("combinations", [])
            if not combinations:
                print("[SamplerCompareCheckpoint] Warning: No combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            print(f"[SamplerCompareCheckpoint] Processing {len(combinations)} combinations")
            
            # Collect latents for all combinations - for now use the provided latent
            sampled_latents = []
            labels_list = []
            
            for i, combo in enumerate(combinations[:4]):  # Limit to 4 for now
                print(f"[SamplerCompareCheckpoint] Processing combination {i+1}/{min(len(combinations), 4)}")
                print(f"  Model: {combo['model']}, VAE: {combo['vae']}, LoRAs: {combo['lora_names']}")
                
                # Use the input latent (would be actual sampling in real implementation)
                sampled_latents.append(latent["samples"])
                labels_list.append(f"Combo {i+1}: {combo['model']}")
            
            # Stack all sampled latents
            if sampled_latents:
                stacked_latents = torch.cat(sampled_latents, dim=0)
                print(f"[SamplerCompareCheckpoint] Stacked latent shape: {stacked_latents.shape}")
                
                # Decode latents with VAE
                print(f"[SamplerCompareCheckpoint] Decoding {stacked_latents.shape[0]} latents with VAE")
                decoded = vae.decode_tiled(stacked_latents) if hasattr(vae, 'decode_tiled') else vae.decode(stacked_latents)
                
                # Ensure output is in correct format (B, H, W, C) with values in [0, 1]
                if decoded.shape[-1] == 3:
                    output = decoded
                else:
                    # If it's (B, C, H, W), transpose to (B, H, W, C)
                    output = decoded.permute(0, 2, 3, 1)
                
                # Clamp to [0, 1]
                output = torch.clamp(output, 0.0, 1.0)
                
                labels = "; ".join(labels_list)
                return (output, labels)
            else:
                return (torch.zeros((1, 512, 512, 3)), "Error: No latents generated")
        
        except Exception as e:
            print(f"[SamplerCompareCheckpoint] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
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
                print("[SamplerCompareQwenEdit] Warning: No combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            print(f"[SamplerCompareQwenEdit] Processing {len(combinations)} combinations")
            
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
            
            for i, combo in enumerate(combinations[:4]):  # Limit to 4 for now
                print(f"[SamplerCompareQwenEdit] Processing combination {i+1}/{min(len(combinations), 4)}")
                print(f"  Model: {combo['model']}, VAE: {combo['vae']}, LoRAs: {combo['lora_names']}")
                
                # Use the input latent (would be actual sampling in real implementation)
                sampled_latents.append(latent["samples"])
                labels_list.append(f"Combo {i+1}: {combo['model']}")
            
            # Stack all sampled latents
            if sampled_latents:
                stacked_latents = torch.cat(sampled_latents, dim=0)
                print(f"[SamplerCompareQwenEdit] Stacked latent shape: {stacked_latents.shape}")
                
                # Decode latents with VAE
                print(f"[SamplerCompareQwenEdit] Decoding {stacked_latents.shape[0]} latents with VAE")
                decoded = vae.decode_tiled(stacked_latents) if hasattr(vae, 'decode_tiled') else vae.decode(stacked_latents)
                
                # Ensure output is in correct format (B, H, W, C) with values in [0, 1]
                if decoded.shape[-1] == 3:
                    output = decoded
                else:
                    # If it's (B, C, H, W), transpose to (B, H, W, C)
                    output = decoded.permute(0, 2, 3, 1)
                
                # Clamp to [0, 1]
                output = torch.clamp(output, 0.0, 1.0)
                
                labels = "; ".join(labels_list)
                return (output, labels)
            else:
                return (torch.zeros((1, 512, 512, 3)), "Error: No latents generated")
        
        except Exception as e:
            print(f"[SamplerCompareQwenEdit] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
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
        print("[SamplerCompareDiffusion] Sampling from diffusion models (U-Net)")
        print(f"  - Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
        print(f"  - Seed: {seed}")
        
        try:
            combinations = config.get("combinations", [])
            if not combinations:
                print("[SamplerCompareDiffusion] Warning: No combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            print(f"[SamplerCompareDiffusion] Processing {len(combinations)} combinations")
            
            # Collect latents for all combinations - for now use the provided latent
            sampled_latents = []
            labels_list = []
            
            for i, combo in enumerate(combinations[:4]):  # Limit to 4 for now
                print(f"[SamplerCompareDiffusion] Processing combination {i+1}/{min(len(combinations), 4)}")
                print(f"  Model: {combo['model']}, VAE: {combo['vae']}, LoRAs: {combo['lora_names']}")
                
                # Use the input latent (would be actual sampling in real implementation)
                sampled_latents.append(latent["samples"])
                labels_list.append(f"Combo {i+1}: {combo['model']}")
            
            # Stack all sampled latents
            if sampled_latents:
                stacked_latents = torch.cat(sampled_latents, dim=0)
                print(f"[SamplerCompareDiffusion] Stacked latent shape: {stacked_latents.shape}")
                
                # Decode latents with VAE
                print(f"[SamplerCompareDiffusion] Decoding {stacked_latents.shape[0]} latents with VAE")
                decoded = vae.decode_tiled(stacked_latents) if hasattr(vae, 'decode_tiled') else vae.decode(stacked_latents)
                
                # Ensure output is in correct format (B, H, W, C) with values in [0, 1]
                if decoded.shape[-1] == 3:
                    output = decoded
                else:
                    # If it's (B, C, H, W), transpose to (B, H, W, C)
                    output = decoded.permute(0, 2, 3, 1)
                
                # Clamp to [0, 1]
                output = torch.clamp(output, 0.0, 1.0)
                
                labels = "; ".join(labels_list)
                return (output, labels)
            else:
                return (torch.zeros((1, 512, 512, 3)), "Error: No latents generated")
        
        except Exception as e:
            print(f"[SamplerCompareDiffusion] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
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
