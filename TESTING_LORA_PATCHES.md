# Testing LoRA Patches in Model Compare Node

## Overview

You've reported that LoRA patches are being applied (patch count increases from 0 → 720 → 840) but all 4 generated images look identical, suggesting the patches aren't affecting the diffusion output.

This document provides a systematic approach to diagnosing and fixing the issue.

## Summary of Changes Made (This Session)

✅ **COMPLETED:**
1. Removed hardcoded 4-combination limit - now processes all 5+ combinations
2. Fixed smart labels to only show LoRAs that actually vary in strength across combinations
3. Added dynamic grid layout that arranges 1×N for single varying parameter
4. Added detailed patch persistence logging before/after sampling

🔍 **PENDING:** Determine why patches exist but don't affect output

---

## How to Test

### Step 1: Run Your Workflow and Check Console Output

Run your node workflow and look for logs like:

```
[SamplerCompareCheckpoint] Processing combination 1/5
  Model: flux-dev.safetensors, VAE: default, LoRAs: ['LightningA.safetensors', 'SkinA.safetensors']
  LoRA Strengths: [1.0, 0.0]
[SamplerCompareCheckpoint]   Loading LightningA.safetensors with strength 1.0
[SamplerCompareCheckpoint]   LoRA applied successfully (patches: 0 -> 720)
[SamplerCompareCheckpoint] BEFORE sample call: patches count = 720
[SamplerCompareCheckpoint]   Patch keys: ['...']...
[SamplerCompareCheckpoint] Running sampler: euler
[SamplerCompareCheckpoint] AFTER sample call: patches count = 720
```

### Step 2: Verify Patch Counts Change Between Combinations

Look for this pattern across all combinations:

```
Combination 1: patches: 0 -> 720        (Lightning 1.0, Skin 0.0)
Combination 2: patches: 0 -> 720 -> 840 (Lightning 1.0, Skin 1.0)
Combination 3: patches: 0 -> 720 -> 840 (Lightning 1.0, Skin 1.0)
Combination 4: patches: 0 -> 720 -> 840 (Lightning 1.0, Skin 1.0)
Combination 5: patches: 0 -> 720 -> 840 (Lightning 1.0, Skin 1.0)
```

**Expected behavior:** Different combinations should have different final patch counts if using different LoRA strengths.

**If all combinations show the same patch count → PROBLEM: LoRAs aren't loading with the right strength**

---

## Root Cause Analysis Checklist

### Issue #1: Different LoRA Strengths Not Being Applied
**Symptom:** All combinations show `patches: 0 -> 720` regardless of strength value

**Check:**
```python
# Look at logs for this pattern:
[SamplerCompareCheckpoint]   Loading Skin.safetensors with strength 1.0   # Combination 2
[SamplerCompareCheckpoint]   Loading Skin.safetensors with strength 0.5   # Combination 3
[SamplerCompareCheckpoint]   Loading Skin.safetensors with strength 0.0   # Combination 4 (should skip)
```

**If not seeing different strengths being logged:**
- Check `model_compare_loaders.py` - `_compute_combinations()` should create combinations with varying strengths
- Add logging to show what's in `combo['lora_strengths']` at the beginning of each iteration

### Issue #2: Patches Exist But Aren't Used During Sampling
**Symptom:** Patches count is correct (patches: 0 → 720 → 840) but images are identical

**This is the likely cause.** The patches are in `combo_model.patches` but `comfy.sample.sample()` isn't using them.

**Possible causes:**
1. The model object passed to `sample()` loses its patches after `fix_empty_latent_channels()`
2. The model type (FLUX/Qwen) has special requirements we're not meeting
3. The patches dictionary format is incorrect for this model type
4. We need to call a setup function after loading LoRAs

**What to check:**
```
[SamplerCompareCheckpoint] BEFORE sample call: patches count = 840
[SamplerCompareCheckpoint] AFTER sample call: patches count = 840
```

If patches count remains constant before/after → patches ARE present during sampling

### Issue #3: Same Seed Producing Same Output
**Symptom:** Using same seed for all combinations

**Check in logs:**
```
[SamplerCompareCheckpoint] Sampling with seed 12345...
```

Should see same seed for all combinations (this is intentional for comparison). **This is NOT the problem** - patches should still vary output.

**Important:** In standard diffusion, `same seed + different patches = different outputs`. If that's not happening, patches aren't working.

---

## Quick Diagnostic Script

Add this code to `sampler_specialized.py` right after loading LoRAs to verify they're actually applied:

