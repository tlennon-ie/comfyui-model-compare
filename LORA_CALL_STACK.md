# LoRA Patch Application Flow - Code Reference

## Complete Call Stack: From LoRA Loading to Weight Modification

```
YOUR CODE
├─ combo_model = load_checkpoint(...)
│  └─ Returns: ModelPatcher with model.patches = {}
│
├─ lora_data = load_torch_file("lora.safetensors")
│
├─ combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, strength, 0)
│  │
│  ├─ NEW FILE: comfy/sd.py:65
│  │ def load_lora_for_models(model, clip, lora, strength_model, strength_clip):
│  │   ├─ key_map = comfy.lora.model_lora_keys_unet(model.model, {})
│  │   ├─ loaded = comfy.lora.load_lora(lora, key_map)
│  │   │  └─ Returns: {key_name: (lora_down, lora_up, ...)}
│  │   ├─ new_modelpatcher = model.clone()
│  │   │  └─ Returns: NEW ModelPatcher instance
│  │   └─ k = new_modelpatcher.add_patches(loaded, strength_model)
│  │      │
│  │      ├─ FILE: comfy/model_patcher.py:550
│  │      │ def add_patches(patches, strength_patch=1.0, strength_model=1.0):
│  │      │   for k in patches:
│  │      │     if key in model_sd:
│  │      │       current_patches = self.patches.get(key, [])
│  │      │       # Stores as tuple: (strength_patch, patch_data, strength_model, offset, function)
│  │      │       current_patches.append((strength_patch, patches[k], strength_model, offset, function))
│  │      │       self.patches[key] = current_patches
│  │      └─ ✓ PATCHES NOW IN: combo_model.patches = {key: [(str, data, str, ...)], ...}
│  │
│  └─ Returns: (combo_model_with_patches, None)
│
├─ # NOW: combo_model.patches contains all LoRA data
│  # BUT: Patches are NOT YET applied to model weights
│
├─ samples_out = comfy.sample.sample(combo_model, noise, steps, cfg, ...)
│  │
│  ├─ FILE: comfy/sample.py:56
│  │ def sample(model, noise, steps, cfg, sampler_name, scheduler, positive, negative, latent_image, ...):
│  │   ├─ sampler = comfy.samplers.KSampler(model, ...)
│  │   └─ samples = sampler.sample(noise, positive, negative, cfg=cfg, ...)
│  │      │
│  │      ├─ FILE: comfy/samplers.py:1045
│  │      │ class KSampler.sample(...):
│  │      │   └─ return sample(self.model, noise, positive, negative, cfg, self.device, sampler, sigmas, ...)
│  │      │      │
│  │      │      ├─ FILE: comfy/samplers.py:1028
│  │      │      │ def sample(model, noise, positive, negative, cfg, device, sampler, sigmas, ...):
│  │      │      │   ├─ cfg_guider = CFGGuider(model)  ← WRAPS ModelPatcher
│  │      │      │   ├─ cfg_guider.set_conds(positive, negative)
│  │      │      │   └─ return cfg_guider.sample(noise, latent_image, sampler, sigmas, ...)
│  │      │      │      │
│  │      │      │      ├─ FILE: comfy/samplers.py:938
│  │      │      │      │ def CFGGuider.sample(...):
│  │      │      │      │   └─ return self.outer_sample(noise, latent_image, sampler, sigmas, ...)
│  │      │      │      │      │
│  │      │      │      │      ├─ FILE: comfy/samplers.py:976
│  │      │      │      │      │ def CFGGuider.outer_sample(...):
│  │      │      │      │      │   │
│  │      │      │      │      │   ├─ ★★★ CRITICAL CALL ★★★
│  │      │      │      │      │   │
│  │      │      │      │      │   ├─ self.inner_model, self.conds, self.loaded_models = \
│  │      │      │      │      │   │    comfy.sampler_helpers.prepare_sampling(
│  │      │      │      │      │   │        self.model_patcher,  ← combo_model (with patches)
│  │      │      │      │      │   │        noise.shape,
│  │      │      │      │      │   │        self.conds,
│  │      │      │      │      │   │        self.model_options
│  │      │      │      │      │   │    )
│  │      │      │      │      │   │
│  │      │      │      │      │   ├─ FILE: comfy/sampler_helpers.py:125
│  │      │      │      │      │   │ def prepare_sampling(model, noise_shape, conds, model_options):
│  │      │      │      │      │   │   └─ executor.execute(model, noise_shape, conds, model_options)
│  │      │      │      │      │   │      └─ _prepare_sampling(model, noise_shape, conds, model_options)
│  │      │      │      │      │   │         │
│  │      │      │      │      │   │         ├─ FILE: comfy/sampler_helpers.py:132
│  │      │      │      │      │   │         │ def _prepare_sampling(...):
│  │      │      │      │      │   │         │   models, inference_memory = get_additional_models(...)
│  │      │      │      │      │   │         │   memory_required, minimum_memory_required = estimate_memory(...)
│  │      │      │      │      │   │         │   
│  │      │      │      │      │   │         │   ★★★ THIS IS WHERE PATCHES ARE APPLIED ★★★
│  │      │      │      │      │   │         │
│  │      │      │      │      │   │         └─ comfy.model_management.load_models_gpu(
│  │      │      │      │      │   │              [model] + models,
│  │      │      │      │      │   │              memory_required=memory_required + inference_memory,
│  │      │      │      │      │   │              minimum_memory_required=minimum_memory_required + inference_memory
│  │      │      │      │      │   │          )
│  │      │      │      │      │   │             │
│  │      │      │      │      │   │             ├─ FILE: comfy/model_management.py:618
│  │      │      │      │      │   │             │ def load_models_gpu(models, memory_required=0, ...):
│  │      │      │      │      │   │             │   for loaded_model in models_to_load:
│  │      │      │      │      │   │             │     loaded_model.model_load(lowvram_model_memory, force_patch_weights)
│  │      │      │      │      │   │             │        │
│  │      │      │      │      │   │             │        ├─ FILE: comfy/model_management.py:498
│  │      │      │      │      │   │             │        │ def LoadedModel.model_load(lowvram_model_memory, force_patch_weights):
│  │      │      │      │      │   │             │        │   ├─ self.model.model_patches_to(self.device)
│  │      │      │      │      │   │             │        │   ├─ self.model.model_patches_to(self.model.model_dtype())
│  │      │      │      │      │   │             │        │   └─ self.model_use_more_vram(use_more_vram, force_patch_weights)
│  │      │      │      │      │   │             │        │      └─ self.model.partially_load(self.device, extra_memory, ...)
│  │      │      │      │      │   │             │        │         └─ self.load(device_to, lowvram_model_memory, ...)
│  │      │      │      │      │   │             │        │            │
│  │      │      │      │      │   │             │        │            ├─ FILE: comfy/model_patcher.py:656
│  │      │      │      │      │   │             │        │            │ def ModelPatcher.load(...):
│  │      │      │      │      │   │             │        │            │   # Iterates through model modules
│  │      │      │      │      │   │             │        │            │   loading = self._load_list()  # All modules with params
│  │      │      │      │      │   │             │        │            │   
│  │      │      │      │      │   │             │        │            │   for x in load_completely:
│  │      │      │      │      │   │             │        │            │     n = x[1]  # module name
│  │      │      │      │      │   │             │        │            │     m = x[2]  # module object
│  │      │      │      │      │   │             │        │            │     params = x[3]  # param names: ['weight', 'bias']
│  │      │      │      │      │   │             │        │            │     
│  │      │      │      │      │   │             │        │            │     for param in params:
│  │      │      │      │      │   │             │        │            │       key = f"{n}.{param}"  # e.g., "diffusion_model.input_blocks.0.0.weight"
│  │      │      │      │      │   │             │        │            │       
│  │      │      │      │      │   │             │        │            │       ★★★ PATCHES APPLIED HERE ★★★
│  │      │      │      │      │   │             │        │            │       self.patch_weight_to_device(key, device_to=device_to)
│  │      │      │      │      │   │             │        │            │
│  │      │      │      │      │   │             │        │            └─ (continues below)
│  │      │      │      │      │   │             │        │
│  │      │      │      │      │   │             │        └─ FILE: comfy/model_patcher.py:609
│  │      │      │      │      │   │             │           def patch_weight_to_device(key, device_to=None, inplace_update=False):
│  │      │      │      │      │   │             │             if key not in self.patches:
│  │      │      │      │      │   │             │               return  # No patch for this key
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             weight, set_func, convert_func = get_key_weight(self.model, key)
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             if key not in self.backup:
│  │      │      │      │      │   │             │               # Save original weight (for restoration later)
│  │      │      │      │      │   │             │               self.backup[key] = (weight.to(offload_device, copy=True), inplace)
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             # Convert to float32 for calculation
│  │      │      │      │      │   │             │             temp_weight = cast_to_device(weight, device_to, torch.float32, copy=True)
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             if convert_func is not None:
│  │      │      │      │      │   │             │               temp_weight = convert_func(temp_weight, inplace=True)
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             ★★★ CALCULATE PATCHED WEIGHT ★★★
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             out_weight = comfy.lora.calculate_weight(
│  │      │      │      │      │   │             │               self.patches[key],  # List of LoRA patches
│  │      │      │      │      │   │             │               temp_weight,       # Original weight
│  │      │      │      │      │   │             │               key               # Name for logging
│  │      │      │      │      │   │             │             )
│  │      │      │      │      │   │             │             
│  │      │      │      │      │   │             │             # Apply rounding and set into model
│  │      │      │      │      │   │             │             out_weight = stochastic_rounding(out_weight, weight.dtype, seed=...)
│  │      │      │      │      │   │             │             comfy.utils.set_attr_param(self.model, key, out_weight)
│  │      │      │      │      │   │             │
│  │      │      │      │      │   │             │             ✓ WEIGHT NOW CONTAINS LORA MODIFICATIONS
│  │      │      │      │      │   │             │
│  │      │      │      │      │   │             └─ [Back in load_models_gpu, continue loop]
│  │      │      │      │      │   │
│  │      │      │      │      │   ├─ ✓ AT THIS POINT: All patches have been applied
│  │      │      │      │      │   │
│  │      │      │      │      │   ├─ self.model_patcher.pre_run()
│  │      │      │      │      │   │
│  │      │      │      │      │   └─ output = self.inner_sample(...)
│  │      │      │      │      │      ├─ Actual diffusion loop
│  │      │      │      │      │      └─ Uses patched model weights throughout sampling
│  │      │      │      │      │
│  │      │      │      │      └─ [Returns denoised latent]
│  │      │      │      │
│  │      │      │      └─ [Returns to comfy.samplers.sample]
│  │      │      │
│  │      │      └─ [Returns to comfy.sample.sample]
│  │      │
│  │      └─ [Returns sampled latents with LoRA applied]
│  │
│  └─ samples_out now contains latents sampled with LoRA
│
└─ Success! LoRA has been applied during sampling
```

