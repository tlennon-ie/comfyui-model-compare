# ComfyUI Model Compare

A streamlined custom node package for ComfyUI that enables side-by-side comparison of different model configurations. Test LoRA strength variations, model configurations, and CLIP variations for FLUX and QWEN models in a single workflow with a customizable comparison grid.

## Features

- ✨ **FLUX & QWEN Support**: Optimized for both FLUX and QWEN diffusion models
- 🔄 **Multi-Model Variants**: Compare multiple checkpoints, VAEs, and text encoders (including FLUX clip pairs)
- 📊 **LoRA Strength Testing**: Test LoRAs at multiple strength values (e.g., 0.0, 0.5, 1.0, 1.5) with proper isolation
- 🎨 **CLIP Pair Variations**: For FLUX, test different clip_model_a/b pairs; for QWEN, test different single clips
- 🖼️ **Customizable Comparison Grid**: Arrange results in a visual grid with:
  - Custom labels for axes
  - Border styling and colors
  - Text labels and configurable fonts
- 💾 **Flexible Output**: Save comparison grids and optionally all individual images
- 🎯 **Fixed Seed Comparison**: Same seed across iterations for isolated variable testing

## Installation

### Method 1: ComfyUI Manager (Recommended)
1. Install [ComfyUI Manager](https://github.com/ltdrdata/ComfyUI-Manager)
2. Open ComfyUI Manager in your ComfyUI interface
3. Search for "Model Compare"
4. Click Install

### Method 2: Manual Installation
1. Navigate to your ComfyUI custom nodes directory:
   ```bash
   cd ComfyUI/custom_nodes/
   ```
2. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/comfyui-model-compare.git
   ```
3. Install dependencies:
   ```bash
   cd comfyui-model-compare
   pip install -r requirements.txt
   ```
4. Restart ComfyUI

## Quick Start

### Basic Workflow

1. **Add ModelCompareLoaders Node**
   - Configure number of model variations, VAE variations, CLIP variations, and LoRAs
   - Select specific models and LoRA strength values
   - For FLUX: set clip_model_a and clip_model_b (paired clips)
   - For QWEN: set clip_model (single clip)

2. **Add SamplerCompareSimple Node**
   - Connect the config and models from ModelCompareLoaders
   - Set sampling parameters (steps, cfg, sampler, scheduler, seed)
   - The sampler handles all combinations with fixed seed for comparison isolation

3. **Add GridCompare Node**
   - Connect images and labels from the sampler
   - Configure grid appearance, labels, and save location
   - Toggle "Save individuals" to also save individual comparison images

### Example Configuration

**ModelCompareLoaders:**
- Preset: FLUX
- Diffusion Model: `flux1-dev.safetensors`
- VAE: `flux_vae.safetensors`
- Clip Model (FLUX pair): 
  - clip_model_a: `clip_l.safetensors`
  - clip_model_b: `t5xxl_fp16.safetensors`
- Num LoRAs: 2
- LoRA 1: `AidmaMJ6.safetensors` with strengths `0.0, 1.0`
- LoRA 2: `UltraReal.safetensors` with combiner `OR`

This creates **4 combinations** (2 LoRA groups with 2 strength options each).

## Understanding the Nodes

### ModelCompareLoaders
Loads models and generates all comparison combinations.

**Key Inputs:**
- `preset`: "FLUX" or "QWEN" (determines CLIP loading strategy)
- `diffusion_model`: The base diffusion model
- `vae`: The VAE encoder/decoder
- `clip_model`: For QWEN, the single clip model
- `clip_model_a`, `clip_model_b`: For FLUX, the paired clip models
- `num_clip_variations`: How many clip variations to test (1-5)
- `num_loras`: Number of LoRAs to compare (0-10)

**CLIP Variations:**
- **FLUX**: Collect multiple clip_model_a/b pairs for testing (e.g., different T5XXL + CLIP-L combinations)
- **QWEN**: Collect multiple single clip models for testing

**Output:**
- `config`: Configuration with all combinations
- `base_model`: The diffusion model
- `base_clip`: The base CLIP model (for text encoding)
- `base_vae`: The VAE model

### SamplerCompareSimple
Simplified sampler that processes all combinations with standard KSampler logic.

**Key Inputs:**
- `config`: From ModelCompareLoaders
- `model`: The diffusion model
- `positive`: Text conditioning (positive)
- `negative`: Text conditioning (negative)
- `latent`: Initial latent noise
- `steps`, `cfg`: Sampling parameters
- `sampler_name`, `scheduler`: Sampling algorithm settings
- `seed`: Base seed (same across all combinations for isolation)
- `denoise`: Denoising strength

**Output:**
- `images`: All generated images concatenated
- `labels`: Labels for each image

**How It Works:**
- For each combination: Clone model → Apply LoRAs → Sample with fixed seed → Decode
- LoRAs with strength 0.0 are skipped (no effect)
- Each combination uses the same seed to isolate variables
- CLIP variations are tracked but conditioning is pre-encoded

### GridCompare
Creates a customizable visual comparison grid.

**Key Inputs:**
- `images`: From SamplerCompareSimple
- `labels`: Labels from SamplerCompareSimple
- `config`: From ModelCompareLoaders
- `save_location`: Where to save results
- `grid_title`: Title for the grid
- `gap_size`: Spacing between images
- `border_color`: Cell border color (hex: #RRGGBB)
- `border_width`: Border thickness in pixels
- `text_color`: Label text color
- `font_size`: Label font size
- `x_label`, `y_label`, `z_label`: Axis labels

**Output:**
- `grid_image`: The comparison grid
- `save_path`: Directory where images were saved

## LoRA Strength Format

Specify strengths as comma-separated values:

```
0.0              # No effect (skipped in sampling)
0.5              # Single strength
0.0, 0.5, 1.0    # Multiple strengths (creates Cartesian product)
```

### LoRA Combiners (AND/OR)

- **AND**: Include in all combinations with other LoRAs
- **OR**: Test this LoRA group separately from others

Example:
- LoRA 1 (Style): strengths [0.0, 1.0], combiner AND
- LoRA 2 (Detail): strengths [0.0, 1.0], combiner OR

Creates: (Style 0.0 + Detail 0.0) | (Style 0.0 + Detail 1.0) | (Style 1.0 + Detail 0.0) | (Style 1.0 + Detail 1.0)

## FLUX vs QWEN

### FLUX Configuration
- **CLIP Setup**: Requires TWO models: `clip_model_a` (CLIP-L) and `clip_model_b` (T5XXL)
- **CLIP Variations**: Can test different clip_a/b pairs (e.g., different T5XXL versions)
- **Example**: 
  ```
  clip_model_a: clip_l.safetensors
  clip_model_b: t5xxl_fp16.safetensors
  clip_model_1_a: clip_l.safetensors
  clip_model_1_b: t5xxl_nf4.safetensors  (different quantization)
  ```

### QWEN Configuration
- **CLIP Setup**: Single model: `clip_model`
- **CLIP Variations**: Can test different single clips
- **Example**:
  ```
  clip_model: qwen_vl_model.safetensors
  clip_model_1: qwen_vl_model_v2.safetensors
  ```

## Output Structure

Results are saved in a timestamped directory:

```
output/
└── model-compare/
    └── ComfyUI/
        └── model_compare_grid_20250119_143022/
            ├── comparison_grid.png         # Main grid
            ├── metadata.json               # Configuration info
            └── individual/                 # (if save_individuals=true)
                ├── image_0000.png
                ├── image_0001.png
                └── ...
```

## Tips & Tricks

### Performance
- Start with few LoRAs and strengths to iterate quickly
- Use lower resolution/shorter steps for testing
- Increase for final comparisons

### Grid Dimensions
- Columns = Number of model variations
- Rows = Number of LoRA group combinations
- Larger grids are automatically arranged

### CLIP Variations for FLUX
- Test different T5XXL versions (full vs quantized)
- Test different CLIP-L versions
- Test different tokenizers/embeddings

### Custom Fonts
- Use .ttf files from your system
- Windows: Files in `C:\Windows\Fonts` can be referenced by name
- Or specify full path: `C:\path\to\font.ttf`

### Color Tips
- Use hex colors: `#RRGGBB`
- Examples: `#000000` (black), `#FFFFFF` (white), `#FF6600` (orange)

## Troubleshooting

### "CLIP missing" warning appears
This is a false alarm in ComfyUI when loading FLUX clip pairs. The CLIP is loading correctly even with the warning. You'll see "Requested to load FluxClipModel_" and "loaded completely" confirming it's working.

### No images generated
- Check that all model paths are correct and files exist
- Verify latent dimensions match your model
- Ensure positive/negative conditioning are valid
- Check ComfyUI console for error messages

### Wrong number of combinations
- Each variation type multiplies combinations: model × vae × clip_variation × lora_group
- Verify `num_loras` matches the LoRAs you've configured
- Check that LoRA strengths are valid numbers

### Grid has wrong dimensions
- Grid rows = number of LoRA groups (OR splits create groups)
- Grid columns = total combinations ÷ rows
- Verify your AND/OR combiner settings

### Labels are cut off
- Increase `gap_size` between images
- Reduce `font_size`
- Shorten custom labels
- Make grid larger (higher resolution input)

## Requirements

- ComfyUI (latest master recommended)
- Python 3.8+
- PyTorch (included with ComfyUI)
- Pillow (included with ComfyUI)
- NumPy (included with ComfyUI)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please submit issues and pull requests.

## Changelog

### Version 3.0.0 (Current)
- Complete sampler rewrite - simplified architecture matching standard KSampler
- FLUX clip pair variation support
- Fixed LoRA strength application (0.0 properly skips LoRA)
- Proper model cloning for each iteration
- Fixed seed behavior for accurate comparison isolation
- Removed redundant sampler implementations
- Enhanced documentation for FLUX vs QWEN

### Version 2.x
- Added FLUX preset support
- Improved grid visualization
- Custom label support

### Version 1.0.0
- Initial release with basic model comparison
