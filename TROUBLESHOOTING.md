# Troubleshooting Guide

## Common Issues & Solutions

### 1. "No Images Generated" / Node Fails Silently

**Symptom**: You queue the workflow, it runs, but you get no output.

**Causes & Fixes**:

1. **Missing Model Files**
   ```
   ❌ Error: Model not found
   ✅ Fix: Check your ComfyUI/models/ folder
           Make sure model files exist where you specified
   ```

2. **Incompatible Model Type**
   ```
   If using config_type: QWEN but model is SDXL
   ❌ Won't work - sampling settings mismatch
   ✅ Use config_type: SDXL instead
   ```

3. **Corrupted Configuration**
   ```
   Check Python console for error messages
   Look for: "ConfigError", "ImportError", "KeyError"
   ✅ Note the error and search the README for solutions
   ```

**Debug Steps**:
1. Open ComfyUI console (show Python output)
2. Queue the workflow again
3. Look for error messages mentioning:
   - File paths (model not found)
   - Config keys (typo in settings)
   - Model types (mismatch errors)
4. Fix and try again

---

### 2. Very Slow Generation (5+ minutes for 3 images)

**Symptom**: Workflow takes forever. Just generating 3 still images.

**Causes & Fixes**:

1. **Video Model Slowness** ✅ Expected
   ```
   WAN 2.2 video: 15 minutes is NORMAL
   Hunyuan video: 20+ minutes is NORMAL
   
   That's not slow, that's video generation!
   ```

2. **High Step Count** ⚠️ Check your settings
   ```
   If steps: 50, this is normal:
   3 images × 50 steps = 150 GPU operations
   ✅ Reduce steps to 20-30 for faster iteration
   ```

3. **GPU Poor Performance**
   ```
   If estimated 5 min but it's taking 20 min:
   - Other apps stealing GPU? (Close them)
   - GPU thermal throttling? (Room too hot)
   - Using CPU fallback? (GPU not detected, use CPU-specific builds)
   ✅ Close other apps, restart GPU, or upgrade hardware
   ```

4. **Insufficient VRAM**
   ```
   If you see out-of-memory errors:
   - Model can't fit in your VRAM
   - Falls back to slow CPU processing
   ✅ Use smaller models or lower resolution
   ```

**Debug Steps**:
1. Reduce to single model and single image
2. Check GPU usage (GPU-Z, watch -gpu nvidia-smi)
3. Monitor temperature (should be < 80°C)
4. If GPU idle, problem is elsewhere (config, model mismatch)

---

### 3. "Out of Memory" / "Runtime Error: CUDA out of memory"

**Symptom**: VRAM usage exceeds your GPU capacity.

**Causes**:

- Too many combinations (8+ large models)
- Video models with high frame counts
- High resolution (1024x1024 or more)
- Multiple models loaded simultaneously

**Quick Fixes** (in priority order):

1. **Reduce combinations**
   ```
   ❌ Don't do: 4 models × 3 steps × 2 CFG = 24 images
   ✅ Try: 2 models × 1 step × 1 CFG = 2 images first
   ```

2. **Lower resolution**
   ```
   ❌ 1024x1024 = slow, memory-hungry
   ✅ Try 512x512 = faster to test
   ✅ Try 384x384 = fastest iteration
   ```

3. **Reduce step count**
   ```
   ❌ steps: 40 uses 2x memory vs steps: 20
   ✅ Start with steps: 20
   ✅ Increase to 30 or 40 once you like the output
   ```

4. **Disable lazy loading? (Advanced)**
   ```
   Check if lazy loading is enabled in config
   (Usually it is - this is already optimized)
   ```

5. **Switch to smaller model**
   ```
   ❌ SDXL model (2.5GB)
   ✅ SD 1.5 model (500MB)
   ✅ piFlow model (1GB, faster than FLUX)
   ```

**For Video Models Specifically**:
```
❌ num_frames: 64 at 1024x1024
✅ num_frames: 16 at 512x512 (start here)
```

---

### 4. "Grid Not Showing" / Empty Grid

**Symptom**: Images generated but the grid display is blank.

**Causes**:

1. **Incompatible image dimensions**
   - One image is very different size from others
   - Grid renderer fails silently

2. **Too many images**
   - Grid becomes unmanageably large
   - Browser struggles to render

**Fixes**:

1. **Use consistent dimensions**
   ```
   In all config chains, set same width/height:
   width: 512
   height: 512
   
   ✅ Avoid: one chain with 512x512, another with 768x1024
   ```

2. **Reduce image count**
   ```
   ❌ 16 combinations = complex grid
   ✅ Start with 2-4 images
   ```

3. **Clear browser cache**
   ```
   ✅ Hard refresh: Ctrl+Shift+R (Chrome/Firefox)
   ✅ Clear cookies for ComfyUI domain
   ✅ Restart browser
   ```

---

### 5. "Seed Control Not Working"

**Symptom**: Set seed control to "increment" but seed doesn't change.

**Root Cause**: Seed control applies AFTER the run, not during.

**Explanation**:
```
Run 1: Use seed=42 for ALL combinations
After run 1 completes: seed becomes 43

Run 2: Use seed=43 for ALL combinations
After run 2 completes: seed becomes 44
```

**This is Expected Behavior**. But if seed isn't changing between runs:

**Fixes**:

1. **Check seed widget type**
   ```
   ✅ Seed must be INT widget
   ❌ If it shows as STRING, widget is misconfigured
   ```

2. **Verify seed_control is set**
   ```
   ✅ Try: seed_control: "randomize" (easiest to see)
   ✅ Queue once, seed becomes random
   ✅ Queue again, seed changes again
   ```