---

## Key Data Structures

### 1. LoRA Patch Dictionary (`combo_model.patches`)

**Location:** `ModelPatcher.patches: dict[str, list[tuple]]`

**Structure:**
```python
{
    "diffusion_model.input_blocks.0.0.weight": [
        # Patch 1 (first LoRA)
        (
            strength_patch=1.0,        # float
            patch_data=(...),          # LoRA weights tuple
            strength_model=1.0,        # float
            offset=None,               # optional offset
            function=None              # optional custom function
        ),
        # Patch 2 (second LoRA) - accumulated here
        (1.0, (...), 1.0, None, None),
    ],
    "diffusion_model.input_blocks.0.0.bias": [...],
    # ... hundreds of keys ...
}
```

**When populated:** After `load_lora_for_models()` or `add_patches()`

**When used:** In `patch_weight_to_device()` → `comfy.lora.calculate_weight()`

### 2. Backup Dictionary (`combo_model.backup`)

**Location:** `ModelPatcher.backup: dict[str, namedtuple]`

**Structure:**
```python
{
    "diffusion_model.input_blocks.0.0.weight": namedtuple(
        weight=<original_tensor>,      # Original weight before patching
        inplace_update=False           # Whether update was in-place
    ),
    # ... one entry per patched weight ...
}
```

