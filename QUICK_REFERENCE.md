# Quick Reference Guide - ComfyUI Model Compare

## 🚀 30-Second Setup

```powershell
# 1. Already installed at:
# e:\AI\Comf\ComfyUI\custom_nodes\comfyui-model-compare\

# 2. Restart ComfyUI
python main.py

# 3. Refresh browser (Ctrl+F5)

# 4. Right-click canvas and search for "Model Compare"
# You should see:
#   - Model Compare Loaders
#   - Model Compare Loaders Advanced
#   - Sampler Compare
#   - Grid Compare
```

## 📦 Node Inputs/Outputs Reference

### 1️⃣ Model Compare Loaders

```
INPUTS:
├─ num_checkpoints      [INT: 0-10]
├─ num_vaes             [INT: 0-5]
├─ num_text_encoders    [INT: 0-5]
└─ num_loras            [INT: 0-10]

OUTPUT:
└─ config (MODEL_COMPARE_CONFIG)
```

### 2️⃣ Model Compare Loaders Advanced

```
INPUTS:
├─ config               (from Node 1)
├─ checkpoint_0..9      (dropdown selectors)
├─ vae_0..4             (dropdown selectors)
├─ text_encoder_0..4    (dropdown selectors)
├─ lora_0..9            (dropdown selectors)
└─ lora_0..9_strengths  (text: "0.5, 1.0, 1.5")

OUTPUT:
└─ config (with combinations)
```

### 3️⃣ Sampler Compare

```
INPUTS:
├─ config               (from Node 2)
├─ latent               (from EmptyLatent or other)
├─ steps                [INT: 1-10000]
├─ cfg                  [FLOAT: 0.0-100.0]
├─ sampler_name         (euler, dpmpp_2m, etc.)
├─ scheduler            (normal, karras, etc.)
├─ seed                 [INT]
├─ positive             (from CLIP text encode)
├─ negative             (from CLIP text encode)
├─ model (optional)     (checkpoint loader)
├─ clip (optional)      (CLIP loader)
└─ vae (optional)       (VAE loader)

OUTPUTS:
├─ images               (concatenated tensor)
└─ labels               (string with newlines)
```

### 4️⃣ Grid Compare

```
INPUTS:
├─ images               (from Sampler Compare)
├─ labels               (from Sampler Compare)
├─ config               (from Node 2)
├─ save_location        (default: "model-compare/ComfyUI")
├─ grid_title           (text string)
├─ gap_size             [INT: 0-100]
├─ border_color         (hex: "#000000")
├─ border_width         [INT: 0-10]
├─ text_color           (hex: "#FFFFFF")
├─ font_size            [INT: 8-100]
├─ font_name            (default or .ttf filename)
├─ save_individuals     (boolean)
├─ x_label (optional)   (e.g., "Checkpoint")
├─ y_label (optional)   (e.g., "LoRA Strength")
└─ z_label (optional)   (e.g., "Index")

OUTPUTS:
├─ grid_image           (image tensor)
└─ save_path            (directory path string)
```

## 💡 Common Configurations

### Config A: Simple Checkpoint Comparison
```
Node 1:  checkpoints=2, vaes=0, encoders=0, loras=0
Node 2:  checkpoint_0="model_v1.ckpt"
         checkpoint_1="model_v2.ckpt"
Result:  2 combinations
```

### Config B: LoRA Strength Testing
```
Node 1:  checkpoints=1, vaes=1, encoders=0, loras=1
Node 2:  checkpoint_0="base_model.ckpt"
         vae_0="vae.ckpt"
         lora_0="detail_lora.ckpt"
         lora_0_strengths="0.0, 0.5, 1.0"
Result:  3 combinations (1 × 1 × 1 × 3)
```

### Config C: Multi-LoRA with Strengths
```
Node 1:  checkpoints=1, vaes=1, encoders=0, loras=2
Node 2:  checkpoint_0="model.ckpt"
         vae_0="vae.ckpt"
         lora_0="detail.ckpt"
         lora_0_strengths="0.5, 1.0"
         lora_1="style.ckpt"
         lora_1_strengths="0.0, 1.0"
Result:  4 combinations (1 × 1 × 1 × 2 × 2)
```

### Config D: Full Comparison
```
Node 1:  checkpoints=3, vaes=2, encoders=1, loras=2
Node 2:  [Select all models]
         lora_0_strengths="0.5, 1.0"
         lora_1_strengths="0.0, 1.0"
Result:  24 combinations (3 × 2 × 1 × 2 × 2)
```

## 🎨 Grid Customization

### Colors (Hex Codes)
```
#000000 = Black
#FFFFFF = White
#FF0000 = Red
#00FF00 = Green
#0000FF = Blue
#FF6600 = Orange
#FF00FF = Magenta
```

### Font Names
```
"default"                    = System default
"arial.ttf"                  = Arial (if installed)
"times.ttf"                  = Times New Roman
"C:\\path\\to\\font.ttf"     = Full path to TTF file
```

