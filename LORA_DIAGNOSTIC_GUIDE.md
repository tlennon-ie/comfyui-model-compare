# LoRA Patch Application - Diagnostic & Fix Guide

## Quick Diagnosis: Is Your LoRA Actually Being Applied?

Run this code to check:

```python
# After loading model and LoRA
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)

# Check 1: Are patches in the dictionary?
print("=" * 60)
print("CHECK 1: Patches Dictionary")
print("=" * 60)
print(f"Total patches: {len(combo_model.patches)}")
print(f"Sample keys: {list(combo_model.patches.keys())[:5]}")

# Check 2: Are patches being applied during sampling?
# Add this RIGHT AFTER calling comfy.sample.sample() returns
print("\n" + "=" * 60)
print("CHECK 2: Backup Weights (indicate patches were applied)")
print("=" * 60)
print(f"Backup keys created: {len(combo_model.backup)}")
# If this is 0, patches were NOT applied during sampling
# If > 0, patches WERE applied and original weights backed up

# Check 3: Check device placement
print("\n" + "=" * 60)
print("CHECK 3: Device Placement")
print("=" * 60)
print(f"Model device: {combo_model.model.device}")
print(f"Load device: {combo_model.load_device}")

# Check 4: Check patches themselves
if len(combo_model.patches) > 0:
    first_key = list(combo_model.patches.keys())[0]
    first_patch_list = combo_model.patches[first_key]
    print("\n" + "=" * 60)
    print("CHECK 4: Sample Patch Data")
    print("=" * 60)
    print(f"First patch key: {first_key}")
    print(f"Number of patches for this key: {len(first_patch_list)}")
    if len(first_patch_list) > 0:
        patch = first_patch_list[0]
        print(f"Patch tuple length: {len(patch)}")  # Should be 5
        print(f"Strength patch: {patch[0]}")  # strength_patch
        print(f"Strength model: {patch[2]}")  # strength_model
```

---

## Common Issues & Solutions

### Issue 1: Backup is Empty After Sampling

**Symptom:** `len(combo_model.backup) == 0` after `comfy.sample.sample()` returns

**Root Cause:** The sampling function didn't call `prepare_sampling()` properly, or patches weren't in the dictionary

**Solution:**
```python
# WRONG - doesn't trigger patch application:
samples_out = comfy.samplers.sample(
    combo_model, noise, positive, negative, cfg,
    device, sampler, sigmas, 
    model_options=combo_model.model_options
)

# RIGHT - triggers full pipeline with patch application:
samples_out = comfy.sample.sample(
    combo_model, noise, steps, cfg, 
    sampler_name, scheduler, 
    positive, negative, 
    latent_image,
    denoise=1.0,
    disable_noise=False,
    callback=callback,
    disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
    seed=seed
)
```

**Key difference:** `comfy.sample.sample()` wraps the model in `CFGGuider`, which triggers `prepare_sampling()`. Direct calls to `comfy.samplers.sample()` bypass this.

---

### Issue 2: LoRA Not Affecting Output

**Symptom:** LoRA loaded successfully, but output looks identical with/without LoRA

**Possible Causes:**

#### A. LoRA never actually applied (backup empty)
```python
# See Issue 1 above - use comfy.sample.sample() not direct sampler call
```

#### B. LoRA strength is 0
```python
# Make sure strength is not 0
combo_model, _ = comfy.sd.load_lora_for_models(
    combo_model, None, lora_data, 
    lora_strength,  # ← Must be > 0, typically 0.5 to 1.5
    0  # clip strength
)
```

#### C. LoRA keys don't match model keys
```python
# Check if LoRA keys are being loaded
if len(combo_model.patches) == 0:
    print("ERROR: No patches loaded! LoRA keys don't match model.")
    # Verify LoRA is for the correct model architecture
```

#### D. Weights were patched but immediately unpatched
```python
# If you call unpatch_model() after sampling starts:
combo_model.unpatch_model()  # ← Don't do this!
# This restores original weights, removing LoRA effects
```

---

### Issue 3: Device Mismatch

**Symptom:** CUDA out of memory or weights not updating

**Root Cause:** Patches are on wrong device during `patch_weight_to_device()`

**Solution:**
The device handling is automatic in `comfy.sample.sample()`. But if you're doing something custom:

```python
# Make sure model_options has device info
combo_model.load_device = torch.device("cuda:0")  # or your target device
combo_model.offload_device = torch.device("cpu")

# Let the system handle device movement
comfy.model_management.load_models_gpu([combo_model], ...)
```

