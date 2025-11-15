# LoRA Patch Application - Code Snippets & Examples

## Snippet 1: Verify LoRA is Loaded

```python
import comfy.sd
import folder_paths

def verify_lora_loaded(model, lora_name, strength):
    """Check if LoRA was successfully loaded into model patches"""
    
    lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
    lora_data = comfy.utils.load_torch_file(lora_path)
    
    model_with_lora, _ = comfy.sd.load_lora_for_models(
        model, None, lora_data, strength, 0
    )
    
    # Check patches dictionary
    patch_count = len(model_with_lora.patches)
    print(f"Patches loaded: {patch_count} weight keys")
    
    if patch_count > 0:
        # Show sample keys
        sample_keys = list(model_with_lora.patches.keys())[:3]
        print("Sample patch keys:")
        for key in sample_keys:
            patch_list = model_with_lora.patches[key]
            print(f"  {key}: {len(patch_list)} patch(es)")
    else:
        print("ERROR: No patches loaded! Check LoRA file and model compatibility.")
    
    return model_with_lora

# Usage:
# model_with_lora = verify_lora_loaded(model, "my_lora.safetensors", 1.0)
```

---

## Snippet 2: Verify Patches Are Applied

```python
import torch
import comfy.utils

def verify_patches_applied(model_with_lora):
    """Check if patches were applied during sampling"""
    
    print("\nVerifying patch application:")
    
    # Check 1: Patches in dictionary
    patches_in_dict = len(model_with_lora.patches)
    print(f"  Patches in dictionary: {patches_in_dict} keys")
    
    # Check 2: Backups created (indicates patches were applied)
    backups_created = len(model_with_lora.backup)
    print(f"  Backups created: {backups_created} keys")
    
    if backups_created == 0:
        print("  ✗ ERROR: No backups! Patches were NOT applied during sampling.")
        return False
    
    # Check 3: Verify weight modification
    print(f"\n  Verifying weight modification:")
    
    for key in list(model_with_lora.backup.keys())[:3]:
        original = model_with_lora.backup[key].weight
        current = comfy.utils.get_attr(model_with_lora.model, key)
        
        # Check if weights are different
        is_different = not torch.allclose(original, current, atol=1e-5)
        status = "✓ Modified" if is_different else "✗ Unchanged"
        
        print(f"    {key}: {status}")
        
        if not is_different:
            return False
    
    print("\n  ✓ SUCCESS: LoRA patches were applied correctly")
    return True

# Usage:
# After sampling:
# verify_patches_applied(model_with_lora)
```

---

## Snippet 3: Complete LoRA Application Example

```python
import torch
import comfy.sd
import comfy.sample
import comfy.utils
import folder_paths

def apply_lora_and_sample(model, clip, lora_name, strength, positive, negative, 
                          latent_image, steps=20, cfg=8.0, seed=42):
    """
    Complete example of loading LoRA and sampling with it applied
    """
    
    print(f"\n{'='*60}")
    print(f"Loading LoRA: {lora_name}")
    print(f"{'='*60}")
    
    # Load LoRA file
    lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
    lora_data = comfy.utils.load_torch_file(lora_path)
    print(f"✓ LoRA file loaded: {lora_path}")
    
    # Apply LoRA to model
    model_with_lora, clip_with_lora = comfy.sd.load_lora_for_models(
        model, clip, lora_data, strength, 0
    )
    print(f"✓ LoRA patches added: {len(model_with_lora.patches)} weight keys")
    
    # Prepare noise
    latent_samples = latent_image["samples"].clone()
    latent_samples = comfy.sample.fix_empty_latent_channels(model_with_lora, latent_samples)
    batch_inds = latent_image.get("batch_index", None)
    noise = comfy.sample.prepare_noise(latent_samples, seed, batch_inds)
    
    print(f"\n{'='*60}")
    print(f"Sampling with LoRA")
    print(f"{'='*60}")
    print(f"Steps: {steps}, CFG: {cfg}, Strength: {strength}")
    
    # Sample (patches applied internally here)
    samples = comfy.sample.sample(
        model_with_lora,
        noise,
        steps,
        cfg,
        "euler",  # sampler
        "normal",  # scheduler
        positive,
        negative,
        latent_samples,
        denoise=1.0,
        disable_noise=False,
        callback=None,
        disable_pbar=True,
        seed=seed
    )
    
    # Verify patches were applied
    print(f"\n✓ Sampling complete")
    print(f"✓ Backup weights created: {len(model_with_lora.backup)} keys")
    
    if len(model_with_lora.backup) > 0:
        print(f"✓ LoRA was applied successfully")
    else:
        print(f"✗ WARNING: No backup weights - LoRA may not have been applied")
    
    return samples

# Usage:
# samples = apply_lora_and_sample(
#     model, clip, "my_lora.safetensors", 1.0,
#     positive, negative, latent
# )
```

