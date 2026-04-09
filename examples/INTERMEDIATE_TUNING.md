# Intermediate: Parameter Tuning - Find Best Settings

This workflow helps you find the optimal sampling parameters for your favorite model.

## Goal
Test different step counts, CFG scales, and samplers on ONE model to find the best combination.

## Concept
Instead of changing parameters and running separately, compare all variations at once!

## Setup (10 minutes)

### Step 1: Load Your Favorite Model
Add model loader with just ONE model (your go-to model)

### Step 2: Configure Variations
Add **SamplingConfigChain** and set:

```
config_type: FLUX (or your model type)
steps: 15, 20, 30, 40          ← Will test 4 different step counts
cfg: 5.0, 7.0, 10.0             ← Will test 3 different guidance scales  
sampler_name: euler             ← Using single sampler (euler)
scheduler: normal
```

### Step 3: Connect to Sampler Node
1. Add **SamplerCompareAdvanced**
2. Connect your model and config chain
3. Set prompt: `"a beautiful landscape, 8k quality"`

### Step 4: Run
Queue the workflow.

## Expected Output
**4 × 3 = 12 images** showing how parameters affect output:
- Rows: Different step counts (15, 20, 30, 40)
- Columns: Different CFG scales (5.0, 7.0, 10.0)

## Example Results
From left to right (increasing CFG):
- Column 1 (CFG 5.0): Dreamy, loose interpretation
- Column 2 (CFG 7.0): Balanced, follows prompt
- Column 3 (CFG 10.0): Strict, sometimes too literal

From top to bottom (increasing steps):
- Row 1 (15 steps): Fast, slight artifacts
- Row 2 (20 steps): Good balance
- Row 3 (30 steps): High detail
- Row 4 (40 steps): Maximum detail (slowest)

## Analysis
Ask yourself:
- Does more steps always look better? (Often no, diminishing returns)
- What CFG makes the prompt most recognizable?
- Is the added time worth the quality improvement?

## Checklist
- [ ] Configured 4 step values
- [ ] Configured 3 CFG values
- [ ] Got 12 images total
- [ ] Can see the parameter effects
- [ ] Found your preferred combination

## Next Steps
Once you find your optimal settings:
1. Write them down: "Steps 20, CFG 7.0, Euler" = My sweet spot
2. Use those settings for production runs
3. Try **Advanced: Compare Models** with these settings to be fair across models

## Performance Estimate
- 12 combinations × 20 steps avg = 240 total step computations
- ~20-30 minutes depending on GPU
- Budget: Grab coffee! ☕