---

### Issue 4: Multiple LoRAs Not Stacking

**Symptom:** Last LoRA overwrites previous ones instead of combining

**Root Cause:** You're replacing the model instead of continuously adding patches

**Current Code (CORRECT):**
```python
for lora_name, lora_strength in zip(combo['lora_names'], combo['lora_strengths']):
    # ...
    combo_model, _ = comfy.sd.load_lora_for_models(
        combo_model,  # ← This is returned from previous iteration
        None, 
        lora_data, 
        lora_strength, 
        0
    )
```

✓ This is correct because:
- First iteration: loads LoRA into fresh model, returns ModelPatcher with patches
- Second iteration: loads LoRA into that ModelPatcher, adding more patches to same dict
- Patches accumulate in `combo_model.patches` dictionary

**Verify multiple LoRAs are loaded:**
```python
print(f"Total patches keys: {len(combo_model.patches)}")
# Should be much larger than single LoRA would produce

# Check patch count per key
for key in list(combo_model.patches.keys())[:3]:
    print(f"{key}: {len(combo_model.patches[key])} patches")
    # Should show 1, 2, 3+ depending on LoRA count
```

---

## Advanced: Manually Verify Patch Application

### Approach 1: Compare Weight Values

```python
# Before sampling
original_weight_sample = comfy.utils.get_attr(combo_model.model, "diffusion_model.input_blocks.0.0.weight").clone()

# Run sampling
samples_out = comfy.sample.sample(...)

# After sampling (while model still patched)
patched_weight_sample = comfy.utils.get_attr(combo_model.model, "diffusion_model.input_blocks.0.0.weight")

# Should be different if LoRA was applied
if not torch.allclose(original_weight_sample, patched_weight_sample, atol=1e-5):
    print("✓ LoRA was applied - weights were modified")
else:
    print("✗ LoRA was NOT applied - weights are identical")
```

### Approach 2: Check Backup Dictionary

```python
# This proves patches were applied
if len(combo_model.backup) > 0:
    print(f"✓ {len(combo_model.backup)} weights were patched and backed up")
    
    # Get original (backed up) weight
    sample_key = list(combo_model.backup.keys())[0]
    backed_up_weight = combo_model.backup[sample_key].weight
    
    # Get current weight
    current_weight = comfy.utils.get_attr(combo_model.model, sample_key)
    
    if not torch.allclose(backed_up_weight, current_weight, atol=1e-5):
        print(f"✓ Weight '{sample_key}' was successfully modified")
    else:
        print(f"✗ Weight '{sample_key}' was NOT modified despite being backed up")
else:
    print("✗ No backups created - patches were never applied")
```

### Approach 3: Instrument the Code

Add logging to `patch_weight_to_device()`:

```python
# In your sampling code, before calling sample():

original_patch_weight_to_device = combo_model.patch_weight_to_device
patched_keys = []

def logged_patch_weight_to_device(key, device_to=None, inplace_update=False):
    patched_keys.append(key)
    print(f"  Patching weight: {key}")
    return original_patch_weight_to_device(key, device_to, inplace_update)

combo_model.patch_weight_to_device = logged_patch_weight_to_device

# Now run sampling
samples_out = comfy.sample.sample(...)

print(f"\n✓ Applied patches to {len(patched_keys)} weight keys")
for key in patched_keys[:5]:
    print(f"  - {key}")
```

---

## Complete Test: Verify LoRA is Working