---

## Snippet 4: Multiple LoRAs (Your Use Case)

```python
def apply_multiple_loras(model, clip, lora_configs, positive, negative, latent_image, seed=42):
    """
    Apply multiple LoRAs to the same model
    
    lora_configs: list of {'name': 'file.safetensors', 'strength': 1.0}
    """
    
    print(f"Applying {len(lora_configs)} LoRAs...")
    
    # Start with base model
    current_model = model
    current_clip = clip
    
    # Apply each LoRA sequentially
    for i, lora_config in enumerate(lora_configs):
        lora_name = lora_config['name']
        lora_strength = lora_config.get('strength', 1.0)
        
        if lora_strength == 0:
            print(f"  [{i+1}] Skipping {lora_name} (strength=0)")
            continue
        
        print(f"  [{i+1}] Loading {lora_name} (strength={lora_strength})")
        
        # Load LoRA
        lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
        lora_data = comfy.utils.load_torch_file(lora_path)
        
        # Apply to current model (accumulates patches)
        current_model, current_clip = comfy.sd.load_lora_for_models(
            current_model, current_clip, lora_data, lora_strength, 0
        )
        
        print(f"      Total patches: {len(current_model.patches)} keys")
    
    print(f"\n✓ All {len(lora_configs)} LoRAs loaded")
    print(f"✓ Total patch keys: {len(current_model.patches)}")
    
    # Now sample (patches applied internally)
    samples = comfy.sample.sample(
        current_model,
        prepare_noise(...),
        20,  # steps
        8.0,  # cfg
        "euler",
        "normal",
        positive,
        negative,
        latent_image["samples"],
        seed=seed
    )
    
    return samples, current_model

# Usage:
# loras = [
#     {'name': 'lora1.safetensors', 'strength': 1.0},
#     {'name': 'lora2.safetensors', 'strength': 0.8},
# ]
# samples, model_with_loras = apply_multiple_loras(
#     model, clip, loras, positive, negative, latent
# )
```

---

## Snippet 5: Debug LoRA Application

