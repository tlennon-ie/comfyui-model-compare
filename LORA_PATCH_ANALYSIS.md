# ComfyUI LoRA Patches During Sampling - Complete Analysis

## Executive Summary

**THE KEY ISSUE IN YOUR CODE:** After calling `comfy.sd.load_lora_for_models()`, the LoRA patches are stored in the model's `ModelPatcher.patches` dictionary, but they are **NOT applied to actual model weights** until `patch_model()` is called during the sampling pipeline. Your custom sampler is calling `comfy.sample.sample()` directly without going through the proper initialization sequence that activates patches.

---

## How LoRA Patches Work in ComfyUI

### 1. **LoRA Loading** (`comfy.sd.load_lora_for_models()`)

```python
def load_lora_for_models(model, clip, lora, strength_model, strength_clip):
    # ... converts lora file to patch dictionary ...
    lora = comfy.lora_convert.convert_lora(lora)
    loaded = comfy.lora.load_lora(lora, key_map)
    
    if model is not None:
        new_modelpatcher = model.clone()  # ← Create new ModelPatcher
        k = new_modelpatcher.add_patches(loaded, strength_model)  # ← Store patches
    # ...
    return (new_modelpatcher, new_clip)
```

**What happens here:**
- Returns a **cloned ModelPatcher** with patches stored in `model_patcher.patches` dict
- Patches are NOT yet applied to model weights
- Model patcher is in "dormant" state, ready for activation

---

### 2. **Patch Activation During Sampling**

The patches are activated through this call sequence:

```
nodes.KSampler.sample()
  └─> nodes.common_ksampler()
      └─> comfy.sample.sample()
          └─> comfy.samplers.KSampler.sample()
              └─> comfy.samplers.sample()
                  └─> CFGGuider.sample()
                      └─> CFGGuider.outer_sample()
                          └─> comfy.sampler_helpers.prepare_sampling()  # ← CRITICAL POINT
                              └─> model.partially_load()
                                  └─> model.load()
                                      └─> patch_weight_to_device()  # ← APPLIES PATCHES
```

---

## Critical Sequence: How Patches Get Applied

### Step 1: `prepare_sampling()` - Load models onto GPU

**File:** `comfy/sampler_helpers.py:125`

```python
def prepare_sampling(model: ModelPatcher, noise_shape, conds, model_options=None):
    # ...calls _prepare_sampling which does:
    
    models, inference_memory = get_additional_models(conds, model.model_dtype())
    memory_required, minimum_memory_required = estimate_memory(model, noise_shape, conds)
    
    # THIS IS THE KEY CALL - loads models onto device
    comfy.model_management.load_models_gpu(
        [model] + models, 
        memory_required=memory_required + inference_memory,
        minimum_memory_required=minimum_memory_required + inference_memory
    )
    return real_model, conds, models
```

### Step 2: `load_models_gpu()` - Processes patch dictionary

**File:** `comfy/model_management.py:618`

```python
def load_models_gpu(models, memory_required=0, force_patch_weights=False, ...):
    # ...
    for loaded_model in models_to_load:
        # This calls the model's patch application sequence
        loaded_model.model_load(lowvram_model_memory, force_patch_weights=force_patch_weights)
        current_loaded_models.insert(0, loaded_model)
```

### Step 3: `LoadedModel.model_load()` - Moves patches to device

**File:** `comfy/model_management.py:498`

```python
def model_load(self, lowvram_model_memory=0, force_patch_weights=False):
    # Move all patch data to the correct device
    self.model.model_patches_to(self.device)
    self.model.model_patches_to(self.model.model_dtype())
    
    # Call the key function
    self.model_use_more_vram(use_more_vram, force_patch_weights=force_patch_weights)
```

### Step 4: `ModelPatcher.partially_load()` / `ModelPatcher.load()` - Actually applies patches

**File:** `comfy/model_patcher.py:656`

This is where the magic happens - patches modify actual model weight tensors:

```python
def load(self, device_to=None, lowvram_model_memory=0, force_patch_weights=False, full_load=False):
    # ... iterates through model modules ...
    
    for x in load_completely:
        n = x[1]  # module name
        m = x[2]  # module
        params = x[3]  # parameter names
        
        # THIS APPLIES PATCHES TO WEIGHTS
        for param in params:
            key = "{}.{}".format(n, param)
            self.patch_weight_to_device(key, device_to=device_to)
```

### Step 5: `patch_weight_to_device()` - Computes patched weights