3. **Run twice to see the change**
   ```
   Step 1: Queue workflow once
   Step 2: Check the seed value AFTER generation
   Step 3: Queue again
   Step 4: Compare seed value
   They should be different!
   ```

---

### 6. "QWEN Node Not Working" / "QWEN Missing Parameters"

**Symptom**: QWEN config selected but sampling fails.

**Causes**:

1. **QWEN model not loaded**
   ```
   QWEN requires specific tokenizer
   ❌ Using wrong model file
   ✅ Use official QWEN model from HuggingFace
   ```

2. **Missing CLIP configuration**
   ```
   QWEN needs special CLIP encoding
   ❌ Using default CLIP
   ✅ Use CLIP Config node with QWEN type
   ```

3. **Reference images (QWEN_EDIT)**
   ```
   For QWEN_EDIT, reference image is REQUIRED
   ❌ Don't have reference image = crash
   ✅ Provide image input
   ```

**Fixes**:

1. Ensure QWEN model is installed
2. Use CLIP Config node for QWEN
3. For QWEN_EDIT, provide reference image

---

### 7. "piFlow Is Slow" / "piFlow Patches Accumulating"

**Symptom**: piFlow generation takes same time as FLUX, or gets slower with each image.

**Causes**:

- Model not being cloned before patching
- LoRA patches accumulating on model
- Lazy loading not resetting model properly

**Fixes**:

✅ This is automatically fixed in v1.1+

If using older version:
1. Upgrade comfyui-model-compare
2. Or manually clear cache between runs

---

### 8. "Image Quality Issues" / "Distorted Output"

**Symptom**: Generated images have artifacts, look corrupted, or mismatched to prompt.

**Common Causes**:

1. **CFG too high**
   ```
   ❌ CFG: 15.0 = Overconstrained, may distort
   ✅ Try: CFG: 7.0 (default)
   ```

2. **Steps too low**
   ```
   ❌ steps: 5 = Unfinished generation
   ✅ Try: steps: 20+
   ```

3. **Weird prompt**
   ```
   ❌ "a ksbdh asdfnad woman" = random output
   ✅ Use clear, descriptive prompts
   ```

4. **Model-specific issue**
   ```
   Some models prefer specific CFG/steps ranges
   Try the model's recommended settings
   ```

**Fixes**:

1. Increase steps to 25-40
2. Reduce CFG to 6-8 range
3. Simplify/clarify prompt
4. Try another model

---

### 9. "LoRA Not Applied"

**Symptom**: Generated images look the same with/without LoRA.

**Causes**:

1. **LoRA strength 0 or very low**
   ```
   Check: "strength": 0.0
   ✅ Set to: 0.5 - 1.5
   ```

2. **LoRA not compatible with model**
   ```
   SD 1.5 LoRA on FLUX model = won't work
   ✅ Make sure LoRA target matches model
   ```

3. **LoRA file corrupted**
   ```
   ✅ Try different LoRA or re-download
   ```

**Fixes**:

1. Check LoRA strength (should be > 0)
2. Verify LoRA is designed for your model
3. Try different LoRA to test
4. Check LoRA Compare node configuration

---

### 10. "Variations Not Generated"

**Symptom**: Set `steps: 15, 20, 30` but only got 1 image (not 3).

**Causes**:

- Multi-value variation feature not enabled or not recognized
- Comma format invalid (e.g., "15, 20,30" with typo)
- Parsing failed silently

**Fixes**:

1. **Check comma format exactly**: `"15, 20, 30"`
   - ✅ Spacing optional but consistent
   - ❌ `"15,20,30"` (no spaces) might fail
   - ❌ `"15, 20,30"` (inconsistent spacing) might fail

2. **Verify VARIATION_SUPPORT is enabled**
   ```
   Check Python console:
   ✅ "[SamplingConfigChain] Multi-value support enabled"
   ❌ If you see "disabled", update comfyui-model-compare
   ```

3. **Start simple**
   ```
   ❌ Don't combine: steps+cfg+sampler all comma-separated
   ✅ Try: steps: "15, 20" only (2 values)
   ✅ Once working, add cfg: "7.0, 8.0"
   ```

---

## "My Issue Isn't Listed"

**Debug Steps**:

1. **Check Python console** for exact error message
2. **Search README** for error keyword
3. **Check GitHub Issues** for similar errors
4. **Create minimal reproduction**:
   - Single model
   - Single image
   - Remove LoRAs
   - Use default settings
5. **File GitHub issue** with:
   - Error message (from console)
   - Reproduction steps
   - Your GPU model
   - ComfyUI version

---

## Performance Baseline (What's Normal?)

For reference, here's what you should expect:

| Config | Time | Status |
|--------|------|--------|
| 1 image, 20 steps, 512x512 (SD 1.5) | 3-5 sec | ✅ Normal |
| 3 images, 20 steps, 512x512 (SDXL) | 15-20 sec | ✅ Normal |
| 8 images, 30 steps, 1024x1024 (FLUX) | 2-3 min | ✅ Normal |
| 1 video, 16 frames, 512x512 (WAN2.1) | 10 min | ✅ Normal |
| 1 video, 32 frames, 1024x768 (WAN2.2) | 20-25 min | ✅ Normal |

**If your times are 2-3x longer**: Something is slowing things down (see #2)

---

## Getting Help

📖 Documentation:
- README.md - Feature overview
- Examples/ - Quickstart guides
- PRODUCT_ANALYSIS.md - Feature matrix

🐛 Issues:
- GitHub Issues: https://github.com/tlennon-ie/comfyui-model-compare/issues

🆘 Community:
- ComfyUI Discord: #custom-nodes channel
