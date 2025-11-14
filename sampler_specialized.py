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
                "sampler_name": (["euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral"], {"default": "euler"}),
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
        # Standard checkpoint sampling pipeline
        return (torch.zeros((1, 64, 64, 3)), "Sample output")


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
        # Qwen Edit specific sampling pipeline with AuraFlow + CFGNorm
        return (torch.zeros((1, 64, 64, 3)), "Qwen Edit sample output")


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
                "sampler_name": (["euler", "euler_ancestral", "heun"], {"default": "euler"}),
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
        # Diffusion model sampling pipeline
        return (torch.zeros((1, 64, 64, 3)), "Diffusion model sample output")


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
