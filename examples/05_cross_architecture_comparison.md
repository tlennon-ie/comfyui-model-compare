# Example 5: Cross-Architecture Comparison

**Difficulty:** ⭐⭐⭐ Advanced  
**Use Case:** Compare FLUX vs QWEN vs SDXL directly  
**Expected Output:** Grid with architecture-specific settings per model

## Goal

Compare models from different architectures (FLUX, QWEN, SDXL, WAN, etc.) with appropriate settings for each architecture.

## Why Use Chains?

Different architectures need different settings:
- **FLUX:** cfg ~3.5, shift parameters, 16ch latent
- **QWEN:** cfg ~3.5, qwen_shift ~1.15, AuraFlow sampling
- **SDXL:** cfg ~7.0, standard sampling, 4ch latent
- **WAN 2.1:** shift ~8.0, video frames, 16ch latent

**Sampling Config Chain** lets you set architecture-specific parameters per model.

---

## Workflow Structure

```
Model Loaders → Chain (FLUX) → Chain (QWEN) → Chain (SDXL) → Sampler → Grid
```

Each chain configures one model variation with appropriate settings.

---

## Step-by-Step Setup

### 1. Add Model Compare Loaders Node

**Settings:**
- `preset`: `FLUX` (this is default, will be overridden by chains)
- `num_diffusion_models`: `3` (FLUX, QWEN, SDXL)
- `diffusion_model`: Select FLUX model
- `diffusion_model_variation_1`: Select QWEN model
- `diffusion_model_variation_2`: Select SDXL model

**Output:** `config` with 3 models

**Note:** Preset doesn't matter much here since chains override config_type

---

### 2. Add Sampling Config Chain (FLUX - Variation 0)

**Location:** Right-click → Model Compare → Sampling Config Chain

**Settings:**
- `variation_index`: `0` (**FLUX model**)
- `config_type`: `FLUX` (**Important - enables FLUX-specific params**)
- `seed`: `12345`
- `steps`: `20`
- `cfg`: `3.5` (FLUX uses lower CFG)
- `sampler_name`: `euler`
- `scheduler`: `simple`
- `width`: `1024`
- `height`: `1024`
- `flux_guidance`: `3.5` (FLUX-specific)

**Connections:**
- Connect `config` from Loaders → `config` input

**Output:** `config` (with FLUX settings for model 0)

---

### 3. Add Sampling Config Chain (QWEN - Variation 1)

**Settings:**
- `variation_index`: `1` (**QWEN model**)
- `config_type`: `QWEN` (**Enables QWEN params**)
- `seed`: `12345` (same seed for fair comparison)
- `steps`: `20`
- `cfg`: `3.5`
- `sampler_name`: `euler` (QWEN uses AuraFlow internally)
- `scheduler`: `simple`
- `width`: `1024`
- `height`: `1024`
- `qwen_shift`: `1.15` (QWEN-specific shift parameter)

**Connections:**
- Connect `config` from **Chain 0** → `config` input

**Output:** `config` (now has FLUX + QWEN settings)

---

### 4. Add Sampling Config Chain (SDXL - Variation 2)

**Settings:**
- `variation_index`: `2` (**SDXL model**)
- `config_type`: `SDXL` (**Standard SDXL**)
- `seed`: `12345`
- `steps`: `20`
- `cfg`: `7.0` (SDXL uses higher CFG)
- `sampler_name`: `dpmpp_2m`
- `scheduler`: `karras`
- `width`: `1024`
- `height`: `1024`

**Connections:**
- Connect `config` from **Chain 1** → `config` input

**Output:** `config` (now has all 3 architectures configured)

---

### 5. Add Sampler Compare Advanced Node

**Settings:**
- Leave at defaults (chains override everything)
- `num_global_overrides`: `0`

**Connections:**
- Connect `config` from **Chain 2** → `config` input

**Output:** `images` (3 images, one per architecture)

---

### 6. Add Grid Compare Node

**Settings:**
- `output_folder`: `architecture_comparison`
- `output_filename`: `flux_qwen_sdxl`
- `cell_size`: `512`

**Connections:**
- Connect `images` and `config` from Sampler

---

## Expected Result

**Grid Layout:**
```
FLUX        QWEN        SDXL
[Image]     [Image]     [Image]
```

**Labels:**
- Column headers: Model names
- Shows architecture differences clearly

**File Output:**
- PNG: `ComfyUI/output/architecture_comparison/flux_qwen_sdxl.png`
- HTML: Interactive grid with metadata showing different settings per model

