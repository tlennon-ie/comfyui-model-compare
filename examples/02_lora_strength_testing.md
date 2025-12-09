# Example 2: LoRA Strength Testing

**Difficulty:** ⭐⭐ Intermediate  
**Use Case:** Find optimal LoRA strength (0.0 → 1.5)  
**Expected Output:** Grid with strength progression left→right

## Goal

Test a single LoRA at multiple strength values to find the optimal setting for your use case.

## Workflow Structure

```
LoRA Compare → Model Compare Loaders → Sampler Compare Advanced → Grid Compare
```

## Step-by-Step Setup

### 1. Add LoRA Compare Node

**Location:** Right-click → Model Compare → Loaders → LoRA Compare

**Settings:**
- `num_loras`: `1` (testing single LoRA)
- `pair_mode`: `SINGLE` (use `HIGH_LOW_PAIR` only for WAN 2.2)
- `lora_0`: Select your LoRA file
- `lora_0_strengths`: `0.0, 0.5, 0.75, 1.0, 1.25, 1.5`
  - **Important:** Comma-separated values create variations
  - Adjust range based on your needs (e.g., `0.3, 0.5, 0.7` for subtle effects)
- `lora_0_label`: `MyLoRA` (optional custom label)
- `lora_0_ignore_in_grid`: `False`
- `lora_0_combinator`: Leave empty (not needed for single LoRA)

**Output:** `lora_config` (LORA_COMPARE_CONFIG)

---

### 2. Add Model Compare Loaders Node

**Location:** Right-click → Model Compare → Loaders → Model Compare Loaders

**Settings:**
- `preset`: Select your model architecture (e.g., `FLUX`)
- `num_diffusion_models`: `1` (single model)
- `diffusion_model`: Select your model
- Leave `prompt_config` disconnected for now

**Connections:**
- Connect `lora_config` output from LoRA Compare → `lora_variation_0` input on Loaders

**Output:** `config` (MODEL_COMPARE_CONFIG with LoRA variations)

---

### 3. Add Sampler Compare Advanced Node

**Location:** Right-click → Model Compare → Sampling → Sampler Compare Advanced

**Settings:**
- `seed`: `12345`
- `seed_mode`: `fixed` (same seed for all strengths - shows LoRA effect clearly)
- `steps`: `20`
- `cfg`: `3.5` (FLUX) or `7.0` (SDXL)
- `sampler_name`: `euler`
- `scheduler`: `simple`

**Connections:**
- Connect `config` output from Loaders → `config` input on Sampler

**Outputs:** `images`, `config`, `labels`

**Note:** Sampler will generate 6 images (one per strength value)

---

### 4. Add Grid Compare Node

**Location:** Right-click → Model Compare → Grid → Grid Compare

**Settings:**
- `output_folder`: `lora_tests`
- `output_filename`: `mylora_strength_test`
- `cell_size`: `512`
- `save_individual_images`: `True` (recommended - save each strength separately)

**Connections:**
- Connect `images` output from Sampler → `images` input on Grid
- Connect `config` output from Sampler → `config` input on Grid

---

## Expected Result

**Grid Layout:**
- **Columns:** lora_strength (0.0, 0.5, 0.75, 1.0, 1.25, 1.5)
  - Shows progression left→right
  - Strength values appear in column headers
- **Rows:** Single row (same model/prompt)

**File Output:**
- PNG grid: `ComfyUI/output/lora_tests/mylora_strength_test.png`
- HTML grid: `ComfyUI/output/lora_tests/mylora_strength_test.html`
- Individual images: `mylora_strength_test_0.png` through `mylora_strength_test_5.png`

**Visual Analysis:**
- **0.0:** No LoRA effect (baseline)
- **0.5-0.75:** Subtle effect (often sweet spot)
- **1.0:** Full effect as trained
- **1.25-1.5:** Stronger effect (may be over-applied)

---

## Variations

### Test Multiple Strengths More Granularly
```
lora_0_strengths: "0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0"
```
Creates 10 columns for fine-grained analysis

### Compare Two LoRAs at Same Strengths
```
num_loras: 2
lora_0_strengths: "0.5, 1.0"
lora_1_strengths: "0.5, 1.0"
lora_0_combinator: " " (space - OR mode)
```
Creates 4 rows: LoRA A @ 0.5, LoRA A @ 1.0, LoRA B @ 0.5, LoRA B @ 1.0

### Test LoRA on Multiple Models
Set `num_diffusion_models: 2` in Loaders
Result: 2 rows × 6 columns = 12 images

### Add Prompt Variations
Connect Prompt Compare node to `prompt_config`
Result: Multiple rows (one per prompt) × 6 columns

---

## Advanced: Lightning LoRA as Base

If using a Lightning/speed LoRA as baseline:

1. **LoRA Compare:**
   - `num_loras: 2`
   - `lora_0`: Lightning LoRA
   - `lora_0_strengths`: `1.0` (single value - not tested)
   - `lora_0_ignore_in_grid`: `True` (hide from grid labels)
   - `lora_1`: Your test LoRA
   - `lora_1_strengths`: `0.0, 0.5, 0.75, 1.0, 1.25, 1.5`
   - `lora_1_combinator`: `+` (AND - combine with Lightning)

2. **Result:**
   - All images have Lightning LoRA applied
   - Grid only shows your test LoRA strengths
   - Lightning doesn't appear in labels

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Only 1 image generated | Check `lora_0_strengths` has comma-separated values |
| LoRA not applying | Verify LoRA file exists, check model compatibility |
| All images look identical | Set `seed_mode: fixed`, verify LoRA strengths are different |
| Grid has 2 rows instead of 6 cols | Check `lora_0_combinator` is empty or `+`, not space |

---

## Next Steps

- **AND Logic:** See Example 3 (Multi-LoRA AND Logic)
- **OR Logic:** Test multiple LoRAs separately in same grid
- **Per-Model LoRA:** Use Sampling Config Chain to apply different LoRAs per model
