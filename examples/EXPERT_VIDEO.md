# Expert: Video Generation - WAN 2.2 Comparison

Generate and compare video quality across models.

## Goal
Create video variations and compare WAN 2.1 vs WAN 2.2 quality and speed.

## Prerequisites
- ComfyUI with video model support 
- WAN 2.1 and WAN 2.2 models installed
- GPU with 12GB+ VRAM (video models are memory-intensive)

## Setup (15 minutes)

### Step 1: Load Video Models
```
Model 1: wan_21_model.safetensors   (WAN 2.1)
Model 2: wan_22_model.safetensors   (WAN 2.2)
```

### Step 2: Configure Video Sampling
Create two config chains:

**Chain 1 (WAN 2.1):**
```
config_type: WAN2.1
num_frames: 16              ← Generate 16 frames
width: 512
height: 512
steps: 30
cfg: 7.5
seed: 42
```

**Chain 2 (WAN 2.2):**
```
config_type: WAN2.2
num_frames: 16              ← Same frame count for fair comparison
width: 512
height: 512
steps: 30
cfg: 7.5
seed: 42                    ← Same seed for fair comparison!
```

### Step 3: Set Prompt
```
Positive: "A woman walking through a forest, cinematic, smooth motion"
Negative: "static camera, jittery motion, distorted"
```

### Step 4: Run
⚠️ **WARNING**: This will take 10-20 MINUTES per model!
- WAN 2.1: ~10 minutes
- WAN 2.2: ~15 minutes (higher quality, slower)

**Total: 25-35 minutes**

### Step 5: Watch Videos
ComfyUI will generate:
- `output/video_wan21_comparison.mp4` (WAN 2.1)
- `output/video_wan22_comparison.mp4` (WAN 2.2)

Use a video player to compare side-by-side.

## What to Look For

### Motion Quality
- Smoothness: Does motion feel natural or jittery?
- Consistency: Do objects deform or glitch mid-motion?
- Coherence: Does the woman stay in frame and maintain form?

### Visual Quality
- Details: Hair, clothing, features sharpness
- Colors: Consistency across frames
- Lighting: Smooth lighting transitions or flickering?

### Speed
- WAN 2.1: Usually 30-50% faster
- WAN 2.2: Slower but usually higher quality

## Expected Results

| Aspect | WAN 2.1 | WAN 2.2 |
|--------|---------|---------|
| Speed | ✅ Fast (10m) | ⚠️ Slow (15m) |
| Motion | ✅ Good | ✅✅ Better |
| Consistency | ✅ Decent | ✅✅ Excellent |
| Details | ⚠️ Medium | ✅ High |

## Analysis Questions
1. Is WAN 2.2's quality worth the 50% speed increase?
2. At what frame count do you get acceptable results?
3. For your use case, is WAN 2.1 "good enough"?

## Tips

### Tip 1: Start Small
Try 8-16 frames first. Only go to 32+ frames if you need longer videos.

### Tip 2: Use Same Seed
Set `seed: 42` in all chains so differences are pure model quality, not randomness.

### Tip 3: Lower Resolution First
512×512 trains in 10min. Save 1024×1024 for final renders (30+ min).

### Tip 4: Monitor GPU Temperature
Video models use high VRAM. Keep GPU below 80°C. 
Add delays between runs if GPU is thermal throttling.

## Checklist
- [ ] Both models installed
- [ ] Configs set identically (except model)
- [ ] Ran both (patience! ☕☕)
- [ ] Compared videos side-by-side
- [ ] Decided which is better for your needs

## Performance Optimization
If you need faster iterations:

**Reduce to 8 frames** (1-2 second video):
```
num_frames: 8  ← Much faster to generate
```

**Lower resolution**:
```
width: 384
height: 384  ← 30% faster than 512
```

**Fewer steps**:
```
steps: 20  ← Faster, lower quality
```

Example: 8 frames × 384×384 × 20 steps = ~5 minutes per model!

## Advanced: I2V (Image-to-Video)

Want to continue motion from a reference frame?

**Add start frame**:
```
# Reference image (e.g., screenshot)
start_frame: "path/to/first_frame.png"
```

This will:
1. Encode the reference frame
2. Predict motion continuation
3. Generate video starting from that frame

Great for extending partial videos or maintaining consistency!

## Next Steps
1. Compare WAN 2.2 with Hunyuan video (if available)
2. Test parameter variations (steps: 20, 30, 40)
3. Try different prompts to see consistency
4. Document fastest/best combinations for your workflow
