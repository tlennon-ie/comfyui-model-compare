# ComfyUI Model Compare - AI Coding Agent Instructions

## Project Overview
A ComfyUI custom node package for visual model/VAE/CLIP/LoRA comparison with lazy loading and grid generation. Located in `custom_nodes/comfyui-model-compare/`.

**SCOPE**: Only modify files within this custom node folder. The parent ComfyUI directory is reference-only.

## Architecture

### Data Flow & Config Passing Pattern
Nodes communicate via a `MODEL_COMPARE_CONFIG` dict that accumulates settings:
```
PromptCompare → ModelCompareLoaders → SamplingConfigChain(s) → SamplerCompareAdvanced → GridCompare
       ↓               ↓                      ↓
PROMPT_COMPARE_CONFIG → MODEL_COMPARE_CONFIG → (adds sampling_configs[idx])
```

### Key Architectural Patterns

1. **Lazy Loading** (`sampler_compare_advanced.py`): Models load on-demand per combination, unload on config change. All paths stored in config, no model objects passed between nodes.

2. **Config Dict Structure**: Main config contains:
   - `model_variations[]`: Model entries with `model_path`, `display_name`, `use_baked_vae_clip`
   - `vae_paths{}`: Map name→path for lazy loading
   - `clip_variations[]`: CLIP configs with `type` (single/pair/baked), paths, `clip_type`
   - `lora_configs[]`: Per-variation LoRA from LoRA Compare nodes
   - `sampling_configs{}`: Per-variation params from SamplingConfigChain (keyed by variation_index-1)
   - `combinations[]`: Computed list with `model_index`, `vae_name`, `clip_variation`, `lora_config`, `prompt_*`

3. **Multi-Value Expansion** (`variation_expander.py`): Comma-separated strings expand to multiple combinations. Handled in `_expand_combinations_with_sampling_variations()`.

### Core Files

| File | Purpose |
|------|---------|
| `__init__.py` | Node registration, merges `NODE_CLASS_MAPPINGS` from all modules |
| `model_compare_loaders.py` | Central config builder, preset system, path collection |
| `sampler_compare_advanced.py` | Lazy model loading, sampling, caching, model patching |
| `sampling_config_chain.py` | Per-variation params (chainable), multi-value parsing |
| `lora_compare.py` | LoRA config with AND/OR combinators, strength variations |
| `grid_compare.py` | Grid layout, smart axis detection, HTML/video output |
| `gallery_routes.py` | Web routes for `/model-compare/gallery` |
| `variation_expander.py` | Multi-value parsing utilities |

## Node Development Patterns

### Creating a Node
```python
class MyNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {"config": ("MODEL_COMPARE_CONFIG",)},
            "optional": {},
        }
    
    RETURN_TYPES = ("MODEL_COMPARE_CONFIG",)  # Pass config through
    RETURN_NAMES = ("config",)
    FUNCTION = "process"
    CATEGORY = "Model Compare"  # Use "Model Compare" or "Model Compare/Loaders"
    
    def process(self, config, **kwargs):
        new_config = copy.deepcopy(config)  # Always deep copy
        # Modify new_config
        return (new_config,)
    
    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Return hash for caching
        return hashlib.md5(str(kwargs).encode()).hexdigest()
```

### Register in `__init__.py`:
```python
from .my_node import NODE_CLASS_MAPPINGS as MY_MAPPINGS
NODE_CLASS_MAPPINGS = {..., **MY_MAPPINGS}
```

## Supported Model Types
Handled via `config_type` in SamplingConfigChain and `clip_type` in loader:
- `sd`, `sdxl`, `pony` - Standard/SDXL sampling
- `flux`, `flux2`, `flux_kontext` - FLUX variants with guidance
- `qwen`, `qwen_edit` - AuraFlow sampling, shift=1.15, CFG normalization
- `z_image` - Lumina2, AuraFlow shift=3.0
- `wan21`, `wan22` - Video, shift=8.0, WAN22 has two-phase sampling
- `hunyuan`, `hunyuan15` - Hunyuan video with shift

Model patching in `_apply_model_patches()` uses ComfyUI's `ModelSamplingSD3`, `ModelSamplingAuraFlow`, `ModelSamplingFlux`.

## Web Components
- `web/js/model_compare.js`: Frontend JS loaded by ComfyUI
- `web/model_compare_types.js`: Custom type definitions for UI
- Routes registered via `aiohttp` in `gallery_routes.py`, `preset_routes.py`

## Testing
No test framework currently. Manual testing via ComfyUI workflows in `examples/`.

## Common Operations

### Add New Model Type
1. Add to `config_type` list in `sampling_config_chain.py` INPUT_TYPES
2. Add to `preset` list in `model_compare_loaders.py`
3. Add clip_type mapping in `_get_clip_type_enum()` (both loader and sampler)
4. Add model patching in `_apply_model_patches()` in sampler
5. Add tokenization branch in `sample_all_combinations()` if needed

### Add New Sampling Parameter
1. Add to `SamplingConfigChain.INPUT_TYPES` (use STRING for multi-value support)
2. Parse in `apply_config()` using variation_expander helpers
3. Store in `sampling_config` dict
4. Apply in `SamplerCompareAdvanced.sample_all_combinations()`

### Add Grid Layout Option
1. Add to `axis_options` in `GridCompare.INPUT_TYPES`
2. Handle in `_detect_varying_dimensions()` and `_get_combo_field_value()`

## Key Dependencies
- `comfy.sd` - Model/VAE/CLIP loading (`load_checkpoint_guess_config`, `load_diffusion_model`, `load_clip`, `load_lora_for_models`)
- `comfy.model_management` - VRAM management (`unload_all_models`, `cleanup_models`)
- `comfy.samplers` - Available samplers/schedulers
- `folder_paths` - ComfyUI model paths (`get_filename_list`, `get_full_path`)
- `PIL` - Grid image generation

## Conventions
- Emoji prefix `Ⓜ️` in `NODE_DISPLAY_NAME_MAPPINGS` for visibility
- Config always deep-copied before modification
- Use `print(f"[NodeName] ...")` for logging
- Strengths stored as floats, parsed from comma-separated strings
- Model names cleaned by removing `.safetensors` extension for display
