# LoRA Patches in ComfyUI - Executive Summary

## The Bottom Line

When you call `comfy.sd.load_lora_for_models()`, it returns a **ModelPatcher object** with LoRA data stored in its `patches` dictionary. **These patches are automatically applied** when you call `comfy.sample.sample()` because that function internally:

1. Wraps your model in a `CFGGuider`
2. Which calls `prepare_sampling()`
3. Which calls `load_models_gpu()`
4. Which calls `model.load()`
5. Which calls `patch_weight_to_device()` for each patched weight
6. **Which actually modifies the model's weight tensors**

**No special setup is needed.** Your code is correct.

---

## Three Key Facts

### Fact 1: Patches Are Stored, Not Applied
```python
# After this call:
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, strength, 0)

# combo_model.patches now contains:
{
    "weight_key_1": [(strength, lora_weights, ...), ...],
    "weight_key_2": [(strength, lora_weights, ...), ...],
    ...
}

# BUT the model weights are UNCHANGED at this point
# They're only stored in the dictionary
```

### Fact 2: Patches Are Applied During Sampling
```python
# When you call:
samples = comfy.sample.sample(combo_model, noise, ...)

# Internally it triggers:
CFGGuider(combo_model)
  └─ outer_sample()
    └─ prepare_sampling()
      └─ load_models_gpu()
        └─ model.load()
          └─ patch_weight_to_device() ← APPLIES PATCHES HERE

# Now the model weights contain the LoRA modifications
```

### Fact 3: Automatic Cleanup
```python
# After sampling completes, patches can be removed:
combo_model.unpatch_model()

# This restores original weights from backup
# But the patches dictionary remains unchanged
```

---

## What Happens at Each Stage

### Stage 1: Before LoRA Loading
```
Original Model
├─ model.patches = {}  (empty)
├─ model.backup = {}   (empty)
└─ model.weight_key.data = [original values]
```

### Stage 2: After LoRA Loading
```
Model with LoRA Data (Not Applied)
├─ model.patches = {weight_key: [(str, lora, str, ...)]}  ← Data stored
├─ model.backup = {}  (still empty)
└─ model.weight_key.data = [original values]  (unchanged)
```

### Stage 3: After prepare_sampling() in Sampling
```
Model with LoRA Applied
├─ model.patches = {weight_key: [(str, lora, str, ...)]}  (unchanged)
├─ model.backup = {weight_key: (original_tensor, False)}  ← Backup created
└─ model.weight_key.data = [original + lora modification]  (CHANGED!)
```

### Stage 4: After Sampling Completes
```
Model with LoRA Still Applied (waiting to be unpatch)
├─ model.patches = {weight_key: [(str, lora, str, ...)]}  (unchanged)
├─ model.backup = {weight_key: (original_tensor, False)}  (still has backup)
└─ model.weight_key.data = [original + lora modification]  (patched)
```

### Stage 5: After unpatch_model()
```
Original Model (Restored)
├─ model.patches = {weight_key: [(str, lora, str, ...)]}  (patches kept)
├─ model.backup = {}  (cleared after restoring)
└─ model.weight_key.data = [original values]  (restored)
```

---

## Verification Checklist

### ✓ Before Sampling
- [ ] `len(combo_model.patches) > 0` - Patches loaded into dictionary
- [ ] LoRA file successfully loaded with `load_torch_file()`
- [ ] `load_lora_for_models()` didn't raise exception

### ✓ After `comfy.sample.sample()` Completes
- [ ] `len(combo_model.backup) > 0` - **CRITICAL** indicates patches were applied
- [ ] Model still has LoRA weights in memory
- [ ] Can verify by comparing weights to original

### ✓ To Prove LoRA Changed Output
```python
# Get a weight before/after
weight_before = comfy.utils.get_attr(combo_model.model, "some_key").clone()

# Do sampling (patches applied internally)
samples = comfy.sample.sample(combo_model, ...)

# Get same weight after (should be different)
weight_after = comfy.utils.get_attr(combo_model.model, "some_key")

# Should be different
assert not torch.allclose(weight_before, weight_after)  # ✓ LoRA was applied
```

---

## Most Common Mistake

```python
# ❌ WRONG - Skips patch application
samples = comfy.samplers.sample(
    combo_model, noise, positive, negative, cfg,
    device, sampler, sigmas,
    model_options=combo_model.model_options
)

# ✓ CORRECT - Triggers full pipeline with patches
samples = comfy.sample.sample(
    combo_model, noise, steps, cfg,
    sampler_name, scheduler,
    positive, negative, latent_image
)
```

**Key difference:** `comfy.sample.sample()` wraps model in `CFGGuider` which triggers `prepare_sampling()` which applies patches. Direct calls bypass this.

---

## How to Verify in Your Code

Add this after sampling:

