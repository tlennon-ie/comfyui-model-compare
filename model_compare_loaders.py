"""
Model Compare Loaders Node - Combined single node
Allows users to:
1. Set number of checkpoints, diffusion models, VAEs, text encoders, LoRAs with sliders
2. Click "Update Inputs" button to show corresponding dropdown fields
3. Select specific models from the dropdowns
"""

import os
import itertools
from typing import List, Dict, Tuple, Any
import folder_paths


class ModelCompareLoaders:
    """
    Single combined loader node with configuration sliders and dynamic model selection.
    """

    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the node."""
        checkpoints = folder_paths.get_filename_list("checkpoints")
        diffusion_models = folder_paths.get_filename_list("diffusion_models")
        vaes = folder_paths.get_filename_list("vae")
        clip_models = folder_paths.get_filename_list("clip")
        loras = folder_paths.get_filename_list("loras")

        inputs = {
            "required": {
                "num_checkpoints": ("INT", {
                    "default": 1,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                }),
                "num_diffusion_models": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                }),
                "num_vaes": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                }),
                "num_text_encoders": ("INT", {
                    "default": 0,
                    "min": 0,
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

        # Add checkpoint selection widgets (up to 10)
        for i in range(10):
            inputs["optional"][f"checkpoint_{i}"] = (
                ["NONE"] + checkpoints,
                {"default": "NONE"},
            )

        # Add diffusion model selection widgets (up to 10)
        for i in range(10):
            inputs["optional"][f"diffusion_model_{i}"] = (
                ["NONE"] + diffusion_models,
                {"default": "NONE"},
            )

        # Add VAE selection widgets (up to 5)
        for i in range(5):
            inputs["optional"][f"vae_{i}"] = (
                ["NONE"] + vaes,
                {"default": "NONE"},
            )

        # Add text encoder selection widgets (up to 5)
        for i in range(5):
            inputs["optional"][f"text_encoder_{i}"] = (
                ["NONE"] + clip_models,
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
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "apply_model_selections"
    OUTPUT_NODE = True

    def apply_model_selections(
        self,
        num_checkpoints: int,
        num_diffusion_models: int,
        num_vaes: int,
        num_text_encoders: int,
        num_loras: int,
        **kwargs
    ) -> Tuple[Dict[str, Any]]:
        """
        Process user selections and populate the config with specific models.
        Only uses the number of slots specified by the num_* sliders.
        """
        # Extract checkpoint selections (only use the number specified)
        checkpoints = []
        for i in range(num_checkpoints):
            key = f"checkpoint_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                checkpoints.append(("checkpoint", kwargs[key]))

        # Extract diffusion model selections (only use the number specified)
        diffusion_models = []
        for i in range(num_diffusion_models):
            key = f"diffusion_model_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                diffusion_models.append(("diffusion_model", kwargs[key]))

        # Extract VAE selections (only use the number specified)
        vaes = []
        for i in range(num_vaes):
            key = f"vae_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                vaes.append(kwargs[key])

        # Extract text encoder selections (only use the number specified)
        text_encoders = []
        for i in range(num_text_encoders):
            key = f"text_encoder_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                text_encoders.append(kwargs[key])

        # Extract LoRA selections and strengths (only use the number specified)
        loras = []
        for i in range(num_loras):
            lora_key = f"lora_{i}"
            strengths_key = f"lora_{i}_strengths"
            
            if lora_key in kwargs and kwargs[lora_key] != "NONE":
                lora_name = kwargs[lora_key]
                strengths_str = kwargs.get(strengths_key, "1.0")
                
                # Parse comma-separated strength values
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
            "num_checkpoints": num_checkpoints,
            "num_diffusion_models": num_diffusion_models,
            "num_vaes": num_vaes,
            "num_text_encoders": num_text_encoders,
            "num_loras": num_loras,
            "checkpoints": [ckpt[1] for ckpt in checkpoints],
            "checkpoint_types": [ckpt[0] for ckpt in checkpoints],
            "diffusion_models": [dm[1] for dm in diffusion_models],
            "diffusion_model_types": [dm[0] for dm in diffusion_models],
            "vaes": vaes,
            "text_encoders": text_encoders,
            "loras": loras,
        }

        # Compute all combinations
        config["combinations"] = self._compute_combinations(config)

        print(f"[ModelCompareLoaders] Config updated:")
        print(f"  - Checkpoints: {config['checkpoints']}")
        print(f"  - Diffusion Models: {config['diffusion_models']}")
        print(f"  - VAEs: {vaes}")
        print(f"  - Text Encoders: {text_encoders}")
        print(f"  - LoRAs: {[l['name'] for l in loras]}")
        print(f"  - Total combinations: {len(config['combinations'])}")

        return (config,)

    @staticmethod
    def _compute_combinations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compute all possible combinations of models and LoRA strengths.
        """
        checkpoints = config.get("checkpoints", [])
        checkpoint_types = config.get("checkpoint_types", [])
        diffusion_models = config.get("diffusion_models", [])
        vaes = config.get("vaes", [])
        text_encoders = config.get("text_encoders", [])
        loras = config.get("loras", [])

        # Combine checkpoint and diffusion model selections into one list
        all_ckpts = []
        for ckpt, ckpt_type in zip(checkpoints, checkpoint_types):
            all_ckpts.append({"name": ckpt, "type": ckpt_type})
        
        for dm in diffusion_models:
            all_ckpts.append({"name": dm, "type": "diffusion_model"})
        
        if not all_ckpts:
            all_ckpts = [{"name": None, "type": None}]
        if not vaes:
            vaes = [None]
        if not text_encoders:
            text_encoders = [None]

        # Compute all LoRA strength combinations
        lora_strength_combos = []
        if loras:
            strength_lists = [l["strengths"] for l in loras]
            lora_strength_combos = list(itertools.product(*strength_lists))
        else:
            lora_strength_combos = [None]

        # Generate all combinations
        combinations = []
        for ckpt_info, vae, text_enc, lora_strengths in itertools.product(
            all_ckpts, vaes, text_encoders, lora_strength_combos
        ):
            combination = {
                "checkpoint": ckpt_info["name"],
                "checkpoint_type": ckpt_info["type"],
                "vae": vae,
                "text_encoder": text_enc,
                "lora_strengths": lora_strengths,
                "lora_names": [l["name"] for l in loras] if loras else [],
                "label": ModelCompareLoaders._make_label(
                    ckpt_info, vae, text_enc, loras, lora_strengths
                ),
            }
            combinations.append(combination)

        return combinations

    @staticmethod
    def _make_label(ckpt_info, vae, text_encoder, loras, lora_strengths):
        """Create a human-readable label for a combination."""
        parts = []
        
        if ckpt_info and ckpt_info.get("name"):
            label_type = "diffusion" if ckpt_info.get("type") == "diffusion_model" else "ckpt"
            parts.append(f"{label_type}:{os.path.splitext(ckpt_info['name'])[0]}")
        
        if vae:
            parts.append(f"vae:{os.path.splitext(vae)[0]}")
        
        if text_encoder:
            parts.append(f"enc:{os.path.splitext(text_encoder)[0]}")
        
        if loras and lora_strengths:
            for lora, strength in zip(loras, lora_strengths):
                lora_name = os.path.splitext(lora["name"])[0]
                parts.append(f"{lora_name}:{strength:.2f}")

        return " | ".join(parts) if parts else "default"


# Node mappings
NODE_CLASS_MAPPINGS = {
    "ModelCompareLoaders": ModelCompareLoaders,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareLoaders": "Model Compare Loaders",
}
