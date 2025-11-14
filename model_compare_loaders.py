"""
Model Compare Loaders Node - Loads and compares multiple models
"""

import os
import itertools
from typing import List, Dict, Tuple, Any
import folder_paths
import comfy.sd
import comfy.clip_vision
import comfy.utils


class ModelCompareLoaders:
    """
    Combined loader node that loads models and outputs them.
    Enforces minimum of 1 checkpoint/diffusion, 1 VAE, 1 CLIP.
    """

    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the node."""
        checkpoints = folder_paths.get_filename_list("checkpoints")
        diffusion_models = folder_paths.get_filename_list("diffusion_models")
        vaes = folder_paths.get_filename_list("vae")
        clip_models = folder_paths.get_filename_list("clip")
        loras = folder_paths.get_filename_list("loras")
        
        # Get available CLIP types from comfy.sd
        clip_types = ["default"]  # Will add more if available
        if hasattr(comfy.sd, 'SUPPORTED_MODELS'):
            # Try to extract clip types from supported models
            pass

        inputs = {
            "required": {
                # Base model - consolidated checkpoint/diffusion picker
                "base_model": (
                    ["NONE"] + [f"[Checkpoint] {c}" for c in checkpoints] + 
                    [f"[Diffusion] {d}" for d in diffusion_models],
                    {"default": "[Checkpoint] " + checkpoints[0] if checkpoints else "NONE"},
                ),
                # VAE - required minimum 1
                "vae": (
                    ["NONE"] + vaes,
                    {"default": vaes[0] if vaes else "NONE"},
                ),
                # CLIP - required minimum 1
                "clip_model": (
                    ["NONE"] + clip_models,
                    {"default": clip_models[0] if clip_models else "NONE"},
                ),
                "clip_type": (
                    ["default", "stable_diffusion", "stable_diffusion_xl", "flux", "qwen_image"],
                    {"default": "default"},
                ),
                # Number of variations
                "num_model_variations": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                }),
                "num_vae_variations": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                }),
                "num_loras": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                }),
            },
            "optional": {},
        }

        # Add additional model variation widgets (up to 10)
        for i in range(1, 10):
            inputs["optional"][f"model_variation_{i}"] = (
                ["NONE"] + [f"[Checkpoint] {c}" for c in checkpoints] + 
                [f"[Diffusion] {d}" for d in diffusion_models],
                {"default": "NONE"},
            )

        # Add VAE variation widgets (up to 5)
        for i in range(1, 5):
            inputs["optional"][f"vae_variation_{i}"] = (
                ["NONE"] + vaes,
                {"default": "NONE"},
            )

        # Add LoRA selection and strength widgets (up to 10)
        for i in range(10):
            inputs["optional"][f"lora_{i}"] = (
                ["NONE"] + loras,
                {"default": "NONE"},
            )
            inputs["optional"][f"lora_{i}_strengths"] = (
                "STRING",
                {
                    "default": "1.0",
                    "multiline": False,
                    "tooltip": "Comma-separated strength values (e.g., '0.0, 0.5, 1.0, 1.5')",
                },
            )

        return inputs

    CATEGORY = "model"
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG", "MODEL", "CLIP", "VAE")
    RETURN_NAMES = ("config", "base_model", "base_clip", "base_vae")
    FUNCTION = "load_models"
    OUTPUT_NODE = True

    def load_models(
        self,
        base_model: str,
        vae: str,
        clip_model: str,
        clip_type: str,
        num_model_variations: int,
        num_vae_variations: int,
        num_loras: int,
        **kwargs
    ) -> Tuple[Dict[str, Any], Any, Any, Any]:
        """
        Load base models and create configuration for comparisons.
        """
        
        # Parse base_model (format: "[Type] filename")
        base_model_type, base_model_name = self._parse_model_selector(base_model)
        
        # Load the base models
        print(f"[ModelCompareLoaders] Loading base model: {base_model_name} ({base_model_type})")
        base_model_obj = self._load_model(base_model_name, base_model_type)
        
        print(f"[ModelCompareLoaders] Loading base VAE: {vae}")
        base_vae_obj = self._load_vae(vae)
        
        print(f"[ModelCompareLoaders] Loading base CLIP: {clip_model}")
        base_clip_obj = self._load_clip(clip_model, clip_type)
        
        # Collect model variations
        model_variations = [{"name": base_model_name, "type": base_model_type}]
        for i in range(1, num_model_variations):
            key = f"model_variation_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                mtype, mname = self._parse_model_selector(kwargs[key])
                model_variations.append({"name": mname, "type": mtype})
        
        # Collect VAE variations
        vae_variations = [vae]
        for i in range(1, num_vae_variations):
            key = f"vae_variation_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                vae_variations.append(kwargs[key])
        
        # Collect LoRAs
        loras = []
        for i in range(num_loras):
            lora_key = f"lora_{i}"
            strengths_key = f"lora_{i}_strengths"
            
            if lora_key in kwargs and kwargs[lora_key] != "NONE":
                lora_name = kwargs[lora_key]
                strengths_str = kwargs.get(strengths_key, "1.0")
                
                try:
                    strengths = [
                        float(s.strip())
                        for s in strengths_str.split(",")
                        if s.strip()
                    ]
                except ValueError:
                    print(f"[ModelCompareLoaders] Warning: Invalid strength values for {lora_name}")
                    strengths = [1.0]

                loras.append({
                    "name": lora_name,
                    "strengths": strengths,
                })
        
        # Create config
        config = {
            "model_variations": model_variations,
            "vae_variations": vae_variations,
            "loras": loras,
            "clip_type": clip_type,
            "base_model_type": base_model_type,
            "base_model_name": base_model_name,
        }
        
        # Compute all combinations
        config["combinations"] = self._compute_combinations(config)
        
        print(f"[ModelCompareLoaders] Config created:")
        print(f"  - Model variations: {len(model_variations)}")
        print(f"  - VAE variations: {len(vae_variations)}")
        print(f"  - LoRAs: {len(loras)}")
        print(f"  - Total combinations: {len(config['combinations'])}")
        
        return (config, base_model_obj, base_clip_obj, base_vae_obj)
    
    @staticmethod
    def _parse_model_selector(selector: str) -> Tuple[str, str]:
        """Parse model selector format: '[Type] filename' """
        if selector.startswith("[Checkpoint]"):
            return "checkpoint", selector.replace("[Checkpoint] ", "").strip()
        elif selector.startswith("[Diffusion]"):
            return "diffusion_model", selector.replace("[Diffusion] ", "").strip()
        return "checkpoint", selector
    
    @staticmethod
    def _load_model(model_name: str, model_type: str) -> Any:
        """Load a checkpoint or diffusion model."""
        if model_type == "diffusion_model":
            # Load diffusion model (U-Net only)
            model_path = folder_paths.get_full_path("diffusion_models", model_name)
            # For now, return a placeholder - full loading happens in sampler
            return {"type": "diffusion_model", "path": model_path}
        else:
            # Load checkpoint
            model_path = folder_paths.get_full_path("checkpoints", model_name)
            sd = comfy.sd.load_checkpoint_guess_config(model_path, output_vae=False, output_clip=False, embedding_directory=None)
            return sd[0]  # Return just the model
    
    @staticmethod
    def _load_vae(vae_name: str) -> Any:
        """Load a VAE model."""
        # Handle special VAE names
        if vae_name == "pixel_space":
            import torch
            sd = {}
            sd["pixel_space_vae"] = torch.tensor(1.0)
        elif vae_name in ["taesd", "taesdxl", "taesd3", "taef1"]:
            # Load TAESD (approximate) VAE
            sd = {}
            approx_vaes = folder_paths.get_filename_list("vae_approx")
            
            encoder = next(filter(lambda a: a.startswith("{}_encoder.".format(vae_name)), approx_vaes))
            decoder = next(filter(lambda a: a.startswith("{}_decoder.".format(vae_name)), approx_vaes))
            
            enc_path = folder_paths.get_full_path_or_raise("vae_approx", encoder)
            dec_path = folder_paths.get_full_path_or_raise("vae_approx", decoder)
            
            enc = comfy.utils.load_torch_file(enc_path)
            for k in enc:
                sd["taesd_encoder.{}".format(k)] = enc[k]

            dec = comfy.utils.load_torch_file(dec_path)
            for k in dec:
                sd["taesd_decoder.{}".format(k)] = dec[k]

            import torch
            if vae_name == "taesd":
                sd["vae_scale"] = torch.tensor(0.18215)
                sd["vae_shift"] = torch.tensor(0.0)
            elif vae_name == "taesdxl":
                sd["vae_scale"] = torch.tensor(0.13025)
                sd["vae_shift"] = torch.tensor(0.0)
            elif vae_name == "taesd3":
                sd["vae_scale"] = torch.tensor(1.5305)
                sd["vae_shift"] = torch.tensor(0.0609)
            elif vae_name == "taef1":
                sd["vae_scale"] = torch.tensor(0.3611)
                sd["vae_shift"] = torch.tensor(0.1159)
        else:
            # Load standard VAE
            vae_path = folder_paths.get_full_path_or_raise("vae", vae_name)
            sd = comfy.utils.load_torch_file(vae_path)
        
        # Create VAE object from state dict
        vae = comfy.sd.VAE(sd=sd)
        vae.throw_exception_if_invalid()
        return vae
    
    @staticmethod
    def _load_clip(clip_name: str, clip_type: str) -> Any:
        """Load a CLIP model."""
        clip_path = folder_paths.get_full_path_or_raise("text_encoders", clip_name)
        
        # Map clip_type to CLIPType enum
        clip_type_enum = getattr(comfy.sd.CLIPType, clip_type.upper(), comfy.sd.CLIPType.STABLE_DIFFUSION)
        
        # Load CLIP with the specified type
        clip = comfy.sd.load_clip(
            ckpt_paths=[clip_path],
            embedding_directory=folder_paths.get_folder_paths("embeddings"),
            clip_type=clip_type_enum
        )
        
        return clip
    
    @staticmethod
    def _compute_combinations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Compute all possible combinations."""
        models = config["model_variations"]
        vaes = config["vae_variations"]
        loras = config["loras"]
        
        # Compute LoRA strength combinations
        lora_strength_combos = []
        if loras:
            strength_lists = [l["strengths"] for l in loras]
            lora_strength_combos = list(itertools.product(*strength_lists))
        else:
            lora_strength_combos = [None]
        
        # Generate all combinations
        combinations = []
        for model, vae, lora_strengths in itertools.product(
            models, vaes, lora_strength_combos
        ):
            combination = {
                "model": model["name"],
                "model_type": model["type"],
                "vae": vae,
                "lora_strengths": lora_strengths,
                "lora_names": [l["name"] for l in loras] if loras else [],
            }
            combinations.append(combination)
        
        return combinations


# Node mappings
NODE_CLASS_MAPPINGS = {
    "ModelCompareLoaders": ModelCompareLoaders,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareLoaders": "Model Compare Loaders",
}