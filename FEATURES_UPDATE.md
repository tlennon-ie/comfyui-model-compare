# New Features - Model Compare Node Update

**Date:** Current Session  
**Features Added:** 3 major improvements  
**Backward Compatible:** Yes

---

## Feature 1: Custom LoRA Labels

### Purpose
Instead of showing the full LoRA filename in grid labels, you can now customize what each LoRA displays as. For example, "Lightning_LoRA_v1.5.safetensors" can display as "Lightning" or "Speed".

### How to Use

1. In the **Model Compare Loaders** node, you'll see a new field for each LoRA:
   - `lora_0` - Select your LoRA file
   - `lora_0_strengths` - Set strength values (e.g., "0.0, 0.5, 1.0")
   - **NEW** `lora_0_customlabel` - Enter custom display name (optional)

2. **Default behavior (empty custom label):**
   - Uses the LoRA filename automatically
   - Example: "Lightning_LoRA_v1.5.safetensors" → Shows as "Lightning_LoRA_v1.5"

3. **Custom label:**
   - Type any text you prefer
   - Example: Enter "Speed" to display "Speed(0.0)", "Speed(0.5)", "Speed(1.0)" in grid

### Example Setup

```
lora_0: Lightning_LoRA_v1.5.safetensors
lora_0_strengths: 1.0
lora_0_customlabel: (leave empty - uses filename)

lora_1: SkinTexture_LoRA_v2.safetensors  
lora_1_strengths: 0.0, 0.5, 1.0
lora_1_customlabel: Skin (custom label)

Grid labels will show:
- "Skin(0.0)"
- "Skin(0.5)"  
- "Skin(1.0)"
```

### Benefits
- Cleaner grid labels
- User-friendly display names instead of technical filenames
- Makes comparison grids easier to read and present

---

## Feature 2: AND/OR Combiner Operators

### Purpose
Control how multiple LoRAs are combined and tested:
- **AND** - Include this LoRA in ALL combinations (always active with varying strength)
- **OR** - Switch between this LoRA and others (test each separately)

This lets you test LoRAs sequentially instead of all in parallel.

### How to Use

1. In **Model Compare Loaders**, below each LoRA field, you'll see:
   - `lora_0_combiner` - Dropdown with "AND" or "OR" (default: "AND")

2. **AND operator (default):**
   - Includes the LoRA in every generated image
   - Useful for base effect LoRAs that should always be active
   - Example: Lightning LoRA at constant strength

3. **OR operator:**
   - Tests this LoRA separately from others
   - Creates new image set for each OR group
   - Useful for testing multiple variants

### Example: Your Setup

```
lora_0: Lightning_LoRA.safetensors
lora_0_strengths: 1.0
lora_0_customlabel: Lightning
lora_0_combiner: AND ← Always active

↓ Then you choose:

lora_1: SkinTexture_A.safetensors
lora_1_strengths: 0.0, 0.5, 1.0
lora_1_customlabel: Skin_A
lora_1_combiner: OR ← Test separately

lora_2: SkinTexture_B.safetensors
lora_2_strengths: 0.0, 0.5, 1.0
lora_2_customlabel: Skin_B
lora_2_combiner: OR ← Test separately

lora_3: SkinTexture_C.safetensors
lora_3_strengths: 0.0, 0.5, 1.0
lora_3_customlabel: Skin_C
```

### Generated Images

With this setup, you'll get:

```
Group 1: Lightning + Skin_A (all strength combinations)
- Lightning(1.0) + Skin_A(0.0)
- Lightning(1.0) + Skin_A(0.5)
- Lightning(1.0) + Skin_A(1.0)

Group 2: Lightning + Skin_B (all strength combinations)
- Lightning(1.0) + Skin_B(0.0)
- Lightning(1.0) + Skin_B(0.5)
- Lightning(1.0) + Skin_B(1.0)

Group 3: Lightning + Skin_C (all strength combinations)
- Lightning(1.0) + Skin_C(0.0)
- Lightning(1.0) + Skin_C(0.5)
- Lightning(1.0) + Skin_C(1.0)
```

**Result:** 9 images (3 groups × 3 strength variations each), not 27 (which would be all combinations)

### Benefits
- **Sequential testing:** Test each LoRA variant systematically
- **Reduced image count:** No combinatorial explosion
- **Clear comparison:** Each skin LoRA tested with same base
- **Flexible:** Mix AND/OR operators as needed

### Advanced Example: Multiple AND Groups

```
lora_0: Lightning_LoRA
lora_0_combiner: AND ← Always with this lightning

lora_1: DetailBoost_LoRA
lora_1_combiner: AND ← And with this detail boost

lora_2: Skin_A
lora_2_combiner: OR ← But test one skin at a time

lora_3: Skin_B
lora_3_combiner: OR

Result: Each test has Lightning + DetailBoost + one of the skins
```

---

## Feature 3: Debug Log Toggle

### Purpose
Control how much information is printed to the console:
- **Debug OFF:** Clean, minimal output (recommended for production)
- **Debug ON:** Verbose logging for troubleshooting

### How to Use

In the **Model Compare Loaders** node, look for:
- `debug_log` - Toggle switch (default: OFF)

### Debug OFF (Clean Output)

```
[ModelCompareLoaders] Will generate 9 images across 1 grid configurations
[SamplerCompareCheckpoint] Generating image 1/9
[SamplerCompareCheckpoint] Generating image 2/9
[SamplerCompareCheckpoint] Generating image 3/9
...
[GridCompare] Grid saved to: /path/to/output
```

