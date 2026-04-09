# Quick Start: Beginner - Compare 3 Models

This is the simplest possible model comparison workflow.

## Goal
Generate the same image with 3 different models and compare the results.

## Setup (5 minutes)

### Step 1: Load Models
1. Add **Model Loader** node
2. Set to load 3 models:
   - Model 1: `sd15_model.safetensors`
   - Model 2: `juggernautXL.safetensors` 
   - Model 3: `flux_dev.safetensors`

### Step 2: Compare Sampling
1. Add **SamplerCompareAdvanced** node
2. Connect models from loader

### Step 3: Configure Each Model
1. For each model, add **SamplingConfigChain** node
2. Set config_type matching the model:
   - Model 1: `STANDARD` (SD 1.5)
   - Model 2: `SDXL` (model 2)
   - Model 3: `FLUX` (model 3)

### Step 4: Set Prompt
In SamplerCompareAdvanced:
- Positive: "a beautiful woman, portrait, detailed"
- Negative: "ugly, blurry"

### Step 5: Run!
Queue the workflow. You'll get 3 images - one from each model.

## Expected Output
Side-by-side comparison grid showing:
- SD 1.5 result
- SDXL result
- FLUX result

All with identical prompt and settings.

## Checklist
- [ ] Added 3 models
- [ ] Connected config chains
- [ ] Entered your prompt
- [ ] Clicked Queue
- [ ] Got 3 images

## Troubleshooting

**"No images generated"**
→ Check Python console for errors. Make sure model files exist.

**"Very slow (5+ min for 3 images)"**
→ This is normal for video models. For image models, should be 30-60 seconds total.

**"Memory error (Out of VRAM)"**
→ Try smaller models or add more time between runs (let VRAM clear).

## Next Steps
Ready to go deeper? Try:
1. **Add LoRA**: Use LoRA Compare node to test different LoRAs
2. **Vary Parameters**: Try comma-separated steps: "15, 20, 30"
3. **More Models**: Add 1-2 more models for larger comparison
