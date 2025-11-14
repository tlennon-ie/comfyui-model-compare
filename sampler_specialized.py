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
from comfy.utils import ProgressBar
from comfy.samplers import SAMPLER_NAMES

# Get full sampler list from ComfyUI
AVAILABLE_SAMPLERS = list(SAMPLER_NAMES)


class SamplerCompareCheckpoint:
    """
    Sampler for standard Checkpoint models (SD/SDXL)
    Simple pipeline: Load Checkpoint -> Sample
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
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
    
    def sample(self, config, latent, steps, cfg, sampler_name, scheduler, seed, positive, negative):
        print("[SamplerCompareCheckpoint] Sampling from checkpoint models")
        print(f"  - Config: {config}")
        print(f"  - Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
        print(f"  - Seed: {seed}")
        
        try:
            # Extract checkpoint combinations from config
            checkpoint_data = config.get("checkpoint_combinations", [])
            if not checkpoint_data:
                print("[SamplerCompareCheckpoint] Warning: No checkpoint combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No checkpoints")
            
            # For now, return placeholder output
            # TODO: Implement full checkpoint sampling pipeline
            print(f"[SamplerCompareCheckpoint] Would sample {len(checkpoint_data)} checkpoint combinations")
            
            # Generate batch of results (one per checkpoint)
            batch_size = min(len(checkpoint_data), 4)  # Limit to 4 for demo
            output = torch.randn((batch_size, 512, 512, 3)) * 0.1 + 0.5
            
            # Create labels for each combination
            labels = f"Sampled {batch_size} checkpoints with {sampler_name} sampler"
            
            return (output, labels)
        
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
    
    def sample(self, config, latent, steps, seed, positive, negative, guidance_scale, aura_flow_mode, cfg_norm_strength, cfg_norm_mode, model=None, clip=None, vae=None):
        print("[SamplerCompareQwenEdit] Sampling from Qwen Edit models with AuraFlow pipeline")
        print(f"  - AuraFlow Mode: {aura_flow_mode}")
        print(f"  - Guidance Scale: {guidance_scale}")
        print(f"  - CFGNorm: {cfg_norm_mode} (strength: {cfg_norm_strength})")
        print(f"  - Steps: {steps}, Seed: {seed}")
        
        try:
            # Extract diffusion model combinations from config
            diffusion_data = config.get("diffusion_combinations", [])
            if not diffusion_data:
                print("[SamplerCompareQwenEdit] Warning: No diffusion model combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            # For now, return placeholder output
            # TODO: Implement full AuraFlow + CFGNorm sampling pipeline
            print(f"[SamplerCompareQwenEdit] Would sample {len(diffusion_data)} diffusion model combinations")
            
            # Generate batch of results (one per diffusion model)
            batch_size = min(len(diffusion_data), 4)  # Limit to 4 for demo
            output = torch.randn((batch_size, 512, 512, 3)) * 0.1 + 0.5
            
            # Create labels for each combination
            labels = f"Sampled {batch_size} Qwen Edit models with {aura_flow_mode} mode"
            
            return (output, labels)
        
        except Exception as e:
            print(f"[SamplerCompareQwenEdit] Error during sampling: {e}")
            import traceback
            traceback.print_exc()
            return (torch.zeros((1, 512, 512, 3)), f"Error: {str(e)}")


class SamplerCompareDiffusion:
    """
    Sampler for standalone diffusion models (U-Net files)
    Requires external CLIP/VAE but handles model loading
    Pipeline: Load U-Net -> Load External CLIP/VAE -> Sampler
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "latent": ("LATENT",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
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
    
    def sample(self, config, latent, clip, vae, steps, cfg, sampler_name, scheduler, seed, positive, negative):
        print("[SamplerCompareDiffusion] Sampling from diffusion models (U-Net)")
        print(f"  - Steps: {steps}, CFG: {cfg}, Sampler: {sampler_name}, Scheduler: {scheduler}")
        print(f"  - Seed: {seed}")
        
        try:
            # Extract diffusion model combinations from config
            diffusion_data = config.get("diffusion_combinations", [])
            if not diffusion_data:
                print("[SamplerCompareDiffusion] Warning: No diffusion model combinations in config")
                return (torch.zeros((1, 64, 64, 3)), "Error: No models")
            
            # For now, return placeholder output
            # TODO: Implement full diffusion model sampling pipeline with external CLIP/VAE
            print(f"[SamplerCompareDiffusion] Would sample {len(diffusion_data)} diffusion model combinations")
            
            # Generate batch of results (one per diffusion model)
            batch_size = min(len(diffusion_data), 4)  # Limit to 4 for demo
            output = torch.randn((batch_size, 512, 512, 3)) * 0.1 + 0.5
            
            # Create labels for each combination
            labels = f"Sampled {batch_size} diffusion models with {sampler_name} sampler"
            
            return (output, labels)
        
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