```python
import torch
import comfy.sd
import comfy.sample
import folder_paths

def test_lora_application():
    """Complete test of LoRA loading and application"""
    
    # Setup
    model = load_checkpoint_model(...)  # Your model loading code
    positive = encode_positive(...)
    negative = encode_negative(...)
    latent = prepare_latent(...)
    
    # Load LoRA
    print("Loading LoRA...")
    lora_path = folder_paths.get_full_path_or_raise("loras", "your_lora_name.safetensors")
    lora_data = comfy.utils.load_torch_file(lora_path)
    
    model_with_lora, _ = comfy.sd.load_lora_for_models(
        model, None, lora_data, 1.0, 0
    )
    
    # Verify patches loaded
    print(f"✓ Patches dictionary has {len(model_with_lora.patches)} keys")
    assert len(model_with_lora.patches) > 0, "No patches loaded!"
    
    # Clear backup (fresh state)
    model_with_lora.backup.clear()
    
    # Sample
    print("Sampling...")
    samples = comfy.sample.sample(
        model_with_lora, 
        noise, 
        steps=20, 
        cfg=8.0,
        sampler_name="euler",
        scheduler="normal",
        positive=positive,
        negative=negative,
        latent_image=latent,
        denoise=1.0,
        disable_noise=False,
        seed=42
    )
    
    # Verify patches were applied
    print(f"✓ Backup created {len(model_with_lora.backup)} keys")
    assert len(model_with_lora.backup) > 0, "Patches were not applied!"
    
    # Verify weights were changed
    sample_key = list(model_with_lora.backup.keys())[0]
    original = model_with_lora.backup[sample_key].weight
    current = comfy.utils.get_attr(model_with_lora.model, sample_key)
    
    weight_changed = not torch.allclose(original, current, atol=1e-5)
    print(f"✓ Sample weight changed: {weight_changed}")
    assert weight_changed, "Weights were not actually modified!"
    
    print("\n✅ LoRA application test PASSED")
    
    return samples

# Run test
try:
    result = test_lora_application()
    print("Success! LoRA is working correctly.")
except AssertionError as e:
    print(f"❌ Test failed: {e}")
    print("\nThis means LoRA is not being applied. Check Issue #1 and #2 above.")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
```

---

## The CFGGuider Pipeline: Why It Matters

Understanding this flow is crucial:

```python
# CRITICAL FLOW DIAGRAM

comfy.sample.sample(model_patcher, ...)
    ↓
CFGGuider.__init__(model_patcher)
    ↓
CFGGuider.sample(...)
    ↓
CFGGuider.outer_sample()
    ├─ CALLS: prepare_sampling(model_patcher, ...)
    │   └─ CALLS: load_models_gpu([model_patcher], ...)
    │       └─ CALLS: model_patcher.partially_load(...)
    │           └─ CALLS: model_patcher.load(...)
    │               └─ CALLS: model_patcher.patch_weight_to_device(key)
    │                   └─ APPLIES PATCHES ← HERE'S WHERE THEY HAPPEN!
    │
    ├─ CALLS: model_patcher.pre_run()
    │
    └─ CALLS: inner_sample() [the actual diffusion loop]
        └─ Uses patched model weights for generation
```

**Key point:** If you skip `comfy.sample.sample()` and call samplers directly, you skip the `CFGGuider` wrapper, which skips `prepare_sampling()`, which skips patch application!

---

## What to Check in Your Sampler Code

Looking at your `sampler_specialized.py`:

```python
# Line 190
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)

# Line 206-214 - This is correct! You're calling comfy.sample.sample()
samples_out = comfy.sample.sample(
    combo_model,
    noise,
    steps,
    cfg,
    sampler_name,
    scheduler,
    positive,
    negative,
    latent_samples,
    denoise=1.0,
    disable_noise=False,
    callback=callback,
    disable_pbar=not comfy.utils.PROGRESS_BAR_ENABLED,
    seed=seed
)
# ✓ This should trigger patch application correctly
```

**Your code looks correct!** If LoRAs aren't working, debug using the diagnostic code above.

---

## Performance Note: Patch Caching

ComfyUI caches patches to avoid recalculating them:

```python
# In model_patcher.py
self.cached_hook_patches: dict[comfy.hooks.HookGroup, dict[str, torch.Tensor]] = {}

# If you load the same model twice with same patches:
# First load: calculates patches, saves to cache
# Second load: reuses cached weights (much faster)
```

If you're doing comparisons with multiple models and seeing cache issues:

```python
# Clear cache between comparisons
combo_model.cached_hook_patches.clear()
combo_model.hook_patches_backup = None
combo_model.hook_backup.clear()
```

---

## Expected Output Indicators

### ✅ LoRA IS Being Applied:
- `len(combo_model.backup) > 0` after sampling
- `len(combo_model.patches) > 0` before sampling
- Weights are different between original and backup
- Visual difference in generated images

### ❌ LoRA is NOT Being Applied:
- `len(combo_model.backup) == 0` after sampling
- `len(combo_model.patches) == 0` before sampling  
- No weight differences in model
- Generated images look identical with/without LoRA

---

## Summary

Your code's LoRA loading is correct. The patches ARE being applied during `comfy.sample.sample()` because that function internally calls the CFGGuider pipeline which applies patches.

**Use the diagnostic code above to determine:**
1. Are patches in the dictionary? (should be yes)
2. Did sampling create backups? (should be yes)
3. Did weights actually change? (should be yes)

If any of these are "no," focus on the corresponding issue section above.

