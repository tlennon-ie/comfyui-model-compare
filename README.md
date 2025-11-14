# ComfyUI Model Compare

A powerful custom node package for ComfyUI that enables side-by-side comparison of different model configurations. Generate and compare all possible combinations of checkpoints, VAEs, text encoders, and LoRAs in a single workflow with a customizable comparison grid.

## Features

- 🔄 **Multi-Model Support**: Compare multiple checkpoints, VAEs, text encoders, and LoRAs simultaneously
- 📊 **Automatic Combination Generation**: Generates all possible combinations of your model selections
- 🎯 **LoRA Strength Testing**: Test each LoRA at multiple strength values (e.g., 0.0, 0.5, 1.0, 1.5)
- 🖼️ **Customizable Comparison Grid**: Arrange results in a visual grid with configurable:
  - Grid dimensions based on model configurations
  - Custom labels for axes (X, Y, Z)
  - Border styling and colors
  - Text labels and fonts
- 💾 **Flexible Output**: Save comparison grids and optionally all individual images
- 🎨 **Full Customization**: Configure fonts, colors, spacing, and layout

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
3. Install dependencies (optional, as most are already in ComfyUI):
   ```bash
   cd comfyui-model-compare
   pip install -r requirements.txt
   ```
4. Restart ComfyUI

## Quick Start

### Basic Workflow

1. **Add Model Compare Loaders Node**
   - Set number of checkpoints, VAEs, text encoders, and LoRAs you want to compare
   - This creates the configuration template

2. **Add Model Compare Loaders Advanced Node**
   - Connect the output from the first node
   - Select specific models from dropdowns for each slot
   - For LoRAs, specify strength values as comma-separated numbers (e.g., "0.0, 0.5, 1.0")

3. **Add Sampler Compare Node**
   - Connect the config, latent, positive/negative conditioning, and other sampling parameters
   - Performs sampling across all combinations

4. **Add Grid Compare Node**
   - Connect sampled images and labels from the Sampler
   - Configure grid appearance, labels, and save location
   - Toggle "Save individuals" to also save individual images

### Example Configuration

**Model Compare Loaders:**
- Number of Checkpoints: 2
- Number of VAEs: 2
- Number of Text Encoders: 0
- Number of LoRAs: 2

**Model Compare Loaders Advanced:**
- Checkpoint 0: `model_v1.safetensors`
- Checkpoint 1: `model_v2.safetensors`
- VAE 0: `vae_model_a.safetensors`
- VAE 1: `vae_model_b.safetensors`
- LoRA 0: `QwenEdit.safetensors` with strengths `0.0, 0.5, 1.0`
- LoRA 1: `DetailBoost.safetensors` with strengths `0.0, 0.75, 1.0`

This creates **2 × 2 × (3 × 3) = 36 combinations** to sample and compare.

## Node Reference

### Model Compare Loaders
Configuration node that defines how many of each model type will be compared.

**Inputs:**
- `num_checkpoints`: Number of base models to compare (0-10)
- `num_vaes`: Number of VAE models to compare (0-5)
- `num_text_encoders`: Number of text encoders to compare (0-5)
- `num_loras`: Number of LoRAs to compare (0-10)

**Output:**
- `config`: Configuration dictionary for downstream nodes

### Model Compare Loaders Advanced
Detailed configuration node where you select specific models and LoRA strengths.

**Inputs:**
- `config`: From Model Compare Loaders
- `checkpoint_0 to checkpoint_9`: Specific checkpoint selections
- `vae_0 to vae_4`: Specific VAE selections
- `text_encoder_0 to text_encoder_4`: Specific text encoder selections
- `lora_0 to lora_9`: Specific LoRA selections
- `lora_0_strengths to lora_9_strengths`: Comma-separated strength values for each LoRA

**Output:**
- `config`: Updated configuration with all model selections

### Sampler Compare
Performs sampling across all model combinations.

**Inputs:**
- `config`: From Model Compare Loaders Advanced
- `latent`: Initial latent tensor
- `steps`: Number of sampling steps
- `cfg`: CFG scale value
- `sampler_name`: Sampling algorithm (euler, dpmpp_2m_sde, etc.)
- `scheduler`: Noise scheduler
- `seed`: Base seed (incremented for each combination)
- `positive`: Positive conditioning
- `negative`: Negative conditioning
- `model` (optional): Base model (used if no checkpoint in combination)
- `clip` (optional): Base CLIP model
- `vae` (optional): Base VAE

