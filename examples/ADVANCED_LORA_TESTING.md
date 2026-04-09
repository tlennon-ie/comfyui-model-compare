# Advanced: Multi-Model + LoRA Testing

Compare multiple models while testing different LoRA strengths.

## Goal
Determine which model works best with your favorite LoRA.

## Scenario
"I have a character LoRA. Does it work better on SDXL or FLUX? Should I use 0.7x or 1.0x strength?"

## Setup (15 minutes)

### Step 1: Load 2-3 Models
```
Model 1: sd_xl_base_1.0.safetensors     (SDXL)
Model 2: flux_dev.safetensors             (FLUX)
Model 3: piflow_model.safetensors         (piFlow, faster alternative)
```

### Step 2: Add LoRA Configuration
Use **LoRA Compare** node to load your LoRA:
- LoRA file: `character_v1.safetensors`
- LoRA label: `MyCharacter`

### Step 3: Add Sampling Chains
Create ONE config chain, but set it with LoRA strength VARIATIONS:

```
Chain 1:
  config_type: SDXL
  Steps: 30
  CFG: 7.5
  LoRA: MyCharacter [0.5, 0.7, 1.0]   ← Tests 3 strengths

Chain 2:
  config_type: FLUX
  Steps: 30
  CFG: 7.5
  LoRA: MyCharacter [0.5, 0.7, 1.0]

Chain 3:
  config_type: PIFLOW
  Steps: 30
  CFG: 7.5
  LoRA: MyCharacter [0.5, 0.7, 1.0]
```

### Step 4: Set Prompt
```
Positive: "MyCharacter, portrait, detailed face, professional lighting"
Negative: "ugly, distorted face"
```

### Step 5: Run
Queue workflow.

## Expected Output
**3 models × 3 LoRA strengths = 9 images**

Grid layout:
```
         0.5x Strength    0.7x Strength    1.0x Strength
SDXL     [weak LoRA]      [medium LoRA]    [strong LoRA]
FLUX     [weak LoRA]      [medium LoRA]    [strong LoRA]
piFlow   [weak LoRA]      [medium LoRA]    [strong LoRA]
```

## Analysis
Look at the results and ask:
1. **By Column (LoRA strength)**: 
   - Does 0.5x lose character detail?
   - Does 1.0x overdrive the style?
   - Where's the sweet spot?

2. **By Row (Model comparison)**:
   - Which model best preserves the character?
   - Which produces the most natural results?
   - Are there significant quality differences?

3. **Combinations**:
   - Best pairing: Which model × strength looks best?
   - Fastest result: Which model is quickest (for iteration)?
   - Most reliable: Which doesn't have artifacts?

## Real Example Analysis
If you see:
- SDXL 0.7x looks best overall
- → Use that for your character generation going forward

If you see:
- FLUX 1.0x + LoRA sometimes distorts
- FLUX 0.7x is better
- → Adjust your LoRA strength

If you see:
- piFlow matches FLUX quality at 60% speed
- → Use piFlow for quick iteration, FLUX for final renders

## Checklist
- [ ] Loaded 2-3 models
- [ ] Added LoRA with 3 strength values
- [ ] Got ~9 images total
- [ ] Identified best model/LoRA combo
- [ ] Documented your findings

## Performance Estimate
- 9 combinations × 30 steps = 270 step calculations
- Time: 15-25 minutes depending on models
- This is WORTH IT if you'll use this LoRA frequently!

## Tips

### Tip 1: Run This Once Per New LoRA
Document results in a notepad:
```
MyCharacter LoRA:
- Best Model: FLUX
- Best Strength: 0.7
- Recommended CFG: 7.5
- Recommended Steps: 30
```

### Tip 2: Keep It Simple First
Start with 2 models, 3 strengths (6 images).
Add complexity later.

### Tip 3: Try Different Prompts
Results can vary. The above tests ONE prompt.
Try different character prompts to validate consistency.

### Tip 4: Consider Speed vs Quality
If piFlow does 70% quality at 50% time = Good choice for exploration
Save FLUX for final renders

## Next Steps
Advanced options:
1. Add scheduler variations: `normal, karras`
2. Test with different character prompts  
3. Create a LoRA strength guide for your library
4. Share results with LoRA creator for feedback
