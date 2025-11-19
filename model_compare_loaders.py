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
    
    # Version bump - increment when INPUT_TYPES changes to force UI refresh
    _version = 2
    
    # Cache model lists to maintain consistent ordering
    _model_cache = {
        "checkpoints": None,
        "diffusion_models": None,
        "vaes": None,
        "clip_models": None,
        "loras": None,
    }
    
    # Mapping from cache keys to folder_paths names
    _folder_path_mapping = {
        "checkpoints": "checkpoints",
        "diffusion_models": "diffusion_models",
        "vaes": "vae",
        "clip_models": "clip",
        "loras": "loras",
    }
    
    @classmethod
    def _get_cached_models(cls, model_type: str) -> List[str]:
        """Get cached and sorted model list to ensure consistent ordering."""
        if cls._model_cache[model_type] is None:
            # Load and sort on first call using correct folder_paths name
            folder_name = cls._folder_path_mapping[model_type]
            models = sorted(folder_paths.get_filename_list(folder_name))
            cls._model_cache[model_type] = models
        return cls._model_cache[model_type]
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the node with preset system."""
        diffusion_models = cls._get_cached_models("diffusion_models")
        vaes = cls._get_cached_models("vaes")
        clip_models = cls._get_cached_models("clip_models")
        loras = cls._get_cached_models("loras")

        inputs = {
            "required": {
                # Preset selector - determines which fields are shown
                "preset": (["QWEN", "FLUX"], {
                    "default": "QWEN",
                    "tooltip": "Model preset - determines available configuration options"
                }),
                
                # Diffusion model - used by all presets (diffusion models only, no checkpoints)
                "diffusion_model": (
                    ["NONE"] + [f"[Diffusion] {d}" for d in diffusion_models],
                    {"default": f"[Diffusion] {diffusion_models[0]}" if diffusion_models else "NONE",
                     "tooltip": "Primary diffusion model"},
                ),
                
                # VAE - used by all presets
                "vae": (
                    ["NONE"] + vaes,
                    {"default": vaes[0] if vaes else "NONE",
                     "tooltip": "Primary VAE for encoding/decoding images"},
                ),
                
                # CLIP model - used by all presets
                "clip_model": (
                    ["NONE"] + clip_models,
                    {"default": clip_models[0] if clip_models else "NONE",
                     "tooltip": "Primary text encoder for prompts"},
                ),
                
                # Clip type
                "clip_type": (
                    ["default", "stable_diffusion", "stable_diffusion_xl", "flux", "qwen_image"],
                    {"default": "flux",
                     "tooltip": "CLIP model type (auto-adjusted based on preset)"},
                ),
                
                # Number of diffusion variations
                "num_diffusion_models": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of diffusion model variations to compare",
                }),
                
                # Number of VAE variations
                "num_vae_variations": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of VAE variations to compare",
                }),
                
                # Number of CLIP variations (for both QWEN and FLUX)
                "num_clip_variations": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 5,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of CLIP variations (single for QWEN, pairs for FLUX)",
                }),
                
                # Number of LoRAs
                "num_loras": ("INT", {
                    "default": 1,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of LoRA combinations to test",
                }),
            },
            "optional": {},
        }

        # Add diffusion model variation widgets (up to 5 additional models)
        for i in range(1, 5):
            inputs["optional"][f"diffusion_model_variation_{i}"] = (
                ["NONE"] + [f"[Diffusion] {d}" for d in diffusion_models],
                {"default": "NONE",
                 "tooltip": "Alternative diffusion model for comparison"},
            )
        
        # Add VAE variation widgets
        for i in range(1, 5):
            inputs["optional"][f"vae_variation_{i}"] = (
                ["NONE"] + vaes,
                {"default": "NONE",
                 "tooltip": "Additional VAE for comparison"},
            )
        
        # QWEN-style CLIP variations (individual CLIPs, not pairs)
        # clip_model is the first one, clip_model_1, clip_model_2, etc. are additional
        for i in range(1, 6):
            inputs["optional"][f"clip_model_{i}"] = (
                ["NONE"] + clip_models,
                {"default": "NONE",
                 "tooltip": f"[QWEN] CLIP variation {i}"},
            )
        
        # FLUX-style CLIP pair variations (pairs a/b)
        # clip_model_a and clip_model_b are the first pair
        # clip_model_1_a, clip_model_1_b are the second pair, etc.
        for i in range(6):
            suffix = "" if i == 0 else f"_{i}"
            inputs["optional"][f"clip_model{suffix}_a"] = (
                ["NONE"] + clip_models,
                {"default": "NONE",
                 "tooltip": f"[FLUX] First CLIP in pair variation {i}"},
            )
            inputs["optional"][f"clip_model{suffix}_b"] = (
                ["NONE"] + clip_models,
                {"default": "NONE",
                 "tooltip": f"[FLUX] Second CLIP in pair variation {i}"},
            )

        # Add LoRA selection widgets (up to 10)
        for i in range(10):
            inputs["optional"][f"lora_{i}"] = (
                ["NONE"] + loras,
                {"default": "NONE",
                 "tooltip": "LoRA model for comparison"},
            )
            inputs["optional"][f"lora_{i}_strengths"] = (
                "STRING",
                {
                    "default": "1.0",
                    "multiline": False,
                    "tooltip": "Comma-separated strength values (e.g., '0.0, 0.5, 1.0, 1.5')",
                },
            )
            inputs["optional"][f"lora_{i}_customlabel"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Custom label for this LoRA (leave empty for filename)",
                },
            )
            inputs["optional"][f"lora_{i}_combiner"] = (
                ["AND", "OR"],
                {"default": "AND",
                 "tooltip": "AND: always use, OR: test separately"},
            )

        return inputs

    CATEGORY = "model"
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG", "MODEL", "CLIP", "VAE")
    RETURN_NAMES = ("config", "base_model", "base_clip", "base_vae")
    FUNCTION = "load_models"

    def load_models(
        self,
        preset: str = "QWEN",
        diffusion_model: str = "NONE",
        vae: str = "NONE",
        clip_model: str = "NONE",
        clip_type: str = "flux",
        num_diffusion_models: int = 1,
        num_vae_variations: int = 1,
        num_clip_variations: int = 1,
        num_loras: int = 1,
        **kwargs
    ) -> Tuple[Dict[str, Any], Any, Any, Any]:
        """
        Load base models and create configuration for comparisons.
        Handles preset-specific model loading (QWEN, FLUX).
        Backwards compatible with old parameter names.
        
        IMPORTANT: Output Pin Order and Usage
        ====================================
        Pin 1 (config): MODEL_COMPARE_CONFIG dict
            → Use for: SamplerCompare.config, GridCompare.config
            → DO NOT use for: ModelSamplingAuraFlow, CFGNorm, or other model-sampling nodes!
        
        Pin 2 (base_model): Actual MODEL object
            → Use for: ModelSamplingAuraFlow, CFGNorm, and other model-patching nodes
            → Use for: Direct model input to samplers if not using patching nodes
            → Connected to: SamplerCompare.model (when not using model-patching nodes)
        
        Pin 3 (base_clip): CLIP text encoder
            → Use for: Conditioning nodes, SamplerCompare.clip
        
        Pin 4 (base_vae): VAE model
            → Use for: SamplerCompare.vae, VAE encode/decode operations
        
        Common Error: "'dict' object has no attribute 'clone'"
        → This means you connected Pin 1 (config) to a node expecting a MODEL
        → Always use Pin 2 (base_model) for model-related nodes!
        """
        
        # Backwards compatibility: Handle old parameter names
        # Old name: base_model → New name: diffusion_model
        if "base_model" in kwargs and (diffusion_model == "NONE" or not diffusion_model):
            diffusion_model = kwargs.pop("base_model")
        
        # Old name: num_model_variations → New name: num_diffusion_models
        if "num_model_variations" in kwargs and num_diffusion_models == 1:
            num_diffusion_models = kwargs.pop("num_model_variations")
        
        # Old name: model_variation_* → New name: diffusion_model_variation_*
        for i in range(1, 10):
            old_key = f"model_variation_{i}"
            new_key = f"diffusion_model_variation_{i}"
            if old_key in kwargs and new_key not in kwargs:
                kwargs[new_key] = kwargs.pop(old_key)
        
        # Adjust clip_type based on preset (can still be overridden by user)
        if preset == "QWEN" and clip_type not in ["qwen_image", "default"]:
            clip_type = "qwen_image"
        elif preset == "FLUX" and clip_type not in ["flux", "default"]:
            clip_type = "flux"
        
        # If diffusion_model is NONE or empty, use first available model
        if not diffusion_model or diffusion_model == "NONE":
            diffusion_models = self._get_cached_models("diffusion_models")
            if diffusion_models:
                diffusion_model = f"[Diffusion] {diffusion_models[0]}"
            else:
                raise ValueError("No diffusion models available")
        
        # If vae is NONE or empty, use first available VAE
        if not vae or vae == "NONE":
            vaes = self._get_cached_models("vaes")
            if vaes:
                vae = vaes[0]
            else:
                raise ValueError("No VAEs available")
        
        # Handle CLIP model selection
        if not clip_model or clip_model == "NONE":
            clip_models = self._get_cached_models("clip_models")
            if clip_models:
                clip_model = clip_models[0]
            else:
                raise ValueError("No CLIP models available")
        
        # Parse diffusion_model (format: "[Type] filename")
        base_model_type, base_model_name = self._parse_model_selector(diffusion_model)
        
        # Load the base models
        base_model_obj = self._load_model(base_model_name, base_model_type)
        base_vae_obj = self._load_vae(vae)
        
        # Load CLIP based on preset
        # FLUX uses clip_model_a and clip_model_b (pair), QWEN uses clip_model (single)
        if preset == "FLUX":
            # For FLUX, try to load clip_model_a and clip_model_b pair
            clip_model_a = kwargs.get("clip_model_a", "NONE")
            clip_model_b = kwargs.get("clip_model_b", "NONE")
            
            # If both FLUX clips are set, use them
            if clip_model_a != "NONE" and clip_model_b != "NONE":
                base_clip_obj = self._load_clip_pair(clip_model_a, clip_model_b, clip_type)
            # Otherwise fall back to single clip_model
            elif clip_model != "NONE":
                print(f"[ModelCompareLoaders] Warning: FLUX preset but using single CLIP model. For best results, use clip_model_a and clip_model_b pair.")
                base_clip_obj = self._load_clip(clip_model, clip_type)
            else:
                raise ValueError("FLUX preset requires clip_model_a and clip_model_b to be set")
        else:
            # For QWEN or other presets, use single clip_model
            base_clip_obj = self._load_clip(clip_model, clip_type)
        
        # Collect CLIP variations (only up to num_clip_variations)
        # For FLUX: look for clip_model_1_a/b, clip_model_2_a/b, etc.
        # For QWEN: look for clip_model_1, clip_model_2, etc.
        clip_variations = []
        if preset == "FLUX":
            # FLUX clip pairs
            clip_variations.append({"a": clip_model_a, "b": clip_model_b, "type": "pair"})
            for i in range(1, num_clip_variations):
                clip_a_key = f"clip_model_{i}_a"
                clip_b_key = f"clip_model_{i}_b"
                clip_a = kwargs.get(clip_a_key, "NONE")
                clip_b = kwargs.get(clip_b_key, "NONE")
                
                if clip_a != "NONE" and clip_b != "NONE":
                    clip_variations.append({"a": clip_a, "b": clip_b, "type": "pair"})
        else:
            # QWEN single clips
            clip_variations.append({"model": clip_model, "type": "single"})
            for i in range(1, num_clip_variations):
                clip_key = f"clip_model_{i}"
                clip_m = kwargs.get(clip_key, "NONE")
                
                if clip_m != "NONE":
                    clip_variations.append({"model": clip_m, "type": "single"})
        
        # Collect model variations (only up to num_diffusion_models)
        model_variations = [{"name": base_model_name, "type": base_model_type}]
        for i in range(1, num_diffusion_models):
            key = f"diffusion_model_variation_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                try:
                    mtype, mname = self._parse_model_selector(kwargs[key])
                    model_variations.append({"name": mname, "type": mtype})
                except:
                    # Silently skip invalid model variations
                    pass
        
        # Collect VAE variations (only up to num_vae_variations)
        vae_variations = [vae]
        for i in range(1, num_vae_variations):
            key = f"vae_variation_{i}"
            if key in kwargs and kwargs[key] != "NONE":
                try:
                    vae_variations.append(kwargs[key])
                except:
                    # Silently skip invalid VAE variations
                    pass
        
        # Collect LoRAs with custom labels and combiner operators (only up to num_loras)
        loras = []
        lora_combiners = []  # Track AND/OR operators between LoRAs
        
        for i in range(num_loras):
            lora_key = f"lora_{i}"
            strengths_key = f"lora_{i}_strengths"
            customlabel_key = f"lora_{i}_customlabel"
            combiner_key = f"lora_{i}_combiner"
            
            if lora_key in kwargs and kwargs[lora_key] != "NONE":
                try:
                    lora_name = kwargs[lora_key]
                    strengths_str = kwargs.get(strengths_key, "1.0")
                    custom_label = kwargs.get(customlabel_key, "").strip()
                    combiner = kwargs.get(combiner_key, "AND")  # Default to AND
                    
                    try:
                        strengths = [
                            float(s.strip())
                            for s in strengths_str.split(",")
                            if s.strip()
                        ]
                    except ValueError:
                        strengths = [1.0]

                    loras.append({
                        "name": lora_name,
                        "display_name": custom_label if custom_label else lora_name,  # Use custom label if provided
                        "strengths": strengths,
                    })
                    
                    # Store combiner operator (before the next LoRA)
                    lora_combiners.append(combiner)
                except:
                    # Silently skip invalid LoRAs
                    pass
        
        # Create config
        config = {
            "preset": preset,
            "model_variations": model_variations,
            "vae_variations": vae_variations,
            "clip_variations": clip_variations,
            "loras": loras,
            "lora_combiners": lora_combiners,  # Store combiner operators
            "clip_type": clip_type,
            "base_model_type": base_model_type,
            "base_model_name": base_model_name,
        }
        
        # Compute all combinations
        config["combinations"] = self._compute_combinations(config)
        
        # Summary logging - always show key info
        num_total_combos = len(config['combinations'])
        lora_combiners_list = config.get('lora_combiners', [])
        
        # Calculate grid dimensions
        if lora_combiners_list:
            or_count = sum(1 for op in lora_combiners_list if op == 'OR')
            num_rows = or_count + 1
        else:
            num_rows = 1
        
        num_cols = num_total_combos // max(1, num_rows) if num_rows > 0 else num_total_combos
        
        print(f"[ModelCompareLoaders] Grid: {num_rows} rows × {num_cols} columns = {num_total_combos} images")
        
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
            # Load diffusion model (U-Net)
            model_path = folder_paths.get_full_path("diffusion_models", model_name)
            model = comfy.sd.load_diffusion_model(model_path)
            return model
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
    def _load_clip_pair(clip_name_1: str, clip_name_2: str, clip_type: str) -> Any:
        """Load a pair of CLIP models (for FLUX which requires CLIP_L + T5XXL)."""
        clip_path_1 = folder_paths.get_full_path_or_raise("text_encoders", clip_name_1)
        clip_path_2 = folder_paths.get_full_path_or_raise("text_encoders", clip_name_2)
        
        # Map clip_type to CLIPType enum
        clip_type_enum = getattr(comfy.sd.CLIPType, clip_type.upper(), comfy.sd.CLIPType.FLUX)
        
        # Load both CLIPs with the specified type
        clip = comfy.sd.load_clip(
            ckpt_paths=[clip_path_1, clip_path_2],
            embedding_directory=folder_paths.get_folder_paths("embeddings"),
            clip_type=clip_type_enum
        )
        
        return clip
    
    @staticmethod
    def _compute_combinations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Compute all possible combinations.
        Supports AND/OR operators to control LoRA combination strategy.
        AND = include LoRA in all combinations
        OR = switch between LoRAs (test each separately or in groups)
        Also includes CLIP variations (single for QWEN, pairs for FLUX)
        """
        models = config["model_variations"]
        vaes = config["vae_variations"]
        clips = config.get("clip_variations", [])
        loras = config["loras"]
        lora_combiners = config.get("lora_combiners", [])
        
        # Group LoRAs by AND/OR operators
        lora_groups = []
        current_group = [loras[0]] if loras else []
        
        for i, combiner in enumerate(lora_combiners):
            if combiner == "AND" and i + 1 < len(loras):
                # Add to current group
                current_group.append(loras[i + 1])
            elif combiner == "OR" and i + 1 < len(loras):
                # Start a new group
                lora_groups.append(current_group)
                current_group = [loras[i + 1]]
        
        # Add the last group
        if current_group:
            lora_groups.append(current_group)
        
        # If no loras, we still need at least one empty group
        if not loras:
            lora_groups = [[]]
        
        print(f"[ModelCompareLoaders] lora_combiners={lora_combiners}")
        print(f"[ModelCompareLoaders] lora_groups={[[l['name'] for l in g] for g in lora_groups]}")
        print(f"[ModelCompareLoaders] clip_variations={len(clips)} variations")
        
        # Compute LoRA strength combinations within each group
        group_combos = []
        for group in lora_groups:
            if not group:
                group_combos.append([{"lora_names": [], "lora_strengths": ()}])
                continue
            
            # For each group, compute all strength combinations for LoRAs in that group
            strength_lists = [l["strengths"] for l in group]
            lora_strength_combos = list(itertools.product(*strength_lists))
            
            group_combo_list = []
            for lora_strengths in lora_strength_combos:
                combo = {
                    "lora_names": [l["name"] for l in group],
                    "lora_display_names": [l["display_name"] for l in group],
                    "lora_strengths": lora_strengths,
                }
                print(f"[ModelCompareLoaders] Combo: names={combo['lora_names']}, display={combo['lora_display_names']}, strengths={combo['lora_strengths']}")
                group_combo_list.append(combo)
            
            group_combos.append(group_combo_list)
        
        # Now create combinations: model × vae × clip × (group1_combos OR group2_combos OR ...)
        # This means we'll test each group separately, across all clip variations
        combinations = []
        
        if len(lora_groups) == 1 and len(lora_groups[0]) == 0:
            # No LoRAs case
            for model, vae, clip_var in itertools.product(models, vaes, clips):
                combination = {
                    "model": model["name"],
                    "model_type": model["type"],
                    "vae": vae,
                    "clip_variation": clip_var,
                    "lora_strengths": (),
                    "lora_names": [],
                    "lora_display_names": [],
                }
                combinations.append(combination)
        else:
            # Standard case with LoRAs
            for model, vae, clip_var in itertools.product(models, vaes, clips):
                for group_idx, group_combo_list in enumerate(group_combos):
                    for group_combo in group_combo_list:
                        combination = {
                            "model": model["name"],
                            "model_type": model["type"],
                            "vae": vae,
                            "clip_variation": clip_var,
                            "lora_strengths": group_combo["lora_strengths"],
                            "lora_names": group_combo["lora_names"],
                            "lora_display_names": group_combo.get("lora_display_names", group_combo["lora_names"]),
                        }
                        combinations.append(combination)
        
        print(f"[ModelCompareLoaders] Total combinations created: {len(combinations)}")
        for i, combo in enumerate(combinations[:5]):  # Show first 5 for brevity
            print(f"[ModelCompareLoaders]   Combo {i}: names={combo['lora_names']}, strengths={combo['lora_strengths']}, clip={combo['clip_variation'].get('type', 'unknown')}")
        
        return combinations


# Node mappings
NODE_CLASS_MAPPINGS = {
    "ModelCompareLoaders": ModelCompareLoaders,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareLoaders": "Model Compare Loaders",
}