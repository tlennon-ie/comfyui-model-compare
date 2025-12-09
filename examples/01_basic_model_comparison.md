# Example 1: Basic Model Comparison

**Difficulty:** ⭐ Beginner  
**Use Case:** Compare 2-3 models with identical settings  
**Expected Output:** Simple grid with one model per column

## Goal

Generate a side-by-side comparison of different models using the same prompt and sampling parameters.

## Workflow Structure

```
Model Compare Loaders → Sampler Compare Advanced → Grid Compare
```

## Step-by-Step Setup

### 1. Add Model Compare Loaders Node

**Location:** Right-click → Model Compare → Loaders → Model Compare Loaders

**Settings:**
- `preset`: Select your model architecture
  - For FLUX models: `FLUX`
  - For SDXL models: `SDXL`
  - For QWEN models: `QWEN`
- `num_diffusion_models`: `2` (or 3 for three-way comparison)
- `diffusion_model`: Select your first model
- `diffusion_model_variation_1`: Select your second model
- `diffusion_model_variation_2`: (Optional) Select third model
- Leave `prompt_config` and `lora_variation_0` disconnected for now

**Output:** `config` (MODEL_COMPARE_CONFIG)

---

### 2. Add Sampler Compare Advanced Node

**Location:** Right-click → Model Compare → Sampling → Sampler Compare Advanced

**Settings:**
- `seed`: `12345` (or any seed value)
  - Use `fixed` to keep same seed across all models
  - Use `increment` to vary seed per model
- `steps`: `20` (adjust based on model)
- `cfg`: `3.5` (for FLUX), `7.0` (for SDXL)
- `sampler_name`: `euler` or `dpmpp_2m`
- `scheduler`: `simple` or `normal`
- Leave global overrides at `0` for now

**Connections:**
- Connect `config` output from Loaders → `config` input on Sampler

**Outputs:** `images`, `config`, `labels`

---

### 3. Add Grid Compare Node

**Location:** Right-click → Model Compare → Grid → Grid Compare

**Settings:**
- `output_folder`: `comparison_grids`
- `output_filename`: `model_comparison`
- `cell_size`: `512` (adjust based on your output resolution)
- `save_individual_images`: `False` (set to `True` if you want individual files)
- `embed_workflow`: `True` (embeds workflow in PNG metadata)

**Connections:**
- Connect `images` output from Sampler → `images` input on Grid
- Connect `config` output from Sampler → `config` input on Grid

**Outputs:** `images`, `save_path`, `video_path`

---

## Expected Result

**Grid Layout:**
- **Columns:** model (one per model variation)
- **Rows:** Single row (same prompt/settings)

**File Output:**
- PNG grid: `ComfyUI/output/comparison_grids/model_comparison.png`
- HTML grid: `ComfyUI/output/comparison_grids/model_comparison.html`

**Grid Labels:**
- Column headers will show model names
- No row headers (only 1 row)

---

## Variations

### Three-Way Comparison
Set `num_diffusion_models: 3` and add `diffusion_model_variation_2`

### Different Resolution per Model
Add Sampling Config Chain nodes (see Example 4)

### Add Prompt Variations
Connect a Prompt Compare node to `prompt_config` input (see Example 7)

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Only one image generated | Check `num_diffusion_models` is set to 2 or 3 |
| Models not loading | Verify model paths exist, check preset matches model type |
| Grid looks wrong | Adjust `cell_size` to match your output resolution |
| No HTML file | Check `output_folder` exists and has write permissions |

---

## Next Steps

- **Add LoRAs:** See Example 2 (LoRA Strength Testing)
- **Add Prompts:** Connect Prompt Compare node
- **Customize Layout:** See Example 6 (Custom Grid Layout)