---

## Understanding Config Types

### Available Config Types

| config_type | Architecture | Special Parameters | Latent Channels |
|-------------|-------------|-------------------|-----------------|
| `STANDARD` | Generic | None | Auto-detect |
| `FLUX` | FLUX Dev/Schnell | flux_guidance | 16ch |
| `FLUX2` | FLUX.2 | flux_guidance | 128ch |
| `QWEN` | QWEN | qwen_shift | 16ch |
| `SDXL` | SDXL 1.0 | None | 4ch |
| `WAN2.1` | WAN 2.1 | wan_shift, num_frames | 16ch |
| `WAN2.2` | WAN 2.2 | wan_shift, num_frames | 16ch |
| `HUNYUAN_VIDEO` | Hunyuan 1.0 | hunyuan_shift, num_frames | 16ch |
| `HUNYUAN_VIDEO_15` | Hunyuan 1.5 | hunyuan_shift, num_frames | 16ch |

### Chain Field Visibility

Setting `config_type` shows/hides relevant fields:
- **FLUX:** Shows `flux_guidance`
- **QWEN:** Shows `qwen_shift`
- **WAN:** Shows `wan_shift`, `num_frames`
- **Video models:** Shows `reference_image_1/2/3`, `start_frame`, `end_frame`

---

## Variations

### Four-Way: FLUX vs FLUX2 vs QWEN vs SDXL

Add fourth model and chain:
```
num_diffusion_models: 4
Chain 3: config_type: FLUX2, variation_index: 3
```

### Add LoRA to One Architecture

**Example:** Test LoRA only on FLUX

**LoRA Compare:**
```
num_loras: 1
lora_0_strengths: "0.5, 1.0"
```

**Chain 0 (FLUX):**
- Connect `lora_config` from LoRA Compare → `lora_config` input

**Chains 1, 2:** Leave `lora_config` disconnected

**Result:**
- FLUX: 2 images (with LoRA at 0.5 and 1.0)
- QWEN: 1 image (no LoRA)
- SDXL: 1 image (no LoRA)
- Total: 4 images (ragged grid)

### Video vs Image Models

**Example:** WAN 2.1 vs FLUX

**Chain 0 (WAN):**
```
config_type: WAN2.1
wan_shift: 8.0
num_frames: 25
width: 832
height: 480
```

**Chain 1 (FLUX):**
```
config_type: FLUX
width: 1024
height: 1024
(no num_frames)
```

**Grid Compare:**
- Connect `video_config` for video output
- Result: Video grid with WAN animated, FLUX static

---

## Advanced: Different Resolutions Per Architecture

**Use Case:** SDXL at 1024×1024, FLUX at 1360×768

**Chain 0 (FLUX):**
```
width: 1360
height: 768
```

**Chain 1 (SDXL):**
```
width: 1024
height: 1024
```

**Grid Compare:**
- Set `cell_size` to accommodate largest dimension
- Grid will handle different sized images automatically

---

## Common Architecture Combinations

### General Purpose
```
FLUX + SDXL + QWEN
→ Compare latest architectures
```

### Video Comparison
```
WAN 2.1 + WAN 2.2 + HUNYUAN_VIDEO
→ Compare video models
```

### Same Base, Different Configs
```
FLUX + FLUX + FLUX (3 variations)
Chain 0: cfg 2.5
Chain 1: cfg 3.5
Chain 2: cfg 5.0
→ Test CFG effect on same model
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Wrong settings applied | Check `variation_index` matches model order (0, 1, 2...) |
| Special params not showing | Verify `config_type` set correctly in chain |
| Latent size errors | Ensure `config_type` matches model architecture |
| Chain ignored | Verify chains connect sequentially: Loaders → C0 → C1 → C2 → Sampler |
| Video/image mismatch | Video models need `num_frames > 1` in chain |

---

## Performance Tips

1. **Use Grid Preview:** Verify 3 images will be generated before sampling
2. **Test Resolution:** Start at 512×512 for quick tests
3. **Same Seed:** Use fixed seed across all chains for fair comparison
4. **Skip Global Overrides:** Let chains handle all settings

---

## Next Steps

- **Custom Layout:** Use Grid Preset Formula to control hierarchy (Example 6)
- **Prompt Variations:** Add Prompt Compare to test across architectures
- **VAE/CLIP per Architecture:** Combine with Example 4 patterns
