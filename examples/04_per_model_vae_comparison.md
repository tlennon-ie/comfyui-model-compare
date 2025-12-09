# Example 4: Per-Model VAE Comparison

**Difficulty:** ⭐⭐⭐ Advanced  
**Use Case:** Test different VAEs with each model variation  
**Expected Output:** Grid showing model × VAE combinations

## Goal

Compare how different VAEs affect each model's output. Useful for finding optimal VAE per model or testing VAE quality.

## Workflow Structure

```
VAE Config ──────┐
                 ├──→ Sampling Config Chain (var 0) ──┐
Model Loaders ───┘                                     │
                                                       ├──→ Sampler → Grid
VAE Config ──────┐                                     │
                 ├──→ Sampling Config Chain (var 1) ──┘
Model Loaders ───┘
```

## Key Concept: Config Chains

**Sampling Config Chain** nodes configure individual model variations. Each chain specifies:
- `variation_index`: Which model (0, 1, 2...)
- VAE, CLIP, sampling parameters specific to that model

Chains connect sequentially, building up configuration.

---

## Step-by-Step Setup

### 1. Add VAE Config Node (for variation 0)

**Location:** Right-click → Model Compare → Loaders → VAE Config

**Settings:**
- `num_vaes`: `2` (or 3 for more VAEs)
- `vae_0`: Select first VAE (e.g., `sdxl_vae.safetensors`)
- `vae_0_label`: `SDXL VAE`
- `vae_1`: Select second VAE (e.g., `mse_vae.safetensors`)
- `vae_1_label`: `MSE VAE`
- `vae_2`: (Optional) `__baked__` to test checkpoint's built-in VAE
- `vae_2_label`: `Baked`

**Output:** `vae_config` (VAE_COMPARE_CONFIG)

---

### 2. Add Model Compare Loaders Node

**Settings:**
- `preset`: `SDXL` (or your architecture)
- `num_diffusion_models`: `2` (testing 2 models)
- `diffusion_model`: Select first model
- `diffusion_model_variation_1`: Select second model

**Output:** `config` (base MODEL_COMPARE_CONFIG)

**Note:** Don't connect VAE directly to Loaders - use chains instead

---

### 3. Add Sampling Config Chain Node (Variation 0)

**Location:** Right-click → Model Compare → Sampling Config Chain

**Settings:**
- `variation_index`: `0` (**Important - configures first model**)
- `config_type`: `SDXL` (match your model type)
- `seed`: `12345`
- `steps`: `20`
- `cfg`: `7.0`
- `sampler_name`: `dpmpp_2m`
- `scheduler`: `karras`
- `width`: `1024`
- `height`: `1024`

**Connections:**
- Connect `config` from Model Loaders → `config` input on Chain
- Connect `vae_config` from VAE Config → `vae_config` input on Chain

**Output:** `config` (updated with VAE variations for model 0)

---

### 4. Add VAE Config Node (for variation 1)

**Settings:**
- `num_vaes`: `2` (same or different VAEs)
- `vae_0`: Different VAE or same set
- `vae_0_label`: `SDXL VAE`
- `vae_1`: Second VAE
- `vae_1_label`: `MSE VAE`

**Output:** `vae_config`

**Note:** You can reuse the same VAE Config node for all variations if testing same VAEs

---

### 5. Add Sampling Config Chain Node (Variation 1)

**Settings:**
- `variation_index`: `1` (**Configures second model**)
- `config_type`: `SDXL`
- Other params same as variation 0 chain

**Connections:**
- Connect `config` output from **previous chain** (variation 0) → `config` input
- Connect `vae_config` from VAE Config → `vae_config` input

**Output:** `config` (now has VAE variations for both models)

---

### 6. Add Sampler Compare Advanced Node

**Settings:**
- Standard sampling settings (will be overridden by chains)

**Connections:**
- Connect `config` from **final chain** → `config` input

**Output:** `images` (2 models × 2 VAEs = 4 images)

---

### 7. Add Grid Compare Node

**Settings:**
- `output_folder`: `vae_tests`
- `output_filename`: `model_vae_comparison`
- `cell_size`: `512`

**Connections:**
- Connect `images` and `config` from Sampler

---

## Expected Result

**Grid Layout (2 models × 2 VAEs):**
```
            SDXL VAE    MSE VAE
Model A     [Image]     [Image]
Model B     [Image]     [Image]
```

**Grid Structure:**
- **Rows:** model
- **Columns:** vae

**Combination Count:** 2 models × 2 VAEs = 4 images

---

## Variations

### Test 3 VAEs per Model

In VAE Config node:
```
num_vaes: 3
vae_0: SDXL VAE
vae_1: MSE VAE
vae_2: __baked__
```
Result: 2 models × 3 VAEs = 6 images

### Test VAE Only on One Model

**Setup:**
- Chain 0: Connect VAE Config (2 VAEs)
- Chain 1: Leave `vae_config` disconnected (uses default)

**Result:** 
- Model 0: 2 images (with VAE variations)
- Model 1: 1 image (no VAE variation)
- Total: 3 images (ragged grid)

### Combine with LoRA Testing

Add LoRA Compare node:
```
lora_0_strengths: "0.5, 1.0"
```
Connect to Loaders `lora_variation_0`

**Result:** 2 models × 2 VAEs × 2 LoRA strengths = 8 images

---

## Advanced: Different VAEs Per Model

Test VAE A on Model A, VAE B on Model B:

**VAE Config 1 (for Model A):**
```
num_vaes: 1
vae_0: SDXL VAE
```

**VAE Config 2 (for Model B):**
```
num_vaes: 1
vae_0: MSE VAE
```

**Chains:**
- Chain 0: Connect VAE Config 1
- Chain 1: Connect VAE Config 2

**Result:** 2 images (one per model, each with different VAE)

---

## Using `__baked__` VAE

Special value `__baked__` uses the checkpoint's built-in VAE:

**Use Case:** Compare external VAE vs checkpoint's VAE
```
vae_0: "sdxl_vae.safetensors"
vae_1: "__baked__"
```

**Result:** Shows difference between external and built-in VAE

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Chain not updating config | Verify `variation_index` matches model (0, 1, 2...) |
| Wrong VAE applied | Check chains connect sequentially: Loaders → Chain0 → Chain1 → Sampler |
| Too many images | Check if VAE Config connected to multiple chains unintentionally |
| VAE not loading | Verify VAE file exists in ComfyUI/models/vae/ |
| `__baked__` not working | Ensure model checkpoint has embedded VAE |

---

## Understanding Config Chains

**Flow:**
```
Loaders creates base config with 2 models
↓
Chain 0 adds VAE variations (2) to model 0
→ Config now has: Model 0 (2 VAE variants), Model 1 (default)
↓
Chain 1 adds VAE variations (2) to model 1
→ Config now has: Model 0 (2 VAE variants), Model 1 (2 VAE variants)
↓
Sampler generates all combinations: 2×2 = 4 images
```

**Key Rule:** Each chain processes `variation_index` sequentially

---

## Next Steps

- **CLIP Config:** Similar pattern to test CLIP variations (Example 5)
- **Cross-Architecture:** Different model types with chains (Example 5)
- **Complex Chains:** Add dimensions, sampling params per model
