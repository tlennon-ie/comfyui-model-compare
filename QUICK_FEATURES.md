# Quick Start: New Features

## 🎯 What's New

Three powerful features added to Model Compare node:

1. **Custom LoRA Labels** - Give your LoRAs friendly display names
2. **AND/OR Operators** - Control how LoRAs combine (parallel vs sequential)
3. **Debug Toggle** - Clean vs verbose console output

---

## ⚡ 30-Second Setup

### Feature 1: Custom Labels (Optional)

Find in **Model Compare Loaders** node:
```
lora_0_customlabel: (empty or type custom name)
```

**Example:**
- Leave empty → Shows filename "Lightning_LoRA_v1.5.safetensors"
- Type "Speed" → Shows as "Speed(0.0)", "Speed(1.0)"

### Feature 2: AND/OR Combiner (Default: AND)

Find in **Model Compare Loaders** node:
```
lora_0_combiner: AND
lora_1_combiner: OR
lora_2_combiner: OR
```

**What it means:**
- **AND** - Always include this LoRA with all others
- **OR** - Test this LoRA separately from others

**Your case:**
```
Lightning LoRA:    AND  ← Always active
Skin LoRA 1:       OR   ← Test separately
Skin LoRA 2:       OR   ← Test separately
Skin LoRA 3:       OR   ← Test separately

Result: 9 images (Lightning + each skin at 3 strengths each)
Instead of: 27 images (all combinations)
```

### Feature 3: Debug Log Toggle

Find in **Model Compare Loaders** node:
```
debug_log: OFF (or ON)
```

**Clean mode (OFF):**
```
[ModelCompareLoaders] Will generate 9 images
[SamplerCompareCheckpoint] Generating image 1/9
[GridCompare] Grid saved to: /output
```

**Debug mode (ON):**
```
[ModelCompareLoaders] Loading base model: flux-dev
[ModelCompareLoaders] Config created:
  - Model variations: 1
  - VAE variations: 1
  - LoRAs: 2
... detailed info for each step ...
```

---

## 📋 Common Setups

### Setup 1: Simple Comparison (Recommended for Your Use Case)

```
lora_0: Lightning_LoRA.safetensors
  strengths: 1.0
  customlabel: Lightning
  combiner: AND

lora_1: Skin_Texture_A.safetensors
  strengths: 0.0, 0.5, 1.0
  customlabel: TextureA
  combiner: OR

lora_2: Skin_Texture_B.safetensors
  strengths: 0.0, 0.5, 1.0
  customlabel: TextureB
  combiner: OR

lora_3: Skin_Texture_C.safetensors
  strengths: 0.0, 0.5, 1.0
  customlabel: TextureC
  combiner: OR

debug_log: OFF
```

**Result:** 9 images showing Lightning + each texture at 3 strength levels

### Setup 2: Testing All Combinations (Old Behavior)

```
(All combiners set to AND)
debug_log: OFF
```

**Result:** Tests every combination of all LoRAs at every strength

### Setup 3: Debugging

Change any time to:
```
debug_log: ON
```

Gives full console output for troubleshooting.

---

## 🎨 Label Examples

### Without Custom Labels
```
Grid shows: "Lightning_LoRA_v1.5.safetensors(1.0) + Skin_Texture_A_v2.safetensors(0.5)"
```

### With Custom Labels
```
Grid shows: "Lightning(1.0) + TextureA(0.5)"
```

Much cleaner!

---

## 🔄 AND/OR Decision Guide

| LoRA Type | Best Operator | Reason |
|-----------|---------------|--------|
| Base effect (Lightning, Detail) | AND | Always apply this base |
| Test variants (multiple skins) | OR | Test each separately |
| Style modifier | AND | Applies to all |
| Strength variant | OR | Test one variant at a time |

**Simple rule:** If you're comparing 3 different skin LoRAs, use OR. If you have a lightning effect that should always be on, use AND.

---

## ✅ Testing Checklist

- [ ] Add custom label to lightning LoRA
- [ ] Set lightning LoRA to AND
- [ ] Set other skin LoRAs to OR
- [ ] Set debug_log to OFF for clean output
- [ ] Run workflow
- [ ] Check grid labels are clean and custom
- [ ] Verify 9 images (not 27)
- [ ] Turn on debug_log if images don't look different

---

## 🆘 Troubleshooting

**Q: Images still look identical?**
- A: Probably LoRA patch issue (existed before these features)
- Solution: Set debug_log to ON and check console

**Q: Getting too many images?**
- A: Check your OR operators - maybe set to AND instead
- Solution: Review which LoRAs should be tested together

**Q: Labels show filename instead of custom label?**
- A: Custom label field is empty
- Solution: Type a custom label in the field

**Q: Console too verbose?**
- A: debug_log is ON
- Solution: Set to OFF

---

## 🚀 You're Ready!

All three features work together. Update your loader node with:

1. Custom labels for each LoRA ✓
2. AND for base effects, OR for variants ✓
3. Debug OFF for clean output ✓

Then run your workflow with cleaner labels and smarter LoRA combinations!

---

## 📖 Full Documentation

For detailed explanations, examples, and advanced usage:
→ Read **FEATURES_UPDATE.md**

This quick start just covers the essentials to get you going fast.