**When populated:** During `patch_weight_to_device()` - ONLY if key in `self.patches`

**When used:** During `unpatch_model()` to restore original weights

**Indicator:** If empty after sampling, patches were NOT applied!

### 3. Model Options (`combo_model.model_options`)

**Location:** `ModelPatcher.model_options: dict`

**Structure:**
```python
{
    "transformer_options": {
        "patches": {
            # Transformer-specific patches (not weight patches)
            "attn1_patch": [...],
            "attn2_patch": [...],
        },
        "patches_replace": {
            # Replacement patches for specific blocks
        },
    },
    "sampler_cfg_function": ...,      # Custom CFG function
    "sampler_post_cfg_function": [...], # Post-CFG callbacks
}
```

**Note:** This is SEPARATE from `self.patches`. This is for runtime modifications.

---

## The LoRA Calculation (`comfy.lora.calculate_weight()`)

**File:** `comfy/lora.py`

**Pseudocode:**
```python
def calculate_weight(patches, weight, key, intermediate_dtype=torch.float32):
    """
    Applies all LoRA patches to a weight tensor.
    
    patches: list of (strength_patch, patch_data, strength_model, offset, function) tuples
    weight: original weight tensor
    key: weight key name (for logging/debugging)
    
    Returns: modified weight tensor
    """
    for patch in patches:
        strength_patch, patch_data, strength_model, offset, function = patch
        
        if function is not None:
            # Custom patch function
            weight = function(weight)
        else:
            # Standard LoRA patch
            # Typically: weight = weight + strength * lora(weight)
            # Where lora() is matrix multiplication with LoRA weights
            weight = apply_standard_lora_patch(
                weight,
                patch_data,
                strength_patch,
                strength_model
            )
    
    return weight
```

