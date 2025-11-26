"""
Advanced Model Compare Sampler - Cross-preset comparison with auto-detection.
Supports comparing models across different architectures (FLUX vs QWEN vs WAN vs Hunyuan).
All sampling parameters exposed - auto-detects which to use per model.

LAZY LOADING: Models are loaded on-demand per combination to minimize VRAM usage.
Smart unloading occurs only when model/VAE/CLIP config changes between combinations.
"""

import gc
import hashlib
import torch
import folder_paths
import comfy.sd
import comfy.utils
import comfy.sample
import comfy.samplers
import comfy.model_management
from typing import List, Dict, Tuple, Any, Optional
from comfy_extras.nodes_model_advanced import ModelSamplingSD3, ModelSamplingAuraFlow, RescaleCFG, ModelSamplingFlux

class SamplerCompareAdvanced:
    """
    Advanced sampler for cross-model comparison with LAZY LOADING.
    Models are loaded on-demand per combination, then unloaded when config changes.
    Supports: FLUX, FLUX2, QWEN, WAN 2.1/2.2, Hunyuan 1.0/1.5, SDXL, SD
    """
    
    RETURN_TYPES = ("IMAGE", "MODEL_COMPARE_CONFIG", "STRING")
    RETURN_NAMES = ("images", "config", "labels")
    FUNCTION = "sample_all_combinations"
    CATEGORY = "sampling"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "latent": ("LATENT",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS,),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS,),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
            },
            "optional": {
                # === FLUX Parameters ===
                "flux_guidance": ("FLOAT", {
                    "default": 3.5, "min": 0.0, "max": 100.0, "step": 0.1,
                    "tooltip": "FLUX guidance scale (used for FLUX/FLUX2 models)"
                }),
                
                # === QWEN Parameters ===
                "qwen_shift": ("FLOAT", {
                    "default": 8.0, "min": 0.0, "max": 20.0, "step": 0.1,
                    "tooltip": "QWEN shift parameter for AuraFlow sampling"
                }),
                "cfg_norm": ("BOOLEAN", {
                    "default": True,
                    "tooltip": "Enable CFG normalization for QWEN models (RescaleCFG)"
                }),
                "cfg_norm_multiplier": ("FLOAT", {
                    "default": 0.7, "min": 0.0, "max": 1.0, "step": 0.01,
                    "tooltip": "CFG normalization multiplier (0.7 recommended)"
                }),
                
                # === WAN Parameters ===
                "wan_shift": ("FLOAT", {
                    "default": 8.0, "min": 0.0, "max": 20.0, "step": 0.1,
                    "tooltip": "WAN 2.1 shift parameter"
                }),
                "wan22_start_step": ("INT", {
                    "default": 0, "min": 0, "max": 10000,
                    "tooltip": "WAN 2.2 High noise start step"
                }),
                "wan22_end_step": ("INT", {
                    "default": 16, "min": 0, "max": 10000,
                    "tooltip": "WAN 2.2 High noise end step (Low noise continues from here)"
                }),
                
                # === Hunyuan Parameters ===
                "hunyuan_shift": ("FLOAT", {
                    "default": 7.0, "min": 0.0, "max": 20.0, "step": 0.1,
                    "tooltip": "Hunyuan Video shift parameter"
                }),
                
                # === Video Latent Input ===
                "video_latent": ("LATENT", {
                    "tooltip": "Optional video latent for Hunyuan/WAN video models"
                }),
                
                # === Image-to-Video Inputs ===
                "start_image": ("IMAGE", {
                    "tooltip": "Start frame for WAN Image-to-Video"
                }),
                "end_image": ("IMAGE", {
                    "tooltip": "End frame for WAN First-Last-Frame-to-Video"
                }),
            }
        }

    def detect_model_type(self, model_obj) -> str:
        """
        Auto-detect model type from model object.
        Returns: 'flux', 'flux2', 'qwen', 'wan21', 'wan22', 'hunyuan', 'hunyuan15', 'sdxl', 'sd'
        """
        if not model_obj:
            return 'sd'
        
        try:
            # Check latent format for FLUX2 (128 channels)
            latent_format = model_obj.get_model_object("latent_format")
            if latent_format:
                if hasattr(latent_format, 'latent_channels') and latent_format.latent_channels == 128:
                    return 'flux2'
            
            # Check model config
            model_config = getattr(model_obj, 'model_config', None)
            if model_config:
                unet_config = getattr(model_config, 'unet_config', {})
                
                # Check for FLUX (16 channels, not 128)
                if unet_config.get('in_channels') == 16:
                    return 'flux'
                
                # Check for Hunyuan 1.5 (has vision_in_dim)
                if unet_config.get('vision_in_dim') == 1152:
                    return 'hunyuan15'
                
                # Check for Hunyuan (has specific config)
                if 'hunyuan' in str(type(model_config)).lower():
                    return 'hunyuan'
                
                # Check for WAN
                if 'wan' in str(type(model_config)).lower():
                    # WAN 2.2 typically uses different architecture
                    return 'wan21'  # Default, would need more info for 2.2
                
                # Check for QWEN
                if 'qwen' in str(type(model_config)).lower():
                    return 'qwen'
                
                # Check for SDXL (in_channels == 4, specific size)
                if unet_config.get('in_channels') == 4:
                    if unet_config.get('context_dim') == 2048:
                        return 'sdxl'
        except Exception as e:
            print(f"[SamplerCompareAdvanced] Model detection error: {e}")
        
        return 'sd'  # Default fallback

    # ===== LAZY LOADING HELPERS =====
    
    def _get_clip_type_enum(self, clip_type_str: str):
        """Convert clip_type string to CLIPType enum."""
        import comfy.sd
        mapping = {
            "sd": comfy.sd.CLIPType.STABLE_DIFFUSION,
            "sdxl": getattr(comfy.sd.CLIPType, "STABLE_DIFFUSION", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "sd3": getattr(comfy.sd.CLIPType, "SD3", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux": getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "flux2": getattr(comfy.sd.CLIPType, "FLUX2", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "wan": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "wan22": getattr(comfy.sd.CLIPType, "WAN", getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
            "hunyuan_video": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "hunyuan_video_15": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO_15", comfy.sd.CLIPType.STABLE_DIFFUSION),
            "qwen": getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION),
        }
        key = clip_type_str.upper().replace("_", "")
        if hasattr(comfy.sd.CLIPType, key):
            return getattr(comfy.sd.CLIPType, key)
        return mapping.get(clip_type_str, comfy.sd.CLIPType.STABLE_DIFFUSION)
    
    def _load_model(self, model_entry: Dict) -> Tuple[Any, Any]:
        """
        Lazy load a model from stored path.
        Returns (model_obj, model_low_obj) tuple.
        """
        model_obj = None
        model_low_obj = None
        
        model_path = model_entry.get("model_path")
        model_type = model_entry.get("model_type")
        
        if not model_path:
            print(f"[SamplerCompareAdvanced] ERROR: No model path in entry")
            return None, None
        
        print(f"[SamplerCompareAdvanced] Loading model: {model_path}")
        
        if model_type == "checkpoint":
            out = comfy.sd.load_checkpoint_guess_config(
                model_path, 
                output_vae=True, 
                output_clip=True, 
                embedding_directory=folder_paths.get_folder_paths("embeddings")
            )
            model_obj = out[0]
            # Store baked VAE/CLIP if use_baked is True
            if model_entry.get("use_baked_vae_clip"):
                model_entry["_baked_clip"] = out[1]
                model_entry["_baked_vae"] = out[2]
        elif model_type == "diffusion":
            model_obj = comfy.sd.load_diffusion_model(model_path, model_options={})
        
        # Load low noise model if WAN 2.2
        model_low_path = model_entry.get("model_low_path")
        if model_low_path:
            print(f"[SamplerCompareAdvanced] Loading WAN 2.2 low noise model: {model_low_path}")
            model_low_obj = comfy.sd.load_diffusion_model(model_low_path, model_options={})
        
        return model_obj, model_low_obj
    
    def _load_vae(self, vae_name: str, config: Dict, model_entry: Dict) -> Any:
        """
        Lazy load a VAE.
        Returns VAE object.
        """
        if vae_name == "__baked__":
            # Use baked VAE from checkpoint
            baked_vae = model_entry.get("_baked_vae")
            if baked_vae:
                print(f"[SamplerCompareAdvanced] Using baked VAE from checkpoint")
                return baked_vae
            else:
                print(f"[SamplerCompareAdvanced] WARNING: No baked VAE available")
                return None
        
        if vae_name == "NONE" or not vae_name:
            return None
        
        vae_paths = config.get("vae_paths", {})
        vae_path = vae_paths.get(vae_name)
        
        if not vae_path:
            print(f"[SamplerCompareAdvanced] WARNING: No path for VAE '{vae_name}'")
            return None
        
        print(f"[SamplerCompareAdvanced] Loading VAE: {vae_path}")
        vae = comfy.sd.VAE(sd=comfy.utils.load_torch_file(vae_path))
        return vae
    
    def _load_clip(self, clip_var: Dict, config: Dict, model_entry: Dict) -> Any:
        """
        Lazy load a CLIP.
        Returns CLIP object.
        """
        if not clip_var:
            return None
        
        clip_type = clip_var.get("type")
        clip_type_str = clip_var.get("clip_type", "sd")
        device = clip_var.get("device", "default")
        
        # Build model options for device
        model_options = {}
        if device == "cpu":
            model_options["load_device"] = torch.device("cpu")
            model_options["offload_device"] = torch.device("cpu")
            print(f"[SamplerCompareAdvanced] Loading CLIP on CPU")
        
        if clip_type == "baked":
            # Use baked CLIP from checkpoint
            baked_clip = model_entry.get("_baked_clip")
            if baked_clip:
                print(f"[SamplerCompareAdvanced] Using baked CLIP from checkpoint")
                return baked_clip
            else:
                print(f"[SamplerCompareAdvanced] WARNING: No baked CLIP available")
                return None
        
        elif clip_type == "pair":
            # Dual CLIP (FLUX, Hunyuan)
            path_a = clip_var.get("a_path")
            path_b = clip_var.get("b_path")
            if path_a and path_b:
                print(f"[SamplerCompareAdvanced] Loading dual CLIP: {clip_var.get('a')} + {clip_var.get('b')}")
                clip_obj = comfy.sd.load_clip(
                    ckpt_paths=[path_a, path_b],
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    clip_type=self._get_clip_type_enum(clip_type_str),
                    model_options=model_options
                )
                return clip_obj
        
        elif clip_type == "single":
            path = clip_var.get("model_path")
            if path:
                print(f"[SamplerCompareAdvanced] Loading single CLIP: {clip_var.get('model')}")
                clip_obj = comfy.sd.load_clip(
                    ckpt_paths=[path],
                    embedding_directory=folder_paths.get_folder_paths("embeddings"),
                    clip_type=self._get_clip_type_enum(clip_type_str),
                    model_options=model_options
                )
                return clip_obj
        
        return None
    
    def _unload_current(self):
        """Unload all models and free VRAM."""
        comfy.model_management.unload_all_models()
        comfy.model_management.cleanup_models()
        comfy.model_management.soft_empty_cache()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            free_mem = torch.cuda.mem_get_info()[0] / (1024**3)
            total_mem = torch.cuda.mem_get_info()[1] / (1024**3)
            print(f"[SamplerCompareAdvanced] GPU Memory: {free_mem:.2f}GB free / {total_mem:.2f}GB total")
    
    def _get_combo_key(self, combo: Dict, config: Dict) -> str:
        """
        Generate a unique key for a combination based on model/VAE/CLIP/LoRA.
        Prompt changes don't change the key (so models stay loaded).
        """
        model_idx = combo.get("model_index", 0)
        vae_name = combo.get("vae_name", "")
        clip_var = combo.get("clip_variation", {})
        
        # CLIP key based on type
        if clip_var.get("type") == "pair":
            clip_key = f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
        else:
            clip_key = clip_var.get("model", "")
        
        # LoRA key from new lora_config structure
        lora_config = combo.get("lora_config", {})
        lora_list = lora_config.get("loras", [])
        lora_key_parts = []
        for lora in lora_list:
            lora_key_parts.append(f"{lora.get('name', '')}:{lora.get('strength', 1.0)}")
            if lora.get("mode") == "HIGH_LOW_PAIR" and lora.get("low_name"):
                lora_key_parts.append(f"{lora.get('low_name', '')}:{lora.get('low_strength', 1.0)}")
        lora_key = "|".join(lora_key_parts)
        
        return f"{model_idx}|{vae_name}|{clip_key}|{lora_key}"
    
    def _apply_loras(self, model, clip, lora_config: Dict, model_type: str):
        """
        Apply LoRAs from the lora_config to model and clip.
        
        Args:
            model: The model patcher to apply LoRAs to
            clip: The CLIP model to apply LoRAs to (can be None)
            lora_config: Dict with "loras" list from LoRA Compare node
            model_type: Model type string for determining HIGH/LOW application
        
        Returns:
            Tuple of (model, model_low, clip) with LoRAs applied
        """
        if not lora_config:
            return model, None, clip
        
        loras = lora_config.get("loras", [])
        if not loras:
            return model, None, clip
        
        model_low = None
        is_wan22 = model_type == "wan22"
        
        for lora in loras:
            lora_path = lora.get("path")
            strength = lora.get("strength", 1.0)
            label = lora.get("label", lora.get("name", ""))
            
            if not lora_path:
                continue
            
            try:
                # Load LoRA
                lora_data = comfy.utils.load_torch_file(lora_path, safe_load=True)
                
                # Apply to model
                model, clip = comfy.sd.load_lora_for_models(
                    model, clip, lora_data, strength, strength
                )
                print(f"[SamplerCompareAdvanced] Applied LoRA: {label} (strength={strength})")
                
                # Handle HIGH_LOW_PAIR mode for WAN 2.2
                if lora.get("mode") == "HIGH_LOW_PAIR" and lora.get("low_path"):
                    low_path = lora.get("low_path")
                    low_strength = lora.get("low_strength", strength)
                    low_label = lora.get("low_label", lora.get("low_name", ""))
                    
                    # Load low LoRA for the low noise model
                    low_lora_data = comfy.utils.load_torch_file(low_path, safe_load=True)
                    
                    # If we have a separate low model, apply to it
                    # Otherwise, we'll need to track this for later
                    print(f"[SamplerCompareAdvanced] Loaded LOW LoRA: {low_label} (strength={low_strength})")
                    
                    # Store low LoRA info for WAN 2.2 two-phase sampling
                    if not hasattr(model, '_low_loras'):
                        model._low_loras = []
                    model._low_loras.append({
                        "data": low_lora_data,
                        "strength": low_strength,
                        "label": low_label
                    })
                    
            except Exception as e:
                print(f"[SamplerCompareAdvanced] Error loading LoRA {label}: {e}")
                continue
        
        return model, model_low, clip

    def _get_sampling_config_for_type(self, config: Dict, model_type: str, defaults: Dict) -> Dict:
        """
        Get sampling configuration for a specific model type.
        
        Priority:
        1. Config chain settings (per-variation)
        2. Global config (ModelCompareGlobals)
        3. Node defaults
        """
        sampling_configs = config.get("sampling_configs", []) if config else []
        global_config = config.get("global_config") if config else None
        
        # Map internal model types to config_type names
        type_mapping = {
            "sd": "STANDARD",
            "sdxl": "SDXL",
            "pony": "PONY",
            "wan21": "WAN2.1",
            "wan22": "WAN2.2",
            "hunyuan": "HUNYUAN_VIDEO",
            "hunyuan15": "HUNYUAN_VIDEO_15",
            "qwen": "QWEN",
            "flux": "FLUX",
            "flux2": "FLUX2",
            "sd3": "STANDARD",
            "lumina2": "Z_IMAGE",
        }
        
        config_type = type_mapping.get(model_type, "STANDARD")
        
        # Start with node defaults
        result = dict(defaults)
        
        # Apply global config values (if set)
        if global_config:
            for key, value in global_config.items():
                if value is not None:
                    result[key] = value
                    print(f"[SamplerCompareAdvanced] Global: {key} = {value}")
        
        # Look for matching config in chain (overrides globals)
        for cfg in sampling_configs:
            if cfg.get("config_type") == config_type:
                print(f"[SamplerCompareAdvanced] Found config chain settings for {config_type}")
                # Chain config overrides globals
                for key, value in cfg.items():
                    if key != "config_type" and value is not None:
                        result[key] = value
                return result
        
        if global_config:
            print(f"[SamplerCompareAdvanced] Using global config for {model_type}")
        else:
            print(f"[SamplerCompareAdvanced] No config chain/globals for {model_type}, using node defaults")
        
        return result

    def sample_all_combinations(
        self,
        config: Dict,
        latent: Dict,
        seed: int,
        steps: int,
        cfg: float,
        sampler_name: str,
        scheduler: str,
        denoise: float,
        # Optional parameters
        flux_guidance: float = 3.5,
        qwen_shift: float = 8.0,
        cfg_norm: bool = True,
        cfg_norm_multiplier: float = 0.7,
        wan_shift: float = 8.0,
        wan22_start_step: int = 0,
        wan22_end_step: int = 16,
        hunyuan_shift: float = 7.0,
        video_latent: Optional[Dict] = None,
        start_image: Optional[torch.Tensor] = None,
        end_image: Optional[torch.Tensor] = None,
    ):
        """
        Sample all combinations with LAZY LOADING.
        Models are loaded on-demand and unloaded when config changes.
        
        Uses config chain settings when available, falls back to node parameters.
        """
        from nodes import common_ksampler
        
        combinations = config.get("combinations", []) if config else []
        if not combinations:
            return (torch.zeros(1, 1, 1, 3), config, "No combinations")
        
        # Store default values from node inputs for fallback
        node_defaults = {
            "seed": seed,
            "steps": steps,
            "cfg": cfg,
            "sampler_name": sampler_name,
            "scheduler": scheduler,
            "denoise": denoise,
            "flux_guidance": flux_guidance,
            "qwen_shift": qwen_shift,
            "cfg_norm": cfg_norm,
            "cfg_norm_multiplier": cfg_norm_multiplier,
            "wan_shift": wan_shift,
            "wan22_start_step": wan22_start_step,
            "wan22_end_step": wan22_end_step,
            "hunyuan_shift": hunyuan_shift,
        }
        
        all_images = []
        all_labels = []
        
        # Get latent info
        latent_image = latent["samples"]
        latent_channels = latent_image.shape[1]
        latent_height = latent_image.shape[2] * 8
        latent_width = latent_image.shape[3] * 8
        
        print(f"\n[SamplerCompareAdvanced] Processing {len(combinations)} combinations (LAZY LOADING)")
        print(f"[SamplerCompareAdvanced] Latent shape: {latent_image.shape}")
        
        # Track currently loaded resources for smart unloading
        current_model = None
        current_model_low = None  
        current_vae = None
        current_clip = None
        current_key = None
        current_model_entry = None
        
        for idx, combo in enumerate(combinations):
            print(f"\n[SamplerCompareAdvanced] === Combination {idx + 1}/{len(combinations)} ===")
            
            # Check if we need to reload models (smart unloading)
            new_key = self._get_combo_key(combo, config)
            needs_reload = current_key is None or new_key != current_key
            
            if needs_reload:
                if current_key is not None:
                    print(f"[SamplerCompareAdvanced] Config changed - unloading current models")
                    self._unload_current()
                
                # Get model entry
                model_idx = combo.get("model_index", 0)
                current_model_entry = config["model_variations"][model_idx]
                
                # LAZY LOAD: Model
                current_model, current_model_low = self._load_model(current_model_entry)
                if current_model is None:
                    print(f"[SamplerCompareAdvanced] ERROR: Failed to load model")
                    continue
                
                # LAZY LOAD: VAE
                vae_name = combo.get("vae_name", "NONE")
                current_vae = self._load_vae(vae_name, config, current_model_entry)
                
                # LAZY LOAD: CLIP
                clip_var = combo.get("clip_variation")
                current_clip = self._load_clip(clip_var, config, current_model_entry)
                
                # APPLY LoRAs from combo's lora_config
                lora_config = combo.get("lora_config", {})
                if lora_config and lora_config.get("loras"):
                    # Get model type first for LoRA application
                    clip_type_str = clip_var.get("clip_type", "") if clip_var else ""
                    temp_model_type = clip_type_str if clip_type_str else "sd"
                    current_model, _, current_clip = self._apply_loras(
                        current_model, current_clip, lora_config, temp_model_type
                    )
                
                current_key = new_key
            else:
                print(f"[SamplerCompareAdvanced] Same config - reusing loaded models")
                model_idx = combo.get("model_index", 0)
            
            # Get model type from clip_variation's clip_type
            clip_var = combo.get("clip_variation")
            clip_type_str = clip_var.get("clip_type", "") if clip_var else ""
            
            clip_type_to_model_type = {
                "flux": "flux", "flux2": "flux2", "wan": "wan21", "wan22": "wan22",
                "hunyuan_video": "hunyuan", "hunyuan_video_15": "hunyuan15",
                "qwen": "qwen", "sdxl": "sdxl", "sd": "sd", "sd3": "sd3",
                "lumina2": "lumina2",
            }
            
            if clip_type_str and clip_type_str in clip_type_to_model_type:
                model_type = clip_type_to_model_type[clip_type_str]
                print(f"[SamplerCompareAdvanced] Model type from clip_type: {model_type}")
            else:
                model_type = self.detect_model_type(current_model)
                print(f"[SamplerCompareAdvanced] Auto-detected model type: {model_type}")
            
            # Prepare latent based on model type
            current_latent = latent
            is_video_model = model_type in ['hunyuan', 'hunyuan15', 'wan21', 'wan22']
            num_frames = 1
            
            # Get sampling config for this model type (from chain or use node defaults)
            sampling_cfg = self._get_sampling_config_for_type(config, model_type, node_defaults)
            
            # Extract sampling parameters (prefer config chain, fallback to node defaults)
            use_seed = sampling_cfg.get("seed", seed)
            use_steps = sampling_cfg.get("steps", steps)
            use_cfg = sampling_cfg.get("cfg", cfg)
            use_sampler = sampling_cfg.get("sampler_name", sampler_name)
            use_scheduler = sampling_cfg.get("scheduler", scheduler)
            use_denoise = sampling_cfg.get("denoise", denoise)
            
            # Model-specific parameters
            use_flux_guidance = sampling_cfg.get("flux_guidance", flux_guidance)
            use_qwen_shift = sampling_cfg.get("qwen_shift", qwen_shift)
            use_cfg_norm = sampling_cfg.get("cfg_norm", cfg_norm)
            use_cfg_norm_mult = sampling_cfg.get("cfg_norm_multiplier", cfg_norm_multiplier)
            use_wan_shift = sampling_cfg.get("wan_shift", wan_shift)
            use_wan22_start = sampling_cfg.get("wan22_start_step", wan22_start_step)
            use_wan22_end = sampling_cfg.get("wan22_end_step", wan22_end_step)
            use_hunyuan_shift = sampling_cfg.get("hunyuan_shift", hunyuan_shift)
            
            print(f"[SamplerCompareAdvanced] Using: steps={use_steps}, cfg={use_cfg}, sampler={use_sampler}, scheduler={use_scheduler}")
            
            # FLUX2 needs 128-channel latent
            if model_type == 'flux2' and latent_channels != 128:
                device = comfy.model_management.intermediate_device()
                flux2_latent = torch.zeros(
                    [latent_image.shape[0], 128, latent_image.shape[2] // 2, latent_image.shape[3] // 2],
                    device=device
                )
                current_latent = {"samples": flux2_latent}
                print(f"[SamplerCompareAdvanced] Created FLUX2 latent: {flux2_latent.shape}")
            
            # Video models use video_latent if provided
            elif is_video_model and video_latent is not None:
                current_latent = video_latent
                video_samples = video_latent.get("samples", video_latent)
                if isinstance(video_samples, torch.Tensor) and video_samples.dim() == 5:
                    num_frames = video_samples.shape[2]
                    print(f"[SamplerCompareAdvanced] Using video latent: {video_samples.shape}, {num_frames} frames")
            
            # Clone and patch model
            working_model = current_model
            if hasattr(working_model, 'clone'):
                working_model = working_model.clone()
            
            working_model = self._apply_model_patches(
                working_model, model_type,
                qwen_shift=use_qwen_shift, wan_shift=use_wan_shift, hunyuan_shift=use_hunyuan_shift,
                cfg_norm=use_cfg_norm, cfg_norm_multiplier=use_cfg_norm_mult,
                latent_width=latent_width, latent_height=latent_height
            )
            
            # Encode conditioning with CLIP
            current_positive = [[torch.zeros((1, 77, 768)), {}]]
            current_negative = [[torch.zeros((1, 77, 768)), {}]]
            
            if current_clip:
                pos_text = combo.get("prompt_positive", "")
                neg_text = combo.get("prompt_negative", "")
                
                try:
                    tokens = current_clip.tokenize(pos_text)
                    if model_type in ['flux', 'flux2']:
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": use_flux_guidance})
                    else:
                        current_positive = current_clip.encode_from_tokens_scheduled(tokens)
                    
                    tokens = current_clip.tokenize(neg_text)
                    if model_type in ['flux', 'flux2']:
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens, add_dict={"guidance": use_flux_guidance})
                    else:
                        current_negative = current_clip.encode_from_tokens_scheduled(tokens)
                    
                    print(f"[SamplerCompareAdvanced] Encoded conditioning for {model_type}")
                except Exception as e:
                    print(f"[SamplerCompareAdvanced] Conditioning error: {e}")
            
            # Apply LoRAs
            lora_names = combo.get("lora_names", [])
            lora_strengths = combo.get("lora_strengths", ())
            if lora_names:
                working_model = self._apply_loras(working_model, lora_names, lora_strengths)
            
            # Sample based on model type (using config chain settings)
            try:
                if model_type == 'wan22':
                    # WAN 2.2 two-phase sampling (use current_model_low from lazy loading)
                    # NOTE: WAN 2.2 uses shift=5.0 (not wan_shift which defaults to 8.0 for WAN 2.1)
                    sampled_latent = self._sample_wan22(
                        working_model, current_model_low,
                        use_seed, use_steps, use_cfg, use_sampler, use_scheduler,
                        current_positive, current_negative, current_latent,
                        use_denoise, use_wan22_start, use_wan22_end, wan_shift=5.0
                    )
                else:
                    # Standard sampling for all other models
                    print(f"[SamplerCompareAdvanced] Standard sampling for {model_type}")
                    (latent_out,) = common_ksampler(
                        model=working_model,
                        seed=use_seed,
                        steps=use_steps,
                        cfg=use_cfg,
                        sampler_name=use_sampler,
                        scheduler=use_scheduler,
                        positive=current_positive,
                        negative=current_negative,
                        latent=current_latent,
                        denoise=use_denoise
                    )
                    sampled_latent = latent_out
                
                # Decode
                print(f"[SamplerCompareAdvanced] Decoding...")
                if current_vae is None:
                    print(f"[SamplerCompareAdvanced] ERROR: No VAE loaded for decoding")
                    continue
                image = self._decode_latent(sampled_latent, current_vae, is_video=is_video_model, num_frames=num_frames)
                all_images.append(image)
                
                # Store actual frame count for this combination
                actual_frame_count = image.shape[0]
                combo["output_frame_count"] = actual_frame_count
                
                # Log video output info
                if is_video_model and image.shape[0] > 1:
                    print(f"[SamplerCompareAdvanced] Video output: {image.shape[0]} frames")
                
            except Exception as e:
                print(f"[SamplerCompareAdvanced] Sampling error: {e}")
                import traceback
                traceback.print_exc()
                continue
            
            # Generate label
            label = current_model_entry.get("display_name", current_model_entry.get("name", f"Model {model_idx}"))
            all_labels.append(f"{label} ({model_type})")
            print(f"[SamplerCompareAdvanced] Label: {label} ({model_type})")
        
        # Final cleanup
        self._unload_current()
        
        # Combine images
        if not all_images:
            return (torch.zeros(1, 1, 1, 3), config, "No images")
        
        # Resize if needed
        target_h, target_w = all_images[0].shape[1], all_images[0].shape[2]
        resized_images = []
        for img in all_images:
            if img.shape[1] != target_h or img.shape[2] != target_w:
                img_p = img.permute(0, 3, 1, 2)
                img_r = torch.nn.functional.interpolate(img_p, size=(target_h, target_w), mode='bilinear')
                img = img_r.permute(0, 2, 3, 1)
            resized_images.append(img)
        
        images_tensor = torch.cat(resized_images, dim=0)
        labels_str = "\n".join(all_labels)
        
        return (images_tensor, config, labels_str)
    
    def _apply_model_patches(self, model, model_type: str, **kwargs):
        """Apply model-specific patches based on detected type."""
        
        if model_type == 'qwen':
            # Apply AuraFlow shift
            shift = kwargs.get('qwen_shift', 8.0)
            model = ModelSamplingAuraFlow().patch(model, shift)[0]
            
            # Apply CFG normalization
            if kwargs.get('cfg_norm', True):
                mult = kwargs.get('cfg_norm_multiplier', 0.7)
                model = RescaleCFG().patch(model, mult)[0]
            print(f"[SamplerCompareAdvanced] Applied QWEN patches (shift={shift})")
        
        elif model_type == 'wan21':
            shift = kwargs.get('wan_shift', 8.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
            print(f"[SamplerCompareAdvanced] Applied WAN 2.1 shift={shift}")
        
        elif model_type == 'wan22':
            # WAN 2.2 needs shift=5.0 (NOT 8.0 like WAN 2.1!)
            # This is applied to BOTH high and low noise models
            shift = 5.0  # WAN 2.2 specific shift
            model = ModelSamplingSD3().patch(model, shift)[0]
            print(f"[SamplerCompareAdvanced] Applied WAN 2.2 shift={shift}")
        
        elif model_type in ['hunyuan', 'hunyuan15']:
            shift = kwargs.get('hunyuan_shift', 7.0)
            model = ModelSamplingSD3().patch(model, shift)[0]
            print(f"[SamplerCompareAdvanced] Applied Hunyuan shift={shift}")
        
        elif model_type in ['flux', 'flux2']:
            # FLUX models get shift patching
            latent_width = kwargs.get('latent_width', 1024)
            latent_height = kwargs.get('latent_height', 1024)
            model = ModelSamplingFlux().patch(model, max_shift=1.15, base_shift=0.5, 
                                              width=latent_width, height=latent_height)[0]
            print(f"[SamplerCompareAdvanced] Applied FLUX patches")
        
        return model
    
    def _sample_wan22(self, model_high, model_low, seed, steps, cfg, sampler_name, scheduler,
                      positive, negative, latent, denoise, start_step, end_step, wan_shift=5.0):
        """WAN 2.2 two-phase sampling.
        
        Based on reference workflow:
        - Phase 1 (High Noise): add_noise=enable, return_with_leftover_noise=enable
        - Phase 2 (Low Noise): add_noise=disable, return_with_leftover_noise=disable
        - Split at 50% of steps
        - Shift = 5.0 for BOTH models (NOT 8.0 like WAN 2.1!)
        """
        from nodes import common_ksampler
        from comfy_extras.nodes_model_advanced import ModelSamplingSD3
        
        # WAN 2.2 splits sampling 50/50 between high and low noise models
        mid_step = steps // 2
        
        print(f"[SamplerCompareAdvanced] WAN 2.2 Phase 1: steps 0-{mid_step} (high noise model)")
        
        # Phase 1: High noise model
        # add_noise=enable -> disable_noise=False
        # return_with_leftover_noise=enable -> force_full_denoise=False
        samples_1 = common_ksampler(
            model=model_high, seed=seed, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            positive=positive, negative=negative, latent=latent,
            denoise=denoise,
            disable_noise=False,
            start_step=0,
            last_step=mid_step,
            force_full_denoise=False
        )[0]
        
        if model_low is None:
            print(f"[SamplerCompareAdvanced] No low noise model, returning after phase 1")
            return samples_1
        
        # Apply shift=5.0 to low noise model (same as high noise model)
        model_low_patched = ModelSamplingSD3().patch(model_low, wan_shift)[0]
        print(f"[SamplerCompareAdvanced] Applied WAN 2.2 shift={wan_shift} to low noise model")
        
        print(f"[SamplerCompareAdvanced] WAN 2.2 Phase 2: steps {mid_step}-{steps} (low noise model)")
        
        # Phase 2: Low noise model
        # add_noise=disable -> disable_noise=True
        # return_with_leftover_noise=disable -> force_full_denoise=True
        samples_2 = common_ksampler(
            model=model_low_patched, seed=seed, steps=steps, cfg=cfg,
            sampler_name=sampler_name, scheduler=scheduler,
            positive=positive, negative=negative, latent=samples_1,
            denoise=denoise,
            disable_noise=True,
            start_step=mid_step,
            last_step=steps,
            force_full_denoise=True
        )[0]
        
        return samples_2
    
    @staticmethod
    def _apply_loras(model, lora_names: List[str], strengths: Tuple[float, ...]):
        """Apply LoRAs to the model."""
        working_model = model
        for lora_name, strength in zip(lora_names, strengths):
            if strength == 0.0:
                continue
            lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
            lora_data = comfy.utils.load_torch_file(lora_path, safe_load=True)
            working_model, _ = comfy.sd.load_lora_for_models(working_model, None, lora_data, strength, strength)
        return working_model
    
    @staticmethod
    def _decode_latent(latent_dict, vae, is_video=False, num_frames=1):
        """Decode latent samples to image using VAE.
        
        For video models, returns all frames as [F, H, W, C] tensor.
        For image models, returns [B, H, W, C] tensor.
        """
        samples = latent_dict["samples"] if isinstance(latent_dict, dict) else latent_dict
        image = vae.decode(samples)
        
        # Handle 5D video output
        # Common shapes after VAE decode:
        # - [B, F, H, W, C] where C=3 (most common for video VAEs)
        # - [B, C, F, H, W] where C=3 (less common)
        if image.dim() == 5:
            # Check if last dimension is channels (C=3)
            if image.shape[-1] == 3:  # [B, F, H, W, C]
                if is_video:
                    # Video model - squeeze batch and return [F, H, W, C]
                    image = image.squeeze(0)
                    print(f"[SamplerCompareAdvanced] Video decoded: {image.shape[0]} frames")
                else:
                    # Image model - take first frame
                    image = image[:, 0, :, :, :]  # [B, H, W, C]
            elif image.shape[1] == 3:  # [B, C, F, H, W]
                # Permute to [B, F, H, W, C] first
                image = image.permute(0, 2, 3, 4, 1)
                if is_video:
                    image = image.squeeze(0)  # [F, H, W, C]
                else:
                    image = image[:, 0, :, :, :]  # [B, H, W, C]
            else:
                # Unknown format - try best effort
                print(f"[SamplerCompareAdvanced] Note: Video shape {image.shape}, using squeeze")
                image = image.squeeze(0)
        
        return image
    
    @classmethod
    def IS_CHANGED(cls, config, latent, seed, steps, cfg, sampler_name, scheduler, denoise, **kwargs):
        """
        Compute a hash to determine if re-execution is needed.
        This prevents unnecessary re-runs when workflow is queued without changes.
        """
        # Hash the config combinations (model paths, not objects)
        combos = config.get("combinations", []) if config else []
        combo_str = str([(c.get("model_index"), c.get("vae_name"), c.get("prompt_positive", "")) for c in combos])
        
        # Hash sampling configs from chain
        sampling_configs = config.get("sampling_configs", []) if config else []
        sampling_str = str([(sc.get("config_type"), sc.get("steps"), sc.get("cfg"), sc.get("sampler_name")) for sc in sampling_configs])
        
        # Hash node's own sampling params (used as defaults)
        params = f"{seed}|{steps}|{cfg}|{sampler_name}|{scheduler}|{denoise}"
        
        # Hash latent shape
        latent_shape = str(latent.get("samples").shape) if isinstance(latent, dict) and latent else "unknown"
        
        # Combine and hash
        hash_input = f"{combo_str}|{sampling_str}|{params}|{latent_shape}"
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if isinstance(val, (str, int, float, bool)):
                hash_input += f"|{key}:{val}"
        
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "SamplerCompareAdvanced": SamplerCompareAdvanced,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "SamplerCompareAdvanced": "Sampler Compare Advanced",
}