**File:** `comfy/model_patcher.py:609`

```python
def patch_weight_to_device(self, key, device_to=None, inplace_update=False):
    if key not in self.patches:  # Check if this weight has patches
        return
    
    weight, set_func, convert_func = get_key_weight(self.model, key)
    
    # Make backup of original weight
    if key not in self.backup:
        self.backup[key] = collections.namedtuple(...)
    
    # Convert to float32 for calculation
    temp_weight = comfy.model_management.cast_to_device(weight, device_to, torch.float32, copy=True)
    
    # APPLY THE PATCH: multiply LoRA weights + add to original
    out_weight = comfy.lora.calculate_weight(
        self.patches[key],  # The patch list
        temp_weight,
        key
    )
    
    # Update the model with patched weights
    comfy.utils.set_attr_param(self.model, key, out_weight)
```

---

## Where Patches Are Stored

### Location 1: ModelPatcher.patches (Weight patches)
```python
ModelPatcher.patches: dict[str, list[tuple]]
# Example structure:
{
    "diffusion_model.input_blocks.0.0.weight": [
        (strength_patch, patch_data, strength_model, offset, function),
        (strength_patch, patch_data, strength_model, offset, function),
    ],
    "diffusion_model.middle_block.0.conv.weight": [ ... ],
    # ... many more keys
}
```

### Location 2: ModelPatcher.model_options (Transformer patches)
```python
ModelPatcher.model_options["transformer_options"]["patches"]: dict[str, list]
# For transformer-related patches like attention modifications
# These are used during forward passes, not weight loading
```

---

## How Default Samplers Use Patches vs. Your Custom Sampler

### Default Flow (ComfyUI Nodes)

```python
# nodes.py - KSamplerAdvanced
def sample(self, model, ...):
    return common_ksampler(model, ...)  # ← Receives ALREADY patched model if LoRAs were loaded

# models.py
def common_ksampler(model, ...):
    # comfy.sample.sample() handles everything
    samples = comfy.sample.sample(model, ...)
```

**The model passed to `common_ksampler` is what was returned by `load_lora_for_models()`.**
The sampling function itself triggers patch application via the CFGGuider pipeline.

### Your Custom Sampler

```python
# Your code
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
# combo_model is now a ModelPatcher with patches in self.patches dict

# Then you call:
samples_out = comfy.sample.sample(combo_model, noise, ...)
# ✓ This SHOULD work because sample() calls CFGGuider.outer_sample()
#   which calls prepare_sampling() which calls load_models_gpu()
#   which applies the patches
```

---

## Critical Differences in Patch Application Methods

### Method 1: Standard Weight Patching (What LoRAs Use)
- **Where stored:** `ModelPatcher.patches` dictionary
- **When applied:** During `model.load()` in `patch_weight_to_device()`
- **Application:** Weights are mathematically modified (original saved in backup)
- **Used for:** LoRAs, weight replacements
- **Triggered by:** `load_models_gpu()` → `prepare_sampling()`

### Method 2: Transformer Option Patches (For runtime modifications)
- **Where stored:** `ModelPatcher.model_options["transformer_options"]["patches"]`
- **When applied:** During `calc_cond_batch()` forward pass
- **Application:** Callbacks modify behavior during diffusion
- **Used for:** Attention modifications, custom computation
- **Triggered by:** Automatically during sampling loop

### Method 3: Hook Patches (Advanced dynamic patching)
- **Where stored:** `ModelPatcher.hook_patches`
- **When applied:** `patch_hooks()` called during sampling
- **Application:** Runtime weight modification with caching
- **Used for:** Complex conditional weight modifications
- **Triggered by:** `apply_hooks()` during prepare_model_patcher()

---

## The Missing Piece: Where You Need to Be Careful

### ✓ What Your Code Does Correctly
```python
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
# patches are now in combo_model.patches
```

### ✓ What comfy.sample.sample() Does
```python
def sample(model, noise, ..., ...):
    cfg_guider = CFGGuider(model)  # Wraps the ModelPatcher
    # ...
    cfg_guider.outer_sample()  # This path WILL trigger prepare_sampling()
```

### What Happens Inside outer_sample()
```python
def outer_sample(self, noise, latent_image, sampler, sigmas, ...):
    # This is the key call - loads models and applies patches
    self.inner_model, self.conds, self.loaded_models = \
        comfy.sampler_helpers.prepare_sampling(
            self.model_patcher,  # ← Has patches in self.patches
            noise.shape, 
            self.conds, 
            self.model_options
        )
    # After this, patches HAVE BEEN APPLIED to model weights
```