**Output:**
- `images`: Concatenated sampled images
- `labels`: String labels for each image

### Grid Compare
Creates a customizable comparison grid from sampled images.

**Inputs:**
- `images`: From Sampler Compare
- `labels`: Image labels from Sampler Compare
- `config`: From Model Compare Loaders Advanced
- `save_location`: Directory to save results (default: `model-compare/ComfyUI`)
- `grid_title`: Title for the comparison grid
- `gap_size`: Pixel spacing between grid cells (0-100)
- `border_color`: Hex color for cell borders (e.g., `#000000`)
- `border_width`: Border thickness in pixels (0-10)
- `text_color`: Hex color for labels (e.g., `#FFFFFF`)
- `font_size`: Font size for labels (8-100)
- `font_name`: System font to use (default, or .ttf filename)
- `save_individuals`: Toggle to save individual images alongside grid
- `x_label`: Label for horizontal axis (e.g., "Checkpoint")
- `y_label`: Label for vertical axis (e.g., "LoRA Configuration")
- `z_label`: Label for depth axis (e.g., "Index")

**Output:**
- `grid_image`: The comparison grid as an image tensor
- `save_path`: Directory where images were saved

## LoRA Strength Format

LoRA strengths are specified as comma-separated values. Examples:

```
Single value:
0.5

Multiple values:
0.0, 0.5, 1.0, 1.5

Range with step:
0.0, 0.25, 0.5, 0.75, 1.0

Precise values:
0.125, 0.375, 0.625, 0.875
```

Each value is tested independently, creating Cartesian products with other LoRAs.

## Output Structure

Results are saved in a timestamped directory:

```
output/
└── model-compare/
    └── ComfyUI/
        └── Model Comparison Grid_20240115_143022/
            ├── grid.png                    # Main comparison grid
            └── individual/                 # (if save_individuals=true)
                ├── image_0000.png
                ├── image_0001.png
                └── ...
```

## Tips & Tricks

### Performance Optimization
- Start with fewer combinations to test your settings
- Use lower resolution for quick iterations
- Increase resolution in final comparisons

### Grid Layout
- Grid dimensions are automatically calculated from configurations
- Number of columns = number of checkpoints
- Number of rows = total images ÷ number of checkpoints

### Custom Fonts
- Use True Type Font (.ttf) filenames
- Place fonts in Windows: `C:\Windows\Fonts`
- Or specify full path to font file

### Color Formatting
- Use hex color codes: `#RRGGBB` (e.g., `#FF0000` for red)
- Valid examples: `#000000` (black), `#FFFFFF` (white), `#FF6600` (orange)

## Troubleshooting

### No images generated
- Verify all model paths are correct
- Check that latent input dimensions match your model
- Ensure positive/negative conditioning inputs are valid

### Grid has wrong dimensions
- Verify the number of checkpoints matches expected columns
- Check that all combinations completed successfully

### Labels are cut off
- Increase `gap_size` or `font_size`
- Adjust grid title length

### Fonts not loading
- Use the full path to the .ttf file
- Ensure font file exists on your system
- Fall back to "default" system font

## Advanced Usage

### Combining with Other Nodes
Connect output from Grid Compare to save nodes:
- Use with VHS (Video Helper Suite) for animated comparisons
- Connect to Image Composite for additional processing
- Export to external tools for batch processing

### Batch Processing
Create multiple comparison workflows in sequence for different model types or prompt variations.

## Requirements

- ComfyUI (latest master branch recommended)
- Python 3.8+
- PyTorch (included with ComfyUI)
- Pillow (included with ComfyUI)
- NumPy (included with ComfyUI)

## License

This project is licensed under the MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Support

For issues, questions, or suggestions:
1. Check the [Troubleshooting](#troubleshooting) section
2. Search existing issues on the repository
3. Create a new issue with:
   - Your ComfyUI version
   - Your workflow JSON
   - Error messages from the console
   - Steps to reproduce

## Roadmap

Planned features for future releases:
- [ ] Video comparison support
- [ ] Interactive web UI for result browsing
- [ ] Advanced statistical analysis
- [ ] Diff/similarity scoring between comparisons
- [ ] Preset configurations library
- [ ] Batch workflow support

## Changelog

### Version 1.0.0 (Initial Release)
- Model Compare Loaders node
- Model Compare Loaders Advanced node
- Sampler Compare node
- Grid Compare node
- Basic customization options
- Individual and grid image saving