**Only shows:**
- Total image count and grid info
- Current image generation progress
- Final output location

### Debug ON (Verbose Output)

```
[ModelCompareLoaders] Loading base model: flux-dev (checkpoint)
[ModelCompareLoaders] Loading base VAE: default
[ModelCompareLoaders] Loading base CLIP: t5xxl
[ModelCompareLoaders] Config created:
  - Model variations: 1
  - VAE variations: 1
  - LoRAs: 2
  - LoRA combinations strategy: LoRA0 AND LoRA1 OR 
  - Total images to generate: 9

[SamplerCompareCheckpoint] Generating image 1/9
  Model: flux-dev.safetensors, VAE: default, LoRAs: ['Lightning', 'Skin_A']
  LoRA Strengths: (1.0, 0.0)
[SamplerCompareCheckpoint] Sampling with seed 0, steps 20...
[SamplerCompareCheckpoint] Loading checkpoint model: flux-dev.safetensors
[SamplerCompareCheckpoint] Model loaded, type: <class 'comfy.model_patcher.ModelPatcher'>
[SamplerCompareCheckpoint] Applying 2 LoRAs
[SamplerCompareCheckpoint]   Loading Lightning with strength 1.0
[SamplerCompareCheckpoint]   LoRA applied successfully (patches: 0 -> 720)
[SamplerCompareCheckpoint]   Loading Skin_A with strength 0.0
[SamplerCompareCheckpoint]   Skipping Skin_A (strength=0)
...
```

**Shows:**
- Model loading details
- LoRA application info
- Patch count tracking
- Memory cleanup operations
- Complete timing information

### When to Use Each Mode

| Situation | Mode | Reason |
|-----------|------|--------|
| Normal operation | OFF | Cleaner console, easier to see important messages |
| Troubleshooting | ON | See all details for debugging |
| LoRA not working | ON | Debug log helps identify where patches load |
| Performance issues | ON | Track memory cleanup operations |
| Automated/batched runs | OFF | Less console spam in logs |

### Benefits
- **Clean workflow:** Production mode doesn't clutter console
- **Easy debugging:** Turn on when you need detailed info
- **Performance:** Less console I/O in clean mode
- **Flexibility:** Toggle per-run as needed

---

## How All Features Work Together

### Example Workflow

**Your goal:** Compare 3 different skin LoRAs with a lightning LoRA, showing clean labels

**Setup:**

```
Model Compare Loaders:
  ├─ lora_0: Lightning_LoRA_v1.5.safetensors
  │  ├─ strengths: 1.0
  │  ├─ customlabel: Lightning
  │  └─ combiner: AND
  │
  ├─ lora_1: DetailedSkin_v2.safetensors
  │  ├─ strengths: 0.0, 0.5, 1.0
  │  ├─ customlabel: Detailed
  │  └─ combiner: OR
  │
  ├─ lora_2: RealisticSkin_v2.safetensors
  │  ├─ strengths: 0.0, 0.5, 1.0
  │  ├─ customlabel: Realistic
  │  └─ combiner: OR
  │
  ├─ lora_3: SoftSkin_v2.safetensors
  │  ├─ strengths: 0.0, 0.5, 1.0
  │  ├─ customlabel: Soft
  │  └─ combiner: OR
  │
  └─ debug_log: OFF (clean output)
```

**Result:**

Console output:
```
[ModelCompareLoaders] Will generate 9 images across 1 grid configurations
[SamplerCompareCheckpoint] Generating image 1/9
[SamplerCompareCheckpoint] Generating image 2/9
...
[GridCompare] Grid saved to: output/model-compare/ComfyUI
```

Grid labels show:
```
Detailed(0.0)    Detailed(0.5)    Detailed(1.0)
Realistic(0.0)   Realistic(0.5)   Realistic(1.0)
Soft(0.0)        Soft(0.5)        Soft(1.0)
```

Grid contains 9 images:
- All with Lightning LoRA at 1.0
- Each row tests one skin LoRA
- Each column tests one strength level

---

## Technical Details

### Custom Labels Implementation
- Stored in config as `lora_display_names`
- Falls back to filename if empty
- Used in `generate_smart_labels()` function
- Applied during grid label generation

### AND/OR Logic
- LoRAs grouped by combiner operators
- AND LoRAs stay together
- OR groups create separate image sets
- Groups are tested sequentially, not as cross-product

### Debug Toggle
- Stored in config: `debug_log` (boolean)
- Checked before each print statement
- Affects all 3 samplers consistently
- Progress output always shown regardless

---

## Backward Compatibility

**Yes, fully backward compatible!**

- Old workflows without custom labels work unchanged
- Default behavior matches previous version
- No breaking changes to config structure
- Existing projects work immediately

---

## Quick Reference

### Custom Labels
- Optional field per LoRA
- Leave empty to use filename
- Affects grid display only

### AND/OR Combiner
- Default: AND (include in all combos)
- Set to OR to test sequentially
- Affects combination generation

### Debug Toggle
- Default: OFF (clean output)
- Turn ON for troubleshooting
- No performance impact

---

## Next Steps

1. **Try Custom Labels:** Set descriptive names for your LoRAs
2. **Test AND/OR:** Experiment with sequential LoRA testing
3. **Use Debug Mode:** When troubleshooting issues
4. **Optimize:** Use OFF mode for production workflows

All three features are designed to work together for a complete, flexible comparison workflow!