**Implementation details:**
- Applies patches **sequentially** (multiple LoRAs accumulate)
- Converts intermediate tensors to `intermediate_dtype` for calculation
- Restores original dtype at end
- Uses `torch.linalg.matmul()` or `torch.mm()` for actual LoRA computation

---

## Critical State Transitions

### Before `prepare_sampling()`:
```python
combo_model.patches      # ✓ Has data: {key: [patches]}
combo_model.backup       # ✗ Empty: {}
combo_model.model        # ✗ Original unpatched weights
```

### After `prepare_sampling()` / `load_models_gpu()`:
```python
combo_model.patches      # ✓ Still has data: {key: [patches]}
combo_model.backup       # ✓ Now has backups: {key: (original_weight, inplace_update)}
combo_model.model        # ✓ Weights are now PATCHED with LoRA
```

### After `unpatch_model()`:
```python
combo_model.patches      # ✓ Still has data (not cleared)
combo_model.backup       # ✗ Cleared: {}
combo_model.model        # ✗ Weights restored to original
```

---

## Verification Points

### Point 1: Check Patches Dictionary
```python
assert len(combo_model.patches) > 0, "No patches loaded!"
# Should show keys like:
# - diffusion_model.input_blocks.0.0.weight
# - diffusion_model.middle_block.0.conv.weight
# - etc.
```

### Point 2: Check Backup Dictionary  
```python
# This check should happen AFTER sampling, not before
assert len(combo_model.backup) > 0, "Patches were not applied!"
# Indicates patch_weight_to_device() was called
```

### Point 3: Verify Weight Modification
```python
key = list(combo_model.backup.keys())[0]
original = combo_model.backup[key].weight
current = comfy.utils.get_attr(combo_model.model, key)
assert not torch.allclose(original, current, atol=1e-5), "Weights not modified!"
```

---

## Troubleshooting by Layer

| Layer | Issue | Check | Fix |
|-------|-------|-------|-----|
| LoRA Loading | No patches loaded | `len(combo_model.patches) > 0` | LoRA keys don't match model |
| Sampling | Patches not applied | `len(combo_model.backup) > 0` after sampling | Use `comfy.sample.sample()` not direct sampler |
| Device | Wrong device | `combo_model.load_device` matches GPU | Call `load_models_gpu()` |
| Memory | OOM during patching | Check available VRAM | Reduce batch size or enable lowvram mode |
| Output | No visual difference | Compare weights using diagnostic code | Check LoRA strength > 0 |

---

## Complete Example: Tracing a Single Weight

```
Input: Model U-Net with layer "diffusion_model.input_blocks.0.0.weight"
       LoRA data with patch for this key
       Sampling call

1. load_lora_for_models()
   └─ combo_model.patches["diffusion_model.input_blocks.0.0.weight"] = [
        (strength=1.0, lora_down_weight, lora_up_weight, offset=None, func=None)
      ]

2. comfy.sample.sample()
   └─ Wraps in CFGGuider

3. CFGGuider.outer_sample()
   └─ Calls prepare_sampling()

4. prepare_sampling()
   └─ Calls load_models_gpu([combo_model])

5. load_models_gpu()
   └─ Calls combo_model.partially_load()

6. partially_load()
   └─ Calls combo_model.load()

7. load()
   └─ Calls patch_weight_to_device("diffusion_model.input_blocks.0.0.weight")

8. patch_weight_to_device()
   ├─ Gets original: weight = model.diffusion_model.input_blocks[0][0].weight
   ├─ Backs up: backup["diffusion_model.input_blocks.0.0.weight"] = (weight.copy(), False)
   ├─ Calls: out_weight = calculate_weight(patches, weight, key)
   │   └─ In calculate_weight:
   │       ├─ For each patch in patches[key]:
   │       │   weight += strength * (lora_down @ lora_up)
   │       └─ Returns modified weight
   └─ Sets: model.diffusion_model.input_blocks[0][0].weight = out_weight

9. Sampling continues using patched weight

10. Result: Generated image reflects LoRA style
```

---

## Why Your Current Code is Correct

```python
# Your code path:
combo_model, _ = comfy.sd.load_lora_for_models(...)  # ← Patches loaded
samples_out = comfy.sample.sample(combo_model, ...)   # ← Triggers patch application

# This is correct because:
# 1. load_lora_for_models() returns ModelPatcher with patches in .patches dict
# 2. comfy.sample.sample() wraps it in CFGGuider
# 3. CFGGuider.outer_sample() calls prepare_sampling()
# 4. prepare_sampling() calls load_models_gpu()
# 5. load_models_gpu() calls model_load()
# 6. model_load() calls load()
# 7. load() calls patch_weight_to_device() for each patched weight
# 8. ✓ Patches are applied
```