### Recommended Settings
```
Border width:   2-4 pixels
Gap size:       10-20 pixels
Font size:      12-20 points
Text color:     White (#FFFFFF) or Black (#000000)
Border color:   Black (#000000) or white with contrast
```

## 📊 Performance Expectations

| Config | Combinations | Time (25 steps) | VRAM | Output Size |
|--------|--------------|-----------------|------|------------|
| 2 ckpt × 1 vae | 2 | 20-30s | 12GB | 50 MB |
| 1 ckpt × 2 loras × 2 str | 4 | 40-60s | 12GB | 100 MB |
| 3 ckpt × 2 vae × 2 loras | 24 | 240-360s | 12GB | 600 MB |
| 3 ckpt × 2 vae × 3 loras | 36 | 360-540s | 12GB | 900 MB |

## 🔧 Troubleshooting Quick Fixes

| Problem | Solution |
|---------|----------|
| Nodes don't appear | Restart ComfyUI, hard refresh (Ctrl+F5) |
| Models not found | Check models in ComfyUI directories |
| Invalid LoRA strengths | Format: "0.5, 1.0, 1.5" (comma-separated) |
| Grid creation fails | Check image dimensions are consistent |
| Out of memory | Reduce combination count or resolution |
| Fonts look wrong | Use "default" or verify .ttf file exists |
| Save path error | Create output directory manually |

## 📁 Output Structure

```
output/model-compare/ComfyUI/
└── Model Comparison_20240115_143022/
    ├── grid.png
    └── individual/
        ├── image_0000.png
        ├── image_0001.png
        └── ...
```

## ⌨️ Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Hard refresh browser | Ctrl+F5 or Cmd+Shift+R |
| Open DevTools | F12 |
| View console errors | F12 → Console tab |
| Duplicate node | Ctrl+C / Ctrl+V |
| Pan canvas | Middle mouse drag |
| Zoom canvas | Mouse wheel |

## 📚 Documentation Files

| File | Contains |
|------|----------|
| `README.md` | User guide, features, examples |
| `SETUP.md` | Installation & configuration |
| `TECHNICAL.md` | Architecture, algorithms, APIs |
| `CONTRIBUTING.md` | Development guidelines |
| `CHANGELOG.md` | Version history & roadmap |
| `PROJECT_SUMMARY.md` | Complete project overview |

## 🆘 Getting Help

```
1. Read: README.md → SETUP.md → TECHNICAL.md
2. Check: example_workflow.json for patterns
3. Review: Console (F12) for error messages
4. Search: GitHub issues for similar problems
5. Create: New issue with reproduction steps
```

## 📋 Workflow Checklist

- [ ] Added all 4 nodes
- [ ] Connected outputs to inputs
- [ ] Loaded checkpoint/clip/vae nodes
- [ ] Set text encoding (positive/negative)
- [ ] Configured sampling parameters
- [ ] Set save location
- [ ] Enabled "save_individuals" if needed
- [ ] Customized grid appearance
- [ ] Queue prompt & watch console
- [ ] Check output directory for results

## 🔄 Quick Iteration Workflow

```
1. Set num_combinations = 2 (small test)
2. Set steps = 5 (quick sample)
3. Queue and check output
4. Increase steps to 20, test again
5. Increase combinations to full count
6. Run final with desired step count
```

## 📖 Common Prompts to Try

**Landscape Comparison:**
```
Positive: "beautiful landscape, mountains, sunset, highly detailed, 4k"
Negative: "blurry, low quality, watermark, distorted"
```

**Portrait Comparison:**
```
Positive: "portrait of beautiful woman, detailed face, professional lighting"
Negative: "blurry face, low quality, distorted, artifacts"
```

**Product Comparison:**
```
Positive: "product photography, studio lighting, white background, professional"
Negative: "blur, shadow, artifacts, low quality"
```

## ⚡ Performance Tips

1. **Reduce Resolution**: 512×512 instead of 1024×1024
2. **Reduce Steps**: 20 instead of 50 for testing
3. **Limit Combinations**: Start with 2-4, scale up
4. **Use Efficient Sampler**: dpmpp_2m instead of dpmpp_3m
5. **Batch Operations**: Compare models by type (first ckpt, then vae, then lora)

## 🎯 Grid Design Patterns

**Checkpoint vs LoRA:**
```
   Model A  Model B
0.5: [img] [img]
1.0: [img] [img]
```

**Multi-LoRA Strength:**
```
   LoRA A   LoRA A
   0.5      1.0
LoRA_B: [img] [img]
0.0: 
LoRA_B: [img] [img]
1.0:
```

**3-Way Comparison:**
```
     VAE_A    VAE_B
Ckpt_A: [img]  [img]
Ckpt_B: [img]  [img]
```

---

**Remember**: Start simple, test often, scale gradually!

For detailed information, see the full documentation files.
