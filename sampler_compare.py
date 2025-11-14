"""
Sampler Compare Node
Performs sampling across all model combinations from ModelCompareLoaders.
Outputs all generated images for grid comparison.
Supports different model types and pipelines (Checkpoint, Diffusion Model, etc.)
"""

import os
import torch
import numpy as np
from typing import Dict, List, Tuple, Any
import folder_paths
import comfy.sd
import comfy.model_management
from comfy.utils import ProgressBar
from .model_pipeline import PipelineFactory, ModelType


class SamplerCompare:
    """
    Samples across all model combinations defined in the config.
    Takes a latent input and generates samples for each combination.
    """

    def __init__(self):
        self.outputs = []
        self.combination_labels = []

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "latent": ("LATENT",),
                "steps": ("INT", {
                    "default": 20,
                    "min": 1,
                    "max": 10000,
                    "step": 1,
                }),
                "cfg": ("FLOAT", {
                    "default": 7.0,
                    "min": 0.0,
                    "max": 100.0,
                    "step": 0.5,
                }),
                "sampler_name": ([
                    "euler",
                    "euler_ancestral",
                    "heun",
                    "dpm_2",
                    "dpm_2_ancestral",
                    "dpm_fast",
                    "dpm_adaptive",
                    "lms",
                    "dpm_s",
                    "dpmpp_2s_ancestral",
                    "dpmpp_sde",
                    "dpmpp_sde_gpu",
                    "dpmpp_2m",
                    "dpmpp_2m_sde",
                    "dpmpp_2m_sde_gpu",
                    "dpmpp_3m_sde",
                    "dpmpp_3m_sde_gpu",
                    "ddpm",
                    "ddim",
                    "uni_pc",
                    "uni_pc_bh2",
                ], {
                    "default": "euler",
                }),
                "scheduler": ([
                    "normal",
                    "karras",
                    "exponential",
                    "simple",
                    "ddim_uniform",
                ], {
                    "default": "normal",
                }),
                "seed": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 0xffffffffffffffff,
                }),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
            },
            "optional": {
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "model_sampling": ("MODEL_SAMPLING",),  # For specialized models like AuraFlow
                "cfg_norm": ("CFG_NORM",),               # For specialized models
            },
        }

    CATEGORY = "sampling"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("images", "labels")
    FUNCTION = "sample_all_combinations"
    OUTPUT_NODE = True

    def sample_all_combinations(
        self,
        config: Dict[str, Any],
        latent: Dict[str, torch.Tensor],
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        seed: int,
        positive: List,
        negative: List,
        model=None,
        clip=None,
        vae=None,
        model_sampling=None,
        cfg_norm=None,
    ) -> Tuple[torch.Tensor, str]:
        """
        Sample across all combinations of models defined in config.
        Returns concatenated images and their labels.
        """
        
        combinations = config.get("combinations", [])
        if not combinations:
            print("[SamplerCompare] Warning: No combinations in config")
            # Return empty image tensor
            empty_tensor = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            return (empty_tensor, "No combinations")

        all_images = []
        all_labels = []
        
        print(f"[SamplerCompare] Sampling {len(combinations)} combinations...")
        pbar = ProgressBar(len(combinations))

        for idx, combination in enumerate(combinations):
            try:
                # Load models for this combination using pipeline system
                ckpt_name = combination.get("checkpoint")
                ckpt_type = combination.get("checkpoint_type")
                vae_name = combination.get("vae")
                text_enc_name = combination.get("text_encoder")
                lora_strengths = combination.get("lora_strengths")
                lora_names = combination.get("lora_names", [])

                # Get appropriate pipeline for this model
                if ckpt_name:
                    pipeline = PipelineFactory.get_pipeline(ckpt_name, ckpt_type or "checkpoint")
                    print(f"[SamplerCompare] Using {pipeline.__class__.__name__} for {ckpt_name}")
                    
                    # Load models through pipeline
                    model, clip, vae_loaded = pipeline.load_models(
                        clip=clip,
                        vae=vae,
                        model_sampling=model_sampling,
                        cfg_norm=cfg_norm
                    )
                    
                    if vae_name or vae_loaded:
                        vae = vae_loaded
                else:
                    if not model or not clip:
                        print("[SamplerCompare] Error: No model/clip provided and no checkpoint in combination")
                        continue

                # Load VAE if specified
                if vae_name:
                    print(f"[SamplerCompare] Loading VAE: {vae_name}")
                    vae = self._load_vae(vae_name)
                elif not vae:
                    print("[SamplerCompare] Warning: No VAE available for sampling")
                    continue

                # Load LoRAs if specified
                if lora_names and lora_strengths:
                    print(f"[SamplerCompare] Loading LoRAs: {lora_names} with strengths {lora_strengths}")
                    model, clip = self._load_loras(
                        model, clip, lora_names, lora_strengths
                    )

                # Perform sampling
                print(f"[SamplerCompare] Sampling with seed {seed + idx}")
                sampled_latent = self._sample_latent(
                    model=model,
                    latent=latent,
                    steps=steps,
                    cfg=cfg,
                    sampler_name=sampler_name,
                    scheduler=scheduler,
                    seed=seed + idx,
                    positive=positive,
                    negative=negative,
                )

                # Decode latent to image
                if vae:
                    print(f"[SamplerCompare] Decoding latent with VAE")
                    image = self._decode_latent(sampled_latent, vae)
                    all_images.append(image)
                    all_labels.append(combination.get("label", f"combination_{idx}"))
                else:
                    print("[SamplerCompare] Error: Cannot decode without VAE")
                    continue

            except Exception as e:
                print(f"[SamplerCompare] Error processing combination {idx}: {e}")
                import traceback
                traceback.print_exc()
                continue

            pbar.update(1)

        if not all_images:
            print("[SamplerCompare] No successful samples generated")
            empty_tensor = torch.zeros((1, 64, 64, 3), dtype=torch.float32)
            return (empty_tensor, "No successful samples")

        # Concatenate all images
        output_image = torch.cat(all_images, dim=0)
        labels_str = "\n".join(all_labels)

        print(f"[SamplerCompare] Generated {len(all_images)} samples")
        return (output_image, labels_str)

    @staticmethod
    def _load_checkpoint(checkpoint_name: str) -> Tuple[Any, Any, Any]:
        """Load a checkpoint and return model, clip, and vae."""
        import comfy.sd
        ckpt_path = folder_paths.get_full_path("checkpoints", checkpoint_name)
        out = comfy.sd.load_checkpoint_guess_config(
            ckpt_path,
            output_vae=True,
            output_clip=True,
            output_clipvision=False,
            embedding_directory=folder_paths.get_folder_names("embeddings"),
        )
        return out[0], out[1], out[2]  # model, clip, vae

    @staticmethod
    def _load_vae(vae_name: str) -> Any:
        """Load a VAE."""
        import comfy.sd
        vae_path = folder_paths.get_full_path("vae", vae_name)
        vae = comfy.sd.load_vae(vae_path)
        return vae

    @staticmethod
    def _load_loras(
        model: Any,
        clip: Any,
        lora_names: List[str],
        strengths: Tuple[float, ...],
    ) -> Tuple[Any, Any]:
        """Load LoRAs and apply strengths."""
        import comfy.sd
        
        for lora_name, strength in zip(lora_names, strengths):
            lora_path = folder_paths.get_full_path("loras", lora_name)
            lora = comfy.sd.load_lora(lora_path)
            
            # Apply LoRA to model and clip
            model, clip = comfy.sd.load_lora_for_models(
                model, clip, lora, strength, strength
            )
        
        return model, clip

    @staticmethod
    def _sample_latent(
        model,
        latent,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        seed: int,
        positive,
        negative,
    ) -> torch.Tensor:
        """Perform KSampler step."""
        import comfy.samplers
        
        # This is a simplified sampling step; in production use actual KSampler
        # For now, we'll return a dummy latent
        # Real implementation should use comfy.samplers.KSampler
        
        # Get the sampler
        sampler = comfy.samplers.KSampler(
            device=comfy.model_management.get_torch_device(),
            model=model,
            steps=steps,
            sampler=sampler_name,
            scheduler=scheduler,
            denoise=1.0,
        )

        # Perform sampling (simplified; real version needs proper callback handling)
        sampled = sampler.sample(
            conditioning_pos=positive,
            conditioning_neg=negative,
            latent_image=latent["samples"],
            seed=seed,
            noise_mask=None,
            denoise_mask=None,
            force_full_denoise=False,
            sigmas=None,
            disable_noise=False,
            start_step=0,
            last_step=steps,
            force_sigma_min=False,
            force_sigma_max=False,
            cfg=cfg,
            base_steps=steps,
            denoise_start=0,
            denoise=1.0,
            preview_latent=True,
        )
        
        return sampled

    @staticmethod
    def _decode_latent(latent: torch.Tensor, vae) -> torch.Tensor:
        """Decode latent to image using VAE."""
        decoded = vae.decode(latent)
        
        # Clamp to valid range and convert to uint8
        image = decoded.clamp(-1, 1)
        image = (image + 1) / 2  # Normalize from [-1, 1] to [0, 1]
        
        return image


# Node mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompare": SamplerCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompare": "Sampler Compare",
}
