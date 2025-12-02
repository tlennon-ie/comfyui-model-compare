"""
Model Loader Utilities

Centralized model loading with caching, error handling, and memory management.
This module provides a unified interface for loading models, VAEs, CLIPs, and LoRAs
with support for lazy loading and resource reuse.

Architecture:
- ModelCache: Singleton LRU cache for loaded models
- load_* functions: High-level loading with automatic caching
- ModelLoadingContext: Context manager for coordinated loading with cleanup
"""

import os
import time
import weakref
import hashlib
import threading
from typing import Dict, Any, Optional, Tuple, List, Union
from dataclasses import dataclass, field
from enum import Enum
from collections import OrderedDict

import torch
import comfy.sd
import comfy.utils
import comfy.model_management
import folder_paths


class ModelType(Enum):
    """Types of models that can be loaded."""
    CHECKPOINT = "checkpoint"
    DIFFUSION = "diffusion"
    VAE = "vae"
    CLIP = "clip"
    LORA = "lora"


@dataclass
class CachedModel:
    """Container for a cached model with metadata."""
    model: Any
    model_type: ModelType
    path: str
    load_time: float
    last_access: float
    size_estimate_mb: float = 0.0
    ref_count: int = 0
    
    def touch(self):
        """Update last access time."""
        self.last_access = time.time()
        
    def add_ref(self):
        """Increment reference count."""
        self.ref_count += 1
        self.touch()
        
    def release_ref(self):
        """Decrement reference count."""
        self.ref_count = max(0, self.ref_count - 1)