```python
class LoRADebugger:
    """Debug utility for LoRA patch application"""
    
    def __init__(self, model):
        self.model = model
        self.before_patches = len(model.patches)
        self.before_backup = len(model.backup)
    
    def check_patches_loaded(self):
        """Check if LoRA was loaded into patches dict"""
        patches = len(self.model.patches)
        print(f"Patches dictionary: {patches} keys")
        
        if patches == 0:
            print("  ✗ ERROR: No patches loaded!")
            return False
        
        print(f"  ✓ Sample keys:")
        for key in list(self.model.patches.keys())[:3]:
            patch_count = len(self.model.patches[key])
            print(f"    - {key}: {patch_count} patch(es)")
        
        return True
    
    def check_patches_applied(self):
        """Check if patches were applied to model weights"""
        backups = len(self.model.backup)
        print(f"Backup weights: {backups} keys")
        
        if backups == 0:
            print("  ✗ ERROR: Patches were NOT applied")
            return False
        
        print(f"  ✓ Patches were applied")
        return True
    
    def check_weight_modification(self):
        """Verify weights were actually modified"""
        if len(self.model.backup) == 0:
            print("Skipping weight check (no backups)")
            return False
        
        print("Weight modification check:")
        all_modified = True
        
        for key in list(self.model.backup.keys())[:3]:
            original = self.model.backup[key].weight
            current = comfy.utils.get_attr(self.model.model, key)
            
            is_modified = not torch.allclose(original, current, atol=1e-5)
            
            if is_modified:
                print(f"  ✓ {key}: Modified")
            else:
                print(f"  ✗ {key}: NOT modified (error!)")
                all_modified = False
        
        return all_modified
    
    def full_check(self):
        """Run all checks"""
        print(f"\n{'='*60}")
        print("LoRA Application Debug Check")
        print(f"{'='*60}\n")
        
        check1 = self.check_patches_loaded()
        print()
        check2 = self.check_patches_applied()
        print()
        check3 = self.check_weight_modification()
        
        print(f"\n{'='*60}")
        if check1 and check2 and check3:
            print("✅ ALL CHECKS PASSED - LoRA is working correctly")
        else:
            print("❌ SOME CHECKS FAILED - LoRA may not be working")
        print(f"{'='*60}\n")
        
        return check1 and check2 and check3

# Usage:
# debugger = LoRADebugger(model_with_lora)
# debugger.full_check()
```

---

## Snippet 6: Restore Original Weights

```python
def restore_original_weights(model_with_lora):
    """Restore model to original (unpatched) state"""
    
    if len(model_with_lora.backup) == 0:
        print("No backups - model is already unpatched")
        return
    
    print(f"Restoring {len(model_with_lora.backup)} original weights...")
    
    # This restores from backup
    model_with_lora.unpatch_model()
    
    print("✓ Original weights restored")
    print(f"  Backups remaining: {len(model_with_lora.backup)}")
    print(f"  Patches still available: {len(model_with_lora.patches)}")

# Usage:
# restore_original_weights(model_with_lora)
```

---

## Snippet 7: Compare Outputs With/Without LoRA

```python
def compare_lora_effect(model, clip, lora_name, strength, positive, negative, 
                       latent_image, seed=42, vae=None):
    """Generate samples with and without LoRA to compare"""
    
    print(f"Generating samples to compare LoRA effect...")
    
    # Sample WITHOUT LoRA
    print("\n1. Sampling WITHOUT LoRA...")
    samples_without = comfy.sample.sample(
        model, prepare_noise(...), 20, 8.0,
        "euler", "normal",
        positive, negative,
        latent_image["samples"],
        seed=seed
    )
    
    # Sample WITH LoRA
    print("\n2. Loading LoRA and sampling...")
    lora_path = folder_paths.get_full_path_or_raise("loras", lora_name)
    lora_data = comfy.utils.load_torch_file(lora_path)
    
    model_with_lora, _ = comfy.sd.load_lora_for_models(
        model.clone(), clip, lora_data, strength, 0
    )
    
    samples_with = comfy.sample.sample(
        model_with_lora, prepare_noise(...), 20, 8.0,
        "euler", "normal",
        positive, negative,
        latent_image["samples"],
        seed=seed
    )
    
    print(f"\n3. Comparison:")
    print(f"  Without LoRA shape: {samples_without.shape}")
    print(f"  With LoRA shape: {samples_with.shape}")
    
    # Check if outputs are different
    diff = torch.abs(samples_with - samples_without).mean()
    print(f"  Mean difference: {diff:.6f}")
    
    if diff > 0.001:
        print(f"  ✓ LoRA made a visible difference")
    else:
        print(f"  ✗ LoRA had minimal effect")
    
    return samples_without, samples_with

# Usage:
# samples_no_lora, samples_with_lora = compare_lora_effect(
#     model, clip, "my_lora.safetensors", 1.0,
#     positive, negative, latent
# )
```

