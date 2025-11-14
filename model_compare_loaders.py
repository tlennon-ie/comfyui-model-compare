"""
Model Compare Loaders Node
Allows users to configure multiple checkpoints, VAEs, text encoders, and LoRAs
for comparison sampling.
"""

import os
import json
import itertools
from typing import List, Dict, Tuple, Any
import folder_paths
import comfy.sd
import comfy.model_management


class ModelCompareLoaders:
    """
    Configure multiple model components for comparison.
    Users specify:
    - Number of checkpoints to compare
    - Number of VAEs to compare
    - Number of text encoders to compare
    - Number of LoRAs to compare (with strength configurations)
    """

    def __init__(self):
        self.checkpoint_models = []
        self.vae_models = []
        self.text_encoder_models = []
        self.lora_models = []
        self.lora_strengths = {}

    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the node."""
        checkpoints = folder_paths.get_filename_list("checkpoints")
        vaes = folder_paths.get_filename_list("vae")
        clip_models = folder_paths.get_filename_list("clip")
        loras = folder_paths.get_filename_list("loras")

        return {
            "required": {
                "num_checkpoints": ("INT", {
                    "default": 1,
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

    CATEGORY = "model"
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "configure_models"
    OUTPUT_NODE = True

    def configure_models(
        self,
        num_checkpoints: int,
        num_vaes: int,
        num_text_encoders: int,
        num_loras: int,
    ) -> Tuple[Dict[str, Any]]:
        """
        Create a configuration dict that specifies how many of each model type
        will be compared.
        """
        config = {
            "num_checkpoints": num_checkpoints,
            "num_vaes": num_vaes,
            "num_text_encoders": num_text_encoders,
            "num_loras": num_loras,
            "checkpoints": [],
            "vaes": [],
            "text_encoders": [],
            "loras": [],  # Format: [{"name": str, "strengths": [float, ...]}]
            "combinations": [],  # Will be computed during sampling
        }
        
        print(f"[ModelCompareLoaders] Config created:")
        print(f"  - Checkpoints: {num_checkpoints}")
        print(f"  - VAEs: {num_vaes}")
        print(f"  - Text Encoders: {num_text_encoders}")
        print(f"  - LoRAs: {num_loras}")

        return (config,)


class ModelCompareLoadersAdvanced:
    """
    Advanced node that allows users to specify which specific models
    and their strengths for LoRAs.
    
    This is designed to work in conjunction with ModelCompareLoaders
    and allows detailed configuration of each model selection.
    """

    @classmethod
    def INPUT_TYPES(cls):
        checkpoints = folder_paths.get_filename_list("checkpoints")
        vaes = folder_paths.get_filename_list("vae")
        clip_models = folder_paths.get_filename_list("clip")
        loras = folder_paths.get_filename_list("loras")

        inputs = {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
            },
            "optional": {},
        }

        # Dynamically add checkpoint selection widgets
        for i in range(10):
            inputs["optional"][f"checkpoint_{i}"] = (
                ["NONE"] + checkpoints,
                {"default": "NONE"},
            )

        # Dynamically add VAE selection widgets
        for i in range(5):
            inputs["optional"][f"vae_{i}"] = (
                ["NONE"] + vaes,
                {"default": "NONE"},
            )

        # Dynamically add text encoder selection widgets
        for i in range(5):
            inputs["optional"][f"text_encoder_{i}"] = (
                ["NONE"] + clip_models,
                {"default": "NONE"},
            )

        # Dynamically add LoRA selection and strength widgets
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
                    "tooltip": "Comma-separated strength values to test (e.g., '0.0, 0.5, 1.0, 1.5')",
                },
            )

        return inputs

    CATEGORY = "model"
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)
    RETURN_NAMES = ("config",)
    FUNCTION = "apply_model_selections"
    OUTPUT_NODE = True

    def apply_model_selections(self, config: Dict[str, Any], **kwargs) -> Tuple[Dict[str, Any]]:
        """
        Process user selections and populate the config with specific models.
        """
        # Extract checkpoint selections
        checkpoints = []
        for i in range(config["num_checkpoints"]):
            key = f"checkpoint_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                checkpoints.append(kwargs[key])

        # Extract VAE selections
        vaes = []
        for i in range(config["num_vaes"]):
            key = f"vae_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                vaes.append(kwargs[key])

        # Extract text encoder selections
        text_encoders = []
        for i in range(config["num_text_encoders"]):
            key = f"text_encoder_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                text_encoders.append(kwargs[key])

        # Extract LoRA selections and strengths
        loras = []
        for i in range(config["num_loras"]):
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

        # Update config
        config["checkpoints"] = checkpoints
        config["vaes"] = vaes
        config["text_encoders"] = text_encoders
        config["loras"] = loras

        # Compute all combinations
        config["combinations"] = self._compute_combinations(config)

        print(f"[ModelCompareLoadersAdvanced] Config updated:")
        print(f"  - Checkpoints: {checkpoints}")
        print(f"  - VAEs: {vaes}")
        print(f"  - Text Encoders: {text_encoders}")
        print(f"  - LoRAs: {[l['name'] for l in loras]}")
        print(f"  - Total combinations: {len(config['combinations'])}")

        return (config,)

    @staticmethod
    def _compute_combinations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compute all possible combinations of models and LoRA strengths.
        
        For example, if we have:
        - 2 checkpoints
        - 2 VAEs
        - 2 LoRAs with 3 strengths each
        
        We generate 2 * 2 * (3 * 3) = 36 combinations
        """
        checkpoints = config.get("checkpoints", [])
        vaes = config.get("vaes", [])
        text_encoders = config.get("text_encoders", [])
        loras = config.get("loras", [])

        # Ensure we have at least one option for each
        if not checkpoints:
            checkpoints = [None]
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
        for ckpt, vae, text_enc, lora_strengths in itertools.product(
            checkpoints, vaes, text_encoders, lora_strength_combos
        ):
            combination = {
                "checkpoint": ckpt,
                "vae": vae,
                "text_encoder": text_enc,
                "lora_strengths": lora_strengths,  # Tuple of strength values
                "lora_names": [l["name"] for l in loras] if loras else [],
                "label": ModelCompareLoadersAdvanced._make_label(
                    ckpt, vae, text_enc, loras, lora_strengths
                ),
            }
            combinations.append(combination)

        return combinations

    @staticmethod
    def _make_label(checkpoint, vae, text_encoder, loras, lora_strengths):
        """Create a human-readable label for a combination."""
        parts = []
        
        if checkpoint:
            # Remove extension for cleaner label
            parts.append(f"ckpt:{os.path.splitext(checkpoint)[0]}")
        
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
    "ModelCompareLoadersAdvanced": ModelCompareLoadersAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareLoaders": "Model Compare Loaders",
    "ModelCompareLoadersAdvanced": "Model Compare Loaders Advanced",
}