---

## Verification: How to Check If Patches Are Applied

### Check 1: After load_lora_for_models()
```python
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)

print(f"Patches in dictionary: {len(combo_model.patches)} weight keys")
print(f"Sample patch keys: {list(combo_model.patches.keys())[:3]}")
# Output should show patch keys like:
# ['diffusion_model.input_blocks.0.0.weight', ...]
```

### Check 2: After prepare_sampling()
```python
# During sampling, after patches are applied
print(f"Backup weights: {len(combo_model.backup)} keys backed up")
# Should be > 0 if patches were applied
```

### Check 3: Compare original vs patched weights
```python
# Get a weight from the model
weight = comfy.utils.get_attr(combo_model.model, "some.weight.key")
print(f"Weight has been modified: {weight.data_ptr() != original_weight.data_ptr()}")
```

---

## The Actual LoRA Application Code

**Location:** `comfy/lora.py` - `calculate_weight()` function

```python
def calculate_weight(patches, weight, key, intermediate_dtype=torch.float32):
    """
    Applies all patches (LoRAs) to a weight tensor.
    
    Patches format: list of (strength_patch, patch_data, strength_model, offset, function)
    
    Returns: modified weight tensor
    """
    for patch in patches:
        strength_patch, patch_data, strength_model, offset, function = patch
        
        if function is not None:
            # Custom patch function
            weight = function(weight)
        else:
            # Standard LoRA: weight = weight + strength * lora_weight
            # This is where the actual LoRA modification happens
            weight = apply_lora(weight, patch_data, strength_patch, strength_model)
    
    return weight
```

---

## Summary: What Activates LoRA Patches

| Step | Function | File | Action |
|------|----------|------|--------|
| 1 | `load_lora_for_models()` | `comfy/sd.py` | Stores patches in `ModelPatcher.patches` |
| 2 | `KSampler.sample()` → `common_ksampler()` → `sample()` | `nodes.py`, `comfy/sample.py` | Wraps in CFGGuider |
| 3 | `CFGGuider.outer_sample()` | `comfy/samplers.py` | Calls prepare_sampling |
| 4 | `prepare_sampling()` | `comfy/sampler_helpers.py` | Calls load_models_gpu |
| 5 | `load_models_gpu()` | `comfy/model_management.py` | Calls model.model_load() |
| 6 | `model.load()` | `comfy/model_patcher.py` | Calls patch_weight_to_device() |
| 7 | `patch_weight_to_device()` | `comfy/model_patcher.py` | **Actually modifies weights** |

---

## Potential Issues in Your Code

### Issue 1: Multiple LoRA Loading in Loop
You're correctly loading LoRAs with increasing patch counts:
```python
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
```

Each call adds to the patches dictionary, so multiple LoRAs should accumulate correctly.

### Issue 2: Model Device/Memory
The patches need to be moved to the correct device during `patch_weight_to_device()`. This should happen automatically in `prepare_sampling()`.

### Issue 3: Model Cloning
When you clone the model for comparison, ensure the patcher is properly cloned:
```python
combo_model = loaded_model.clone()  # Creates new ModelPatcher with copied patches
```

---

## Expected Behavior vs. Debug Checklist

### ✓ Should Work:
- Loading LoRA and calling `comfy.sample.sample()` directly
- Multiple LoRAs applied to same model
- Patched weights backed up and restored

### ⚠️ Watch Out For:
- Device mismatches (patches on CPU, model on GPU)
- Memory allocation for backup weights
- Patch strength of 0 (should skip the patch)
- LoRA keys not matching model keys (warnings logged)

### 🔍 Debug: Add These Checks
```python
# After loading LoRA
print(f"Patches loaded: {len(combo_model.patches)} keys")

# Inside sample() before return
print(f"Backup created: {len(combo_model.backup)} keys")
print(f"Current device: {combo_model.model.device}")
```

---

## Key Takeaway

**Your LoRAs are NOT broken. They're just not being activated in the way you might expect.**

The patches you add with `load_lora_for_models()` are automatically activated when you call `comfy.sample.sample()`, because that function internally:
1. Wraps your model in a `CFGGuider`
2. Calls `outer_sample()` 
3. Which calls `prepare_sampling()`
4. Which calls `load_models_gpu()` 
5. Which finally applies the patches via `patch_weight_to_device()`

**No special setup needed beyond calling `comfy.sample.sample()` with the patched model!**