---

## Snippet 8: Model Management Helper

```python
class LoRAModelManager:
    """Manage model cloning and LoRA application"""
    
    def __init__(self, base_model, base_clip):
        self.base_model = base_model
        self.base_clip = base_clip
    
    def get_model_with_loras(self, lora_configs):
        """Get a fresh clone with LoRAs applied"""
        
        # Clone base model
        model = self.base_model.clone()
        clip = self.base_clip.clone()
        
        # Apply each LoRA
        for config in lora_configs:
            if config['strength'] == 0:
                continue
            
            lora_path = folder_paths.get_full_path_or_raise("loras", config['name'])
            lora_data = comfy.utils.load_torch_file(lora_path)
            
            model, clip = comfy.sd.load_lora_for_models(
                model, clip, lora_data, 
                config['strength'], 0
            )
        
        return model, clip
    
    def sample_with_loras(self, lora_configs, positive, negative, latent, seed):
        """Get model and sample with LoRAs applied"""
        
        model, clip = self.get_model_with_loras(lora_configs)
        
        samples = comfy.sample.sample(
            model, prepare_noise(...), 20, 8.0,
            "euler", "normal",
            positive, negative,
            latent["samples"],
            seed=seed
        )
        
        # Verify LoRAs were applied
        if len(model.backup) > 0:
            print(f"✓ {len(lora_configs)} LoRAs applied successfully")
        else:
            print(f"✗ Warning: LoRAs may not have been applied")
        
        return samples, model

# Usage:
# manager = LoRAModelManager(base_model, base_clip)
# 
# loras = [
#     {'name': 'lora1.safetensors', 'strength': 1.0},
#     {'name': 'lora2.safetensors', 'strength': 0.8},
# ]
# 
# samples, model_used = manager.sample_with_loras(
#     loras, positive, negative, latent, 42
# )
```

---

## Quick Reference: Key Functions

```python
# Load LoRA into patches dictionary
model_with_lora, clip_with_lora = comfy.sd.load_lora_for_models(
    model, clip, lora_data, strength_model, strength_clip
)

# Sample (patches applied automatically)
samples = comfy.sample.sample(
    model_with_lora, noise, steps, cfg,
    sampler_name, scheduler,
    positive, negative, latent_image
)

# Restore original weights
model_with_lora.unpatch_model()

# Check if patches were applied
print(f"Patches applied: {len(model_with_lora.backup) > 0}")

# Get all patched weight keys
patched_keys = list(model_with_lora.patches.keys())

# Get original weight
original_weight = model_with_lora.backup[key].weight

# Get current (possibly patched) weight
current_weight = comfy.utils.get_attr(model_with_lora.model, key)
```

---

## Error Handling Template

```python
try:
    # Load LoRA
    lora_data = comfy.utils.load_torch_file(lora_path)
except Exception as e:
    print(f"Failed to load LoRA file: {e}")
    return None

try:
    # Apply LoRA
    model_with_lora, _ = comfy.sd.load_lora_for_models(
        model, None, lora_data, strength, 0
    )
except Exception as e:
    print(f"Failed to apply LoRA: {e}")
    return model  # Return unpatched model

if len(model_with_lora.patches) == 0:
    print(f"Warning: No patches were loaded (LoRA keys may not match model)")

try:
    # Sample
    samples = comfy.sample.sample(...)
except Exception as e:
    print(f"Sampling failed: {e}")
    model_with_lora.unpatch_model()  # Cleanup
    return None

# Verify patches were applied
if len(model_with_lora.backup) == 0:
    print(f"Warning: Patches may not have been applied")

return samples
```

These snippets provide practical implementations of LoRA patch application that you can adapt for your needs.

