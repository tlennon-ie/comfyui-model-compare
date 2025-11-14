"""
Model Pipeline Manager
Handles loading and pipeline setup for different model types.
Provides model-specific sampling configurations.
"""

import os
from typing import Dict, Any, Tuple, Optional
import folder_paths
import comfy.sd
import comfy.model_management


class ModelType:
    """Enum for supported model types"""
    CHECKPOINT = "checkpoint"           # Full SD/SDXL model
    DIFFUSION_MODEL = "diffusion_model" # Standalone U-Net
    CUSTOM = "custom"                   # Custom/specialized models


class PipelineTemplate:
    """Base class for model-specific pipelines"""
    
    def __init__(self, model_name: str, model_type: str):
        self.model_name = model_name
        self.model_type = model_type
        self.model = None
        self.clip = None
        self.vae = None
        
    def load_models(self, **kwargs) -> Tuple[Any, Any, Any]:
        """Load all required models for this pipeline. Returns (model, clip, vae)"""
        raise NotImplementedError
        
    def get_required_inputs(self) -> Dict[str, str]:
        """Return dict of required input names and their types"""
        raise NotImplementedError


class CheckpointPipeline(PipelineTemplate):
    """Pipeline for standard checkpoint models (SD/SDXL)"""
    
    def __init__(self, checkpoint_name: str):
        super().__init__(checkpoint_name, ModelType.CHECKPOINT)
        
    def load_models(self, **kwargs) -> Tuple[Any, Any, Any]:
        """Load checkpoint and extract model, clip, vae"""
        ckpt_path = folder_paths.get_full_path("checkpoints", self.model_name)
        out = comfy.sd.load_checkpoint_guess_config(
            ckpt_path,
            output_vae=True,
            output_clip=True,
            output_clipvision=False,
            embedding_directory=folder_paths.get_folder_names("embeddings"),
        )
        self.model, self.clip, self.vae = out[0], out[1], out[2]
        return self.model, self.clip, self.vae
        
    def get_required_inputs(self) -> Dict[str, str]:
        return {"model": "MODEL", "clip": "CLIP", "vae": "VAE"}


class DiffusionModelPipeline(PipelineTemplate):
    """Pipeline for standalone diffusion models (U-Net from diffusion_models/unet folder)"""
    
    def __init__(self, model_name: str):
        super().__init__(model_name, ModelType.DIFFUSION_MODEL)
        
    def load_models(self, **kwargs) -> Tuple[Any, Any, Any]:
        """Load diffusion model - user must provide CLIP and VAE separately"""
        model_path = folder_paths.get_full_path("diffusion_models", self.model_name)
        
        # Load the raw model
        try:
            self.model = comfy.sd.load_diffusion_model(model_path)
        except:
            # Fallback: load as state dict and wrap
            import torch
            state_dict = torch.load(model_path, weights_only=True)
            # This is a simplified approach - actual implementation depends on model architecture
            print(f"[ModelCompare] Warning: Diffusion model {self.model_name} requires manual pipeline setup")
            self.model = None
            
        # These must be provided by user or from another node
        self.clip = kwargs.get("clip")
        self.vae = kwargs.get("vae")
        
        return self.model, self.clip, self.vae
        
    def get_required_inputs(self) -> Dict[str, str]:
        return {
            "model": "MODEL",
            "clip": "CLIP (required)",
            "vae": "VAE (required)",
            "lora": "LoRA (optional)"
        }


class QwenEditPipeline(PipelineTemplate):
    """Pipeline for Qwen Edit diffuser - special handling for AuraFlow sampling"""
    
    def __init__(self, model_name: str):
        super().__init__(model_name, ModelType.CUSTOM)
        self.model_sampling = None
        self.cfg_norm = None
        
    def load_models(self, model_sampling=None, cfg_norm=None, **kwargs) -> Tuple[Any, Any, Any]:
        """Load Qwen Edit model with required middleware nodes"""
        model_path = folder_paths.get_full_path("diffusion_models", self.model_name)
        
        # Load base model
        try:
            self.model = comfy.sd.load_diffusion_model(model_path)
        except:
            self.model = None
            
        self.model_sampling = model_sampling
        self.cfg_norm = cfg_norm
        self.clip = kwargs.get("clip")
        self.vae = kwargs.get("vae")
        
        if not self.model:
            print(f"[ModelCompare] Error: Could not load Qwen Edit model {self.model_name}")
            
        return self.model, self.clip, self.vae
        
    def get_required_inputs(self) -> Dict[str, str]:
        return {
            "model": "MODEL",
            "clip": "CLIP (required)",
            "vae": "VAE (required)",
            "model_sampling": "MODEL_SAMPLING (AuraFlow - required)",
            "cfg_norm": "CFG_NORM (required)",
            "lora": "LoRA (optional)"
        }


class PipelineFactory:
    """Factory for creating appropriate pipeline for a given model"""
    
    _CUSTOM_PIPELINES = {
        # Model name patterns -> Pipeline class
        "qwen_edit": QwenEditPipeline,
        "aura_flow": QwenEditPipeline,  # Similar pipeline
    }
    
    @staticmethod
    def get_pipeline(model_name: str, model_type: str) -> PipelineTemplate:
        """Get appropriate pipeline for model"""
        
        model_lower = model_name.lower()
        
        # Check for custom pipelines
        for pattern, pipeline_class in PipelineFactory._CUSTOM_PIPELINES.items():
            if pattern in model_lower:
                return pipeline_class(model_name)
        
        # Default based on model_type
        if model_type == ModelType.CHECKPOINT:
            return CheckpointPipeline(model_name)
        elif model_type == ModelType.DIFFUSION_MODEL:
            return DiffusionModelPipeline(model_name)
        else:
            # Fallback to checkpoint
            return CheckpointPipeline(model_name)
    
    @staticmethod
    def register_custom_pipeline(pattern: str, pipeline_class):
        """Register a custom pipeline for model name patterns"""
        PipelineFactory._CUSTOM_PIPELINES[pattern.lower()] = pipeline_class
