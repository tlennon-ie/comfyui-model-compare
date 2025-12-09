# Example Workflows

This directory contains practical workflow patterns for ComfyUI Model Compare.

## Quick Reference

### Example 1: Basic Model Comparison
**File:** `01_basic_model_comparison.md`  
**Use Case:** Compare 2-3 models with identical settings  
**Nodes:** 3 (Loaders → Sampler → Grid)  
**Complexity:** ⭐ Beginner

### Example 2: LoRA Strength Testing
**File:** `02_lora_strength_testing.md`  
**Use Case:** Find optimal LoRA strength (0.0 → 1.5)  
**Nodes:** 4 (LoRA Compare → Loaders → Sampler → Grid)  
**Complexity:** ⭐⭐ Intermediate

### Example 3: Multi-LoRA AND Logic
**File:** `03_multi_lora_and_logic.md`  
**Use Case:** Test LoRA A + LoRA B combinations  
**Nodes:** 4 (LoRA Compare → Loaders → Sampler → Grid)  
**Complexity:** ⭐⭐ Intermediate

### Example 4: Per-Model VAE Comparison
**File:** `04_per_model_vae_comparison.md`  
**Use Case:** Test different VAEs per model variation  
**Nodes:** 6 (VAE Config → Chains → Loaders → Sampler → Grid)  
**Complexity:** ⭐⭐⭐ Advanced

### Example 5: Cross-Architecture Comparison
**File:** `05_cross_architecture_comparison.md`  
**Use Case:** Compare FLUX vs QWEN vs SDXL directly  
**Nodes:** 6 (Loaders → Multiple Chains → Sampler → Grid)  
**Complexity:** ⭐⭐⭐ Advanced

### Example 6: Custom Grid Layout
**File:** `06_custom_grid_layout.md`  
**Use Case:** Control row/column hierarchy with styling  
**Nodes:** 6 (Formula + Format Config → Grid)  
**Complexity:** ⭐⭐⭐ Advanced

## How to Use

1. **Read the markdown file** for step-by-step setup instructions
2. **Build the workflow** in ComfyUI following the node connections
3. **Adjust parameters** to match your models/LoRAs/prompts
4. **Execute** and review the grid output

## Tips

- Start with Example 1 to understand the basic flow
- Examples 2-3 are great for LoRA testing
- Examples 4-5 show the power of config chains
- Example 6 demonstrates advanced grid customization

## Node Connection Pattern

All workflows follow this general pattern:

```
[Config Nodes] → Model Compare Loaders → [Optional Chains] → Sampler → Grid Compare → [Preview]
```

Where:
- **Config Nodes** = LoRA Compare, VAE Config, CLIP Config, Prompt Compare
- **Optional Chains** = Sampling Config Chain (per-variation settings)
- **Preview** = Video Preview (for video models)

## Need Help?

Check the main [README.md](../README.md) for:
- Complete node reference
- Workflow patterns section
- Troubleshooting guide
- Advanced features