class ModelCache:
    """
    LRU cache for loaded models with memory-aware eviction.
    
    Features:
    - Reference counting for safe eviction
    - Memory pressure detection
    - Thread-safe operations
    - Configurable size limits
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, max_models: int = 10, max_memory_mb: float = 16000):
        if self._initialized:
            return
            
        self._cache: OrderedDict[str, CachedModel] = OrderedDict()
        self._max_models = max_models
        self._max_memory_mb = max_memory_mb
        self._total_memory_mb = 0.0
        self._cache_lock = threading.RLock()
        self._initialized = True
        
        print(f"[ModelCache] Initialized with max_models={max_models}, max_memory_mb={max_memory_mb}")
    
    def _make_cache_key(self, model_type: ModelType, path: str, **kwargs) -> str:
        """Generate a unique cache key."""
        # Include relevant kwargs in the key (e.g., clip_type for CLIP models)
        extra = "|".join(f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None)
        key_str = f"{model_type.value}|{path}|{extra}"
        return hashlib.md5(key_str.encode()).hexdigest()[:16]
    
    def get(self, model_type: ModelType, path: str, **kwargs) -> Optional[Any]:
        """Get a model from cache if available."""
        key = self._make_cache_key(model_type, path, **kwargs)
        
        with self._cache_lock:
            if key in self._cache:
                entry = self._cache[key]
                entry.touch()
                # Move to end (most recently used)
                self._cache.move_to_end(key)
                print(f"[ModelCache] Cache hit for {model_type.value}: {os.path.basename(path)}")
                return entry.model
        
        return None
    
    def put(self, model_type: ModelType, path: str, model: Any, 
            size_estimate_mb: float = 0.0, **kwargs) -> str:
        """Add a model to the cache."""
        key = self._make_cache_key(model_type, path, **kwargs)
        
        with self._cache_lock:
            # Evict if necessary
            self._ensure_capacity(size_estimate_mb)
            
            entry = CachedModel(
                model=model,
                model_type=model_type,
                path=path,
                load_time=time.time(),
                last_access=time.time(),
                size_estimate_mb=size_estimate_mb,
                ref_count=1
            )
            
            self._cache[key] = entry
            self._total_memory_mb += size_estimate_mb
            
            print(f"[ModelCache] Cached {model_type.value}: {os.path.basename(path)} "
                  f"({size_estimate_mb:.0f}MB, total: {self._total_memory_mb:.0f}MB)")
        
        return key
    
    def acquire(self, key: str) -> Optional[Any]:
        """Acquire a reference to a cached model."""
        with self._cache_lock:
            if key in self._cache:
                entry = self._cache[key]
                entry.add_ref()
                return entry.model
        return None
    
    def release(self, key: str):
        """Release a reference to a cached model."""
        with self._cache_lock:
            if key in self._cache:
                self._cache[key].release_ref()
    
    def _ensure_capacity(self, required_mb: float):
        """Evict models if necessary to make room."""
        # Check model count
        while len(self._cache) >= self._max_models:
            self._evict_one()
        
        # Check memory
        while self._total_memory_mb + required_mb > self._max_memory_mb and self._cache:
            self._evict_one()
    
    def _evict_one(self):
        """Evict the least recently used model with ref_count=0."""
        for key, entry in list(self._cache.items()):
            if entry.ref_count == 0:
                self._total_memory_mb -= entry.size_estimate_mb
                del self._cache[key]
                print(f"[ModelCache] Evicted {entry.model_type.value}: {os.path.basename(entry.path)}")
                return
        
        # If all models are in use, evict oldest anyway
        if self._cache:
            key, entry = next(iter(self._cache.items()))
            self._total_memory_mb -= entry.size_estimate_mb
            del self._cache[key]
            print(f"[ModelCache] Force evicted {entry.model_type.value}: {os.path.basename(entry.path)}")
    
    def clear(self):
        """Clear all cached models."""
        with self._cache_lock:
            self._cache.clear()
            self._total_memory_mb = 0.0
            print("[ModelCache] Cache cleared")
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._cache_lock:
            return {
                "count": len(self._cache),
                "max_models": self._max_models,
                "total_memory_mb": self._total_memory_mb,
                "max_memory_mb": self._max_memory_mb,
                "models": [
                    {
                        "type": e.model_type.value,
                        "path": os.path.basename(e.path),
                        "size_mb": e.size_estimate_mb,
                        "ref_count": e.ref_count,
                        "age_seconds": time.time() - e.load_time
                    }
                    for e in self._cache.values()
                ]
            }


# Global cache instance
_model_cache = ModelCache()


def get_model_cache() -> ModelCache:
    """Get the global model cache instance."""
    return _model_cache


def estimate_model_size(path: str, model_type: ModelType) -> float:
    """Estimate model size in MB based on file size."""
    try:
        if path and os.path.exists(path):
            size_bytes = os.path.getsize(path)
            # Models typically use 2-4x file size in memory
            multiplier = 3.0 if model_type == ModelType.CHECKPOINT else 2.5
            return (size_bytes / (1024 * 1024)) * multiplier
    except Exception:
        pass
    
    # Default estimates by type
    defaults = {
        ModelType.CHECKPOINT: 4000,
        ModelType.DIFFUSION: 8000,
        ModelType.VAE: 300,
        ModelType.CLIP: 2000,
        ModelType.LORA: 200,
    }
    return defaults.get(model_type, 1000)


def load_checkpoint(path: str, use_cache: bool = True) -> Tuple[Any, Any, Any]:
    """
    Load a checkpoint file, returning (model, clip, vae).
    
    Args:
        path: Full path to checkpoint file
        use_cache: Whether to use caching
        
    Returns:
        Tuple of (model, clip, vae) - any may be None
    """
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Checkpoint not found: {path}")
    
    cache = get_model_cache()
    
    # Check cache
    if use_cache:
        cached = cache.get(ModelType.CHECKPOINT, path)
        if cached:
            return cached  # Returns (model, clip, vae) tuple
    
    print(f"[ModelLoader] Loading checkpoint: {os.path.basename(path)}")
    start_time = time.time()
    
    try:
        result = comfy.sd.load_checkpoint_guess_config(
            path,
            output_vae=True,
            output_clip=True,
            embedding_directory=folder_paths.get_folder_paths("embeddings")
        )
        
        model = result[0]
        clip = result[1]
        vae = result[2]
        
        load_time = time.time() - start_time
        print(f"[ModelLoader] Loaded checkpoint in {load_time:.2f}s")
        
        if use_cache:
            size = estimate_model_size(path, ModelType.CHECKPOINT)
            cache.put(ModelType.CHECKPOINT, path, (model, clip, vae), size)
        
        return (model, clip, vae)
        
    except Exception as e:
        print(f"[ModelLoader] Error loading checkpoint: {e}")
        raise


def load_diffusion_model(path: str, use_cache: bool = True) -> Any:
    """
    Load a diffusion/UNET model file.
    
    Args:
        path: Full path to diffusion model file
        use_cache: Whether to use caching
        
    Returns:
        Loaded model object
    """
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Diffusion model not found: {path}")
    
    cache = get_model_cache()
    
    # Check cache
    if use_cache:
        cached = cache.get(ModelType.DIFFUSION, path)
        if cached:
            return cached
    
    print(f"[ModelLoader] Loading diffusion model: {os.path.basename(path)}")
    start_time = time.time()
    
    try:
        model = comfy.sd.load_diffusion_model(path)
        
        load_time = time.time() - start_time
        print(f"[ModelLoader] Loaded diffusion model in {load_time:.2f}s")
        
        if use_cache:
            size = estimate_model_size(path, ModelType.DIFFUSION)
            cache.put(ModelType.DIFFUSION, path, model, size)
        
        return model
        
    except Exception as e:
        print(f"[ModelLoader] Error loading diffusion model: {e}")
        raise


def load_vae(path: str, use_cache: bool = True) -> Any:
    """
    Load a VAE model file.
    
    Args:
        path: Full path to VAE file
        use_cache: Whether to use caching
        
    Returns:
        Loaded VAE object
    """
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"VAE not found: {path}")
    
    cache = get_model_cache()
    
    # Check cache
    if use_cache:
        cached = cache.get(ModelType.VAE, path)
        if cached:
            return cached
    
    print(f"[ModelLoader] Loading VAE: {os.path.basename(path)}")
    start_time = time.time()
    
    try:
        vae = comfy.sd.VAE(sd=comfy.utils.load_torch_file(path))
        
        load_time = time.time() - start_time
        print(f"[ModelLoader] Loaded VAE in {load_time:.2f}s")
        
        if use_cache:
            size = estimate_model_size(path, ModelType.VAE)
            cache.put(ModelType.VAE, path, vae, size)
        
        return vae
        
    except Exception as e:
        print(f"[ModelLoader] Error loading VAE: {e}")
        raise


def load_clip(
    path: str,
    clip_type: str = "sd",
    path_b: Optional[str] = None,
    device: str = "default",
    use_cache: bool = True
) -> Any:
    """
    Load a CLIP model (single or dual).
    
    Args:
        path: Full path to primary CLIP file
        clip_type: Type string (sd, sdxl, flux, etc.)
        path_b: Optional second CLIP path for dual CLIP models
        device: Device to load to ("default" or "cpu")
        use_cache: Whether to use caching
        
    Returns:
        Loaded CLIP object
    """
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"CLIP not found: {path}")
    
    cache = get_model_cache()
    cache_key_kwargs = {"clip_type": clip_type, "path_b": path_b, "device": device}
    
    # Check cache
    if use_cache:
        cached = cache.get(ModelType.CLIP, path, **cache_key_kwargs)
        if cached:
            return cached
    
    is_dual = path_b and os.path.exists(path_b)
    print(f"[ModelLoader] Loading {'dual ' if is_dual else ''}CLIP ({clip_type}): {os.path.basename(path)}")
    start_time = time.time()
    
    try:
        # Resolve clip type enum
        clip_type_enum = _get_clip_type_enum(clip_type)
        
        # Determine device
        if device == "cpu":
            load_device = torch.device("cpu")
        else:
            load_device = comfy.model_management.text_encoder_device()
        
        # Load single or dual CLIP
        if is_dual:
            clip = comfy.sd.load_clip(
                ckpt_paths=[path, path_b],
                embedding_directory=folder_paths.get_folder_paths("embeddings"),
                clip_type=clip_type_enum
            )
        else:
            clip = comfy.sd.load_clip(
                ckpt_paths=[path],
                embedding_directory=folder_paths.get_folder_paths("embeddings"),
                clip_type=clip_type_enum
            )
        
        load_time = time.time() - start_time
        print(f"[ModelLoader] Loaded CLIP in {load_time:.2f}s")
        
        if use_cache:
            size = estimate_model_size(path, ModelType.CLIP)
            if is_dual:
                size += estimate_model_size(path_b, ModelType.CLIP)
            cache.put(ModelType.CLIP, path, clip, size, **cache_key_kwargs)
        
        return clip
        
    except Exception as e:
        print(f"[ModelLoader] Error loading CLIP: {e}")
        raise


def load_lora(
    model: Any,
    clip: Any,
    lora_path: str,
    strength_model: float = 1.0,
    strength_clip: float = 1.0,
    use_cache: bool = False  # LoRAs are typically not cached (applied per-model)
) -> Tuple[Any, Any]:
    """
    Apply a LoRA to model and clip.
    
    Args:
        model: Model to apply LoRA to
        clip: CLIP to apply LoRA to (can be None)
        lora_path: Full path to LoRA file
        strength_model: LoRA strength for model
        strength_clip: LoRA strength for CLIP
        use_cache: Whether to cache the loaded LoRA data
        
    Returns:
        Tuple of (model_with_lora, clip_with_lora)
    """
    if not lora_path or not os.path.exists(lora_path):
        print(f"[ModelLoader] LoRA not found, skipping: {lora_path}")
        return model, clip
    
    print(f"[ModelLoader] Applying LoRA: {os.path.basename(lora_path)} "
          f"(model={strength_model}, clip={strength_clip})")
    
    try:
        # Load LoRA data
        lora_data = comfy.utils.load_torch_file(lora_path, safe_load=True)
        
        # Apply to model
        model_lora, clip_lora = comfy.sd.load_lora_for_models(
            model, clip, lora_data, strength_model, strength_clip
        )
        
        return model_lora, clip_lora
        
    except Exception as e:
        print(f"[ModelLoader] Error applying LoRA: {e}")
        return model, clip


def _get_clip_type_enum(clip_type_str: str):
    """Resolve CLIP type string to enum."""
    mapping = {
        "sd": comfy.sd.CLIPType.STABLE_DIFFUSION,
        "sdxl": comfy.sd.CLIPType.STABLE_DIFFUSION,
        "sd3": getattr(comfy.sd.CLIPType, "SD3", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "flux": getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "flux2": getattr(comfy.sd.CLIPType, "FLUX2", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "flux_kontext": getattr(comfy.sd.CLIPType, "FLUX_KONTEXT", 
                               getattr(comfy.sd.CLIPType, "FLUX", comfy.sd.CLIPType.STABLE_DIFFUSION)),
        "wan": getattr(comfy.sd.CLIPType, "WAN", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "wan22": getattr(comfy.sd.CLIPType, "WAN", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "hunyuan_video": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "hunyuan_video_15": getattr(comfy.sd.CLIPType, "HUNYUAN_VIDEO_15", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "qwen": getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION),
        "qwen_edit": getattr(comfy.sd.CLIPType, "QWEN_IMAGE_EDIT", 
                            getattr(comfy.sd.CLIPType, "QWEN_IMAGE", comfy.sd.CLIPType.STABLE_DIFFUSION)),
        "lumina2": getattr(comfy.sd.CLIPType, "LUMINA2", comfy.sd.CLIPType.STABLE_DIFFUSION),
    }
    
    # Try direct enum lookup
    key = clip_type_str.upper().replace("_", "")
    if hasattr(comfy.sd.CLIPType, key):
        return getattr(comfy.sd.CLIPType, key)
    
    return mapping.get(clip_type_str, comfy.sd.CLIPType.STABLE_DIFFUSION)


class ModelLoadingContext:
    """
    Context manager for coordinated model loading.
    
    Ensures proper cleanup and reference management when loading
    multiple models for a comparison batch.
    
    Usage:
        with ModelLoadingContext() as ctx:
            model = ctx.load_model(path)
            vae = ctx.load_vae(vae_path)
            # Use models...
        # Models are released when context exits
    """
    
    def __init__(self):
        self._loaded_keys: List[str] = []
        self._cache = get_model_cache()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Release all acquired references
        for key in self._loaded_keys:
            self._cache.release(key)
        self._loaded_keys.clear()
        return False
    
    def load_model(self, path: str, model_type: str = "diffusion") -> Any:
        """Load a model within this context."""
        if model_type == "checkpoint":
            result = load_checkpoint(path)
            return result[0]  # Return just the model
        else:
            return load_diffusion_model(path)
    
    def load_vae(self, path: str) -> Any:
        """Load a VAE within this context."""
        return load_vae(path)
    
    def load_clip(self, path: str, clip_type: str = "sd", 
                  path_b: Optional[str] = None, device: str = "default") -> Any:
        """Load a CLIP within this context."""
        return load_clip(path, clip_type, path_b, device)


# Export public API
__all__ = [
    'ModelType',
    'ModelCache',
    'get_model_cache',
    'load_checkpoint',
    'load_diffusion_model',
    'load_vae',
    'load_clip',
    'load_lora',
    'ModelLoadingContext',
    'estimate_model_size',
]