```python
# After: samples_out = comfy.sample.sample(...)

# Check 1: Patches were applied
if len(combo_model.backup) > 0:
    print(f"✓ LoRA applied: {len(combo_model.backup)} weights patched")
else:
    print("✗ ERROR: LoRA was not applied!")
    
# Check 2: Verify weight modification
if len(combo_model.backup) > 0:
    key = list(combo_model.backup.keys())[0]
    original = combo_model.backup[key].weight
    current = comfy.utils.get_attr(combo_model.model, key)
    
    if torch.allclose(original, current, atol=1e-5):
        print("✗ ERROR: Weights appear unchanged despite patching")
    else:
        print(f"✓ Weights modified by LoRA: {key}")
```

If `backup` is empty, the patches weren't applied. That means either:
1. No patches in dictionary (LoRA didn't load)
2. Using wrong sample function (not `comfy.sample.sample()`)
3. Exception during loading (check logs)

---

## The Three Patch Types in ComfyUI

### Type 1: Weight Patches (Used by LoRAs)
- **Storage:** `model_patcher.patches` dict
- **Application:** `patch_weight_to_device()`
- **Timing:** During `prepare_sampling()` → `load_models_gpu()`
- **Effect:** Modifies actual weight tensors
- **Persistence:** Backed up in `backup` dict

### Type 2: Transformer Patches (Runtime modifications)
- **Storage:** `model_options["transformer_options"]["patches"]`
- **Application:** `calc_cond_batch()`
- **Timing:** During diffusion loop, every step
- **Effect:** Modifies attention/transformer behavior
- **Persistence:** Not backed up (regenerated each step)

### Type 3: Hook Patches (Dynamic weight patches)
- **Storage:** `model_patcher.hook_patches`
- **Application:** `patch_hooks()`
- **Timing:** When conditions change
- **Effect:** Conditionally modify weights
- **Persistence:** Cached for efficiency

**Your LoRAs use Type 1: Weight Patches**

---

## The Call Stack in One Picture

```
comfy.sample.sample(model_with_lora, ...)
    ↓
CFGGuider(model_with_lora)
    ↓
CFGGuider.outer_sample()
    ↓
comfy.sampler_helpers.prepare_sampling()
    ↓
comfy.model_management.load_models_gpu()
    ↓
model_patcher.load()
    ↓
model_patcher.patch_weight_to_device()  ← LoRA APPLIED HERE
    ↓
comfy.lora.calculate_weight()
    ↓
Model weights now contain LoRA modifications
    ↓
Diffusion sampling uses patched weights
```

---

## Expected Indicators

### ✅ LoRA IS Working:
- `combo_model.backup` has entries after sampling
- Generated images look different than without LoRA
- Debug shows `Patches loaded: N keys` > 0
- Backup shows `Backup created: M keys` > 0

### ❌ LoRA is NOT Working:
- `combo_model.backup` is empty after sampling
- Generated images look identical to no-LoRA version
- Debug shows `Patches loaded: 0 keys`
- Errors in logs about LoRA keys not matching

---

## Your Code Review

Looking at your `sampler_specialized.py` around line 190:

```python
# ✓ CORRECT: Load LoRA
combo_model, _ = comfy.sd.load_lora_for_models(
    combo_model, None, lora_data, lora_strength, 0
)

# ✓ CORRECT: Use proper sampling function
samples_out = comfy.sample.sample(
    combo_model, noise, steps, cfg,
    sampler_name, scheduler,
    positive, negative, latent_samples,
    denoise=1.0, disable_noise=False,
    callback=callback,
    disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
    seed=seed
)
```

**This is exactly right.** The patches should be applied automatically.

If LoRAs aren't showing visual effect, debug using the verification checklist above to determine if:
1. Patches were loaded into dictionary (they should be)
2. Patches were applied during sampling (they should be)
3. Weights were actually modified (they should be)

---

## Files to Review

If you need to understand the implementation:

| File | Purpose | Key Function |
|------|---------|--------------|
| `comfy/sd.py` | LoRA loading | `load_lora_for_models()` |
| `comfy/lora.py` | Patch calculation | `calculate_weight()` |
| `comfy/model_patcher.py` | Patch storage/application | `patch_weight_to_device()` |
| `comfy/samplers.py` | Sampling pipeline | `CFGGuider.outer_sample()` |
| `comfy/sampler_helpers.py` | Preparation | `prepare_sampling()` |
| `comfy/model_management.py` | GPU loading | `load_models_gpu()` |

---

## Summary

**Your implementation is correct.** LoRA patches are:

1. ✓ Loaded into `combo_model.patches` by `load_lora_for_models()`
2. ✓ Automatically applied during `comfy.sample.sample()` 
3. ✓ Visible as backups in `combo_model.backup` after sampling
4. ✓ Used for weight modification during diffusion generation
5. ✓ Automatically managed (no special cleanup needed)

The patches are integrated into ComfyUI's sampling pipeline and require no special setup beyond the two calls you're already making.