```python
# After: combo_model, _ = comfy.sd.load_lora_for_models(...)

# Verify patches are actually different between iterations
print(f"[SamplerCompareCheckpoint] Combo {i+1} LoRA state:")
print(f"  - LoRA names: {combo['lora_names']}")
print(f"  - LoRA strengths: {combo['lora_strengths']}")
print(f"  - Total patches: {len(combo_model.patches)}")

# Show a sample of patch keys to verify they're there
if combo_model.patches:
    patch_keys = list(combo_model.patches.keys())
    print(f"  - Sample patch keys: {patch_keys[:3]}")
    
    # Verify different LoRAs add different patches
    for key in patch_keys[:3]:
        patch_value = combo_model.patches[key]
        if isinstance(patch_value, tuple) and len(patch_value) > 0:
            print(f"    - {key}: {type(patch_value[0])}")
```

---

## Expected vs Actual

### What SHOULD happen:

```
Combination 1 (Skin strength 0.0):
  [Patches loaded, but Skin not applied]
  → generates image with base Lightning effect
  
Combination 2 (Skin strength 0.5):
  [Patches loaded including Skin at 0.5]
  → generates DIFFERENT image - face shows moderate skin texture
  
Combination 3 (Skin strength 1.0):
  [Patches loaded including Skin at 1.0]
  → generates DIFFERENT image - face shows strong skin texture effect
```

### What's ACTUALLY happening:

```
Combination 1: generates image A
Combination 2: generates image A (identical)
Combination 3: generates image A (identical)
```

---

## Investigation Steps

### 1. Verify Combinations Are Created Correctly
Edit `model_compare_loaders.py`:

```python
# In execute() method, after creating combinations:
print(f"[ModelCompareLoaders] Generated combinations:")
for i, combo in enumerate(config['combinations']):
    print(f"  Combo {i+1}:")
    print(f"    Model: {combo['model']}")
    print(f"    LoRA names: {combo['lora_names']}")
    print(f"    LoRA strengths: {combo['lora_strengths']}")
```

**Expected output:** See different strength values for at least one LoRA across combinations

### 2. Check if Strengths Are Actually Being Read from Config
In sampler loop, add before loading LoRAs:

```python
print(f"[SamplerCompareCheckpoint] Combo {i+1} input strengths: {combo['lora_strengths']}")

# Then after each LoRA load, show what strength was actually used:
for j, (lora_name, lora_strength) in enumerate(zip(combo['lora_names'], combo['lora_strengths'])):
    print(f"  - About to load {lora_name} at strength {lora_strength}")
```

### 3. Verify Model Patches Dictionary
After loading LoRAs, inspect the patches:

```python
print(f"[SamplerCompareCheckpoint] Examining patches dictionary:")
if hasattr(combo_model, 'patches') and combo_model.patches:
    # Get patch keys to see what LoRAs are applied
    keys_by_module = {}
    for key in combo_model.patches.keys():
        module = key.split('.')[0]  # Get first part of key
        if module not in keys_by_module:
            keys_by_module[module] = []
        keys_by_module[module].append(key)
    
    for module, keys in keys_by_module.items():
        print(f"  - Module {module}: {len(keys)} patches")
```

### 4. Check if Different LoRA Strengths Create Different Patch Values

The critical test - do different strengths create numerically different patches?

```python
# After loading first LoRA at strength 1.0
patches_full = {k: v for k, v in combo_model.patches.items()}

# Compare to loading the same LoRA at strength 0.5
# The patch values should be scaled differently
```

---

## Most Likely Solution

Based on the investigation from the agent, LoRA patches **should** work correctly with `comfy.sample.sample()`. The patches are automatically applied during the sampling process through this call chain:

```
sample() → CFGGuider.outer_sample() → prepare_sampling() 
  → load_models_gpu() → model.load() → patch_weight_to_device() ← PATCHES APPLIED HERE
```

**If patches are loaded but not affecting output, check:**

1. **Is the model being reused across iterations?**
   - We aggressively clean up with `del combo_model` between iterations
   - Each iteration should load fresh model + fresh LoRAs
   - Check that cleanup is working

2. **Are we accidentally loading the same model twice for different combos?**
   - Look for model caching issues
   - Each combo should independently load its own model instance

3. **Is the LoRA strength multiplier working correctly?**
   - `load_lora_for_models()` takes `strength` parameter
   - Strength 0.0 = LoRA not applied
   - Strength 0.5 = LoRA applied at half strength
   - Check if strength parameter is actually being used

---

## Next Steps

1. **Run with the new diagnostic logging** - check console output matches patterns above
2. **Verify patch counts differ** - if all combos have same patches, LoRAs aren't loading correctly
3. **Check if patches persist** - if before/after counts match, patches are present during sampling
4. **Verify different strengths in logs** - search output for varying strength values

Once you share the console output, we can identify which of these 3 categories the problem falls into and fix it.

---

## Files with Relevant Logging

- `sampler_specialized.py` - All 3 samplers now have before/after patch count logging
- `model_compare_loaders.py` - Shows combo creation
- `grid_compare.py` - No LoRA logic (just grid assembly)

Check console/terminal for `[SamplerCompare*]` log messages when running your workflow.
