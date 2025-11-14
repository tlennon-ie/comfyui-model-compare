# ComfyUI Model Compare Setup Guide

## Installation Quick Start

### For GitHub Cloning

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/yourusername/comfyui-model-compare.git
cd comfyui-model-compare
pip install -r requirements.txt
```

### For ComfyUI Manager Users

1. Open ComfyUI in your browser
2. Click "ComfyUI Manager" button
3. Search for "Model Compare"
4. Click "Install"
5. Restart ComfyUI

## Repository Setup

### Before Publishing

1. **Update author information** in:
   - `__init__.py`: Change author/version as needed
   - `README.md`: Update author, repository URL, license
   - `node_list.json`: Update all fields to match your GitHub repo
   - `LICENSE`: Update copyright year and name

2. **Create GitHub repository**:
   ```bash
   cd comfyui-model-compare
   git init
   git add .
   git commit -m "Initial commit: ComfyUI Model Compare nodes"
   git branch -M main
   git remote add origin https://github.com/yourusername/comfyui-model-compare.git
   git push -u origin main
   ```

3. **Add to ComfyUI Manager** (optional, for wider distribution):
   - Submit PR to https://github.com/ltdrdata/ComfyUI-Manager
   - Add entry to their node_list.json
   - Include node_list.json and installation instructions

## Project Structure

```
comfyui-model-compare/
├── __init__.py                    # Package initialization & node exports
├── model_compare_loaders.py       # Configuration nodes
├── sampler_compare.py             # Sampling node
├── grid_compare.py                # Grid creation & saving
├── README.md                       # User documentation
├── SETUP.md                       # This file
├── requirements.txt               # Python dependencies
├── node_list.json                 # ComfyUI Manager metadata
├── LICENSE                        # MIT License
└── .gitignore                     # Git ignore rules
```

## Node Architecture

### Three-Node Pipeline

1. **Model Compare Loaders** → Defines configuration template
2. **Model Compare Loaders Advanced** → Selects specific models
3. **Sampler Compare** → Samples all combinations
4. **Grid Compare** → Creates comparison grid

### Data Flow

```
[Model Compare Loaders]
         ↓
         → config (MODEL_COMPARE_CONFIG)
         ↓
[Model Compare Loaders Advanced] → updates config with model selections
         ↓
         → config + combinations list
         ↓
[Sampler Compare] → samples all combinations
         ↓
         → images (concatenated) + labels (string)
         ↓
[Grid Compare] → creates grid + saves results
         ↓
         → grid_image + save_path
```

## How to Use

### Basic Workflow Example

1. Add **Model Compare Loaders** node
   - Set: Checkpoints=2, VAEs=1, Text Encoders=0, LoRAs=2

2. Add **Model Compare Loaders Advanced** node
   - Connect config from step 1
   - Select checkpoint_0: model_a.safetensors
   - Select checkpoint_1: model_b.safetensors
   - Select vae_0: vae.safetensors
   - Select lora_0: lora_a.safetensors, strengths: "0.5, 1.0"
   - Select lora_1: lora_b.safetensors, strengths: "0.0, 1.0"

3. Add **Sampler Compare** node
   - Connect config, latent, conditioning
   - Set sampling parameters (steps, cfg, sampler, etc.)

4. Add **Grid Compare** node
   - Connect images and labels from sampler
   - Configure grid appearance
   - Choose save location

5. Connect output to save node or preview

## Development Notes

### Extending the Nodes

**Adding new features to ModelCompareLoaders:**
- Add new `@classmethod INPUT_TYPES` entries
- Update `configure_models()` to handle new config keys
- Pass through to downstream nodes

**Customizing SamplerCompare:**
- Modify `_sample_latent()` for different sampling algorithms
- Add support for additional conditioning inputs
- Implement custom progress reporting

**Grid Styling Options:**
- Add more font options in GridCompare `INPUT_TYPES`
- Implement more border styles
- Add background gradient support

### Testing

```python
# Test individual node logic
from model_compare_loaders import ModelCompareLoadersAdvanced

config = {"num_checkpoints": 2, "num_loras": 2, ...}
combinations = ModelCompareLoadersAdvanced._compute_combinations(config)
print(f"Generated {len(combinations)} combinations")
```

## Troubleshooting Installation

### Import Errors
- Ensure all files are in `custom_nodes/comfyui-model-compare/`
- Verify `__init__.py` exists and imports are correct
- Restart ComfyUI after adding files

### Model Not Showing in Node List
- Clear ComfyUI cache: Delete `web/js/comfyui.js` or browser cache
- Reload page with Ctrl+F5
- Check console for import errors (press F12)

### LoRA/Checkpoint Paths
- Ensure models are in standard ComfyUI directories:
  - Checkpoints: `models/checkpoints/`
  - VAEs: `models/vae/`
  - LoRAs: `models/loras/`
  - Text encoders: `models/clip/`

## Performance Considerations

### Combination Explosion
- 3 checkpoints × 2 VAEs × 2 LoRAs × 3 strengths = **36 samples**
- Keep initial tests small, scale up for production
- Consider memory constraints

### Optimization Tips
1. Use lower resolution for testing
2. Test with 1-2 checkpoints first
3. Batch process if hitting memory limits
4. Use efficient samplers (dpmpp_2m_sde or euler)

## API/Node Types

Custom data types used:
- `MODEL_COMPARE_CONFIG`: Dictionary containing model selections and combinations

Example config structure:
```python
{
    "num_checkpoints": 2,
    "num_vaes": 1,
    "num_text_encoders": 0,
    "num_loras": 2,
    "checkpoints": ["model_a.safetensors", "model_b.safetensors"],
    "vaes": ["vae.safetensors"],
    "text_encoders": [],
    "loras": [
        {"name": "lora_a.safetensors", "strengths": [0.5, 1.0]},
        {"name": "lora_b.safetensors", "strengths": [0.0, 1.0]}
    ],
    "combinations": [
        {
            "checkpoint": "model_a.safetensors",
            "vae": "vae.safetensors",
            "text_encoder": None,
            "lora_strengths": (0.5, 0.0),
            "lora_names": ["lora_a.safetensors", "lora_b.safetensors"],
            "label": "ckpt:model_a | vae:vae | lora_a:0.50 | lora_b:0.00"
        },
        ...
    ]
}
```

## Next Steps

1. Test the nodes in your ComfyUI installation
2. Create example workflows
3. Gather user feedback
4. Add web UI components if needed
5. Submit to ComfyUI Manager
6. Document additional use cases

## Support & Contributing

For bugs, features, or questions:
- GitHub Issues: [yourusername/comfyui-model-compare/issues](https://github.com/yourusername/comfyui-model-compare/issues)
- Pull Requests: [yourusername/comfyui-model-compare/pulls](https://github.com/yourusername/comfyui-model-compare/pulls)

## License

MIT License - See LICENSE file for details
