# LoRA Patches in ComfyUI - Complete Documentation Index

## 📋 Documentation Overview

This documentation set explains **exactly how LoRA patches are applied during sampling in ComfyUI** and how to verify they're working in your custom sampler code.

### Start Here

**New to this issue?** Start with one of these:
1. **[LORA_SUMMARY.md](LORA_SUMMARY.md)** - 5-minute overview (TL;DR version)
2. **[LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md)** - Troubleshooting & debugging

### Deep Dives

Need detailed technical understanding?
1. **[LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md)** - Complete technical analysis (25 pages)
2. **[LORA_CALL_STACK.md](LORA_CALL_STACK.md)** - Code flow from loading to application
3. **[LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md)** - Practical code examples

---

## 🎯 Quick Answers

### "When are LoRA patches actually applied?"
→ During `comfy.sample.sample()`, inside the `prepare_sampling()` function, which calls `load_models_gpu()` → `model.load()` → `patch_weight_to_device()`.

**Reference:** [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Complete Call Stack section

### "Are LoRA patches activated automatically?"
→ Yes, automatically when you call `comfy.sample.sample()`. No special setup needed.

**Reference:** [LORA_SUMMARY.md](LORA_SUMMARY.md) - The Bottom Line

### "How do I check if LoRA was applied?"
→ Check if `model.backup` has entries after sampling. If empty, patches weren't applied.

**Reference:** [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Snippet 2

### "Where are the patches stored?"
→ In `ModelPatcher.patches` dictionary with keys like `"diffusion_model.input_blocks.0.0.weight"`

**Reference:** [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) - Where Patches Are Stored

### "What's the difference between patches and backup?"
→ **Patches:** Stored data about LoRA modifications (dictionary)
→ **Backup:** Original weight tensors saved when patches are applied (dict)

**Reference:** [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Key Data Structures

---

## 📚 Document Descriptions

### LORA_SUMMARY.md
**Purpose:** Quick reference and executive summary
**Length:** ~400 lines
**Best for:** Understanding the big picture
**Key sections:**
- The Bottom Line (TL;DR)
- Three Key Facts
- What Happens at Each Stage
- Most Common Mistake
- Your Code Review

### LORA_PATCH_ANALYSIS.md
**Purpose:** Complete technical deep dive
**Length:** ~600 lines
**Best for:** Understanding every detail
**Key sections:**
- How LoRA Patches Work
- Patch Activation During Sampling
- Critical Sequence (7-step process)
- Verification methods
- Most Important: Where patches actually get applied
- Comparison: your code vs ComfyUI default

### LORA_CALL_STACK.md
**Purpose:** Code reference with complete call chain
**Length:** ~500 lines
**Best for:** Tracing execution flow
**Key sections:**
- Complete Call Stack (visual flow)
- Key Data Structures
- Critical State Transitions
- Troubleshooting by Layer
- Complete Example: Tracing a Single Weight

### LORA_DIAGNOSTIC_GUIDE.md
**Purpose:** Troubleshooting and verification
**Length:** ~400 lines
**Best for:** Debugging LoRA issues
**Key sections:**
- Quick Diagnosis (verification code)
- Common Issues & Solutions
- Advanced verification approaches
- Test code snippets
- Expected output indicators

### LORA_CODE_SNIPPETS.md
**Purpose:** Ready-to-use code examples
**Length:** ~600 lines
**Best for:** Copy-paste implementations
**Contains:**
- 8 complete code snippets
- Debug utility class
- Model manager helper
- Error handling templates
- Quick reference functions

---

## 🔍 How to Use This Documentation

### Use Case 1: "LoRA isn't working - how do I fix it?"

1. Start with [LORA_SUMMARY.md](LORA_SUMMARY.md) - Verification Checklist
2. Go to [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Snippet 1 & 2
3. Run diagnostic code to identify the issue
4. Find your issue in [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Common Issues section
5. Copy solution from [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) if needed

### Use Case 2: "I want to understand how patches work"

1. Read [LORA_SUMMARY.md](LORA_SUMMARY.md) - Three Key Facts
2. Read [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) - How LoRA Patches Work
3. Study [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Complete Call Stack
4. Review [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) - Snippet 3 (Complete Example)

### Use Case 3: "I'm implementing a custom sampler"

1. Review [LORA_SUMMARY.md](LORA_SUMMARY.md) - Most Common Mistake
2. Check [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) - Default Samplers vs Custom
3. Use code from [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) - Snippet 3, 4, 5
4. Verify with [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Complete Test

### Use Case 4: "I'm debugging multiple LoRAs"

1. Review [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) - Snippet 4
2. Use [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) - Snippet 5 (Debug class)
3. Check [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Issue #4

---

## 🎓 Learning Path

### Level 1: Beginner (5 minutes)
- [LORA_SUMMARY.md](LORA_SUMMARY.md) - The Bottom Line
- [LORA_SUMMARY.md](LORA_SUMMARY.md) - Three Key Facts
- [LORA_SUMMARY.md](LORA_SUMMARY.md) - Most Common Mistake

### Level 2: Intermediate (30 minutes)
- [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) - How LoRA Patches Work
- [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) - Critical Sequence
- [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Snippet 2 (Verification)

### Level 3: Advanced (1 hour)
- [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Complete Call Stack
- [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Key Data Structures
- [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) - All snippets

---

## 🔑 Key Concepts

### Patches Dictionary
**What:** `ModelPatcher.patches` dictionary
**Contains:** LoRA weight data keyed by model weight names
**When populated:** After `load_lora_for_models()` call
**Example key:** `"diffusion_model.input_blocks.0.0.weight"`
**Reference:** [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Key Data Structures

### Backup Dictionary
**What:** `ModelPatcher.backup` dictionary
**Contains:** Original weight tensors (created when patches applied)
**When populated:** During `patch_weight_to_device()` in `prepare_sampling()`
**Indicator:** If empty after sampling, patches were NOT applied
**Reference:** [LORA_CALL_STACK.md](LORA_CALL_STACK.md) - Critical State Transitions

### CFGGuider
**What:** Wrapper around ModelPatcher
**Does:** Triggers `prepare_sampling()` which applies patches
**Why important:** Only path that guarantees patch application
**Reference:** [LORA_SUMMARY.md](LORA_SUMMARY.md) - Most Common Mistake

### prepare_sampling()
**What:** Function that loads models and applies patches
**Located:** `comfy/sampler_helpers.py`
**Calls:** `load_models_gpu()` which eventually calls `patch_weight_to_device()`
**Key:** Where patch application actually happens
**Reference:** [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) - Critical Sequence

---

## ❌ Common Pitfalls

### Pitfall 1: Using wrong sampling function
**Wrong:** `comfy.samplers.sample(model, ...)`
**Right:** `comfy.sample.sample(model, ...)`
**Why:** Only `comfy.sample.sample()` wraps in CFGGuider
**Fix:** [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Issue #1

### Pitfall 2: Checking backup before sampling
**Wrong:** Check `model.backup` right after `load_lora_for_models()`
**Right:** Check `model.backup` AFTER `comfy.sample.sample()` completes
**Why:** Backup only created during patch application in sampling
**Fix:** [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Snippet 1

### Pitfall 3: LoRA strength of 0
**Wrong:** `load_lora_for_models(model, clip, lora_data, 0, 0)`
**Right:** Use strength > 0, typically 0.5 to 1.5
**Why:** Strength 0 means no effect
**Fix:** [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) - Issue #2B

### Pitfall 4: Assuming patches are applied immediately
**Wrong:** Check if model weights changed right after `load_lora_for_models()`
**Right:** Weights only change after `prepare_sampling()` during sampling
**Why:** Loading only stores patches, doesn't apply them
**Fix:** [LORA_SUMMARY.md](LORA_SUMMARY.md) - What Happens at Each Stage

---

## 🧪 Testing & Verification

### Minimal Test (Snippet 1 in LORA_CODE_SNIPPETS.md)
Verifies if LoRA was loaded into patches dictionary

### Complete Test (Snippet 3 in LORA_CODE_SNIPPETS.md)
Verifies entire pipeline from loading to sampling

### Debug Tool (Snippet 5 in LORA_CODE_SNIPPETS.md)
Provides detailed verification of all stages

---

## 📊 File Structure

```
Your Custom Node
├── sampler_specialized.py (your code)
├── LORA_SUMMARY.md ← Start here
├── LORA_PATCH_ANALYSIS.md ← Deep dive
├── LORA_CALL_STACK.md ← Code reference
├── LORA_DIAGNOSTIC_GUIDE.md ← Troubleshooting
├── LORA_CODE_SNIPPETS.md ← Code examples
└── README.md (this file)
```

---

## 🔗 Cross-References

| Question | Document | Section |
|----------|----------|---------|
| How patches work | [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) | How LoRA Patches Work |
| When patches applied | [LORA_CALL_STACK.md](LORA_CALL_STACK.md) | Complete Call Stack |
| How to debug | [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) | Snippet 1-2 |
| Code examples | [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md) | All snippets |
| Quick overview | [LORA_SUMMARY.md](LORA_SUMMARY.md) | The Bottom Line |
| Common mistakes | [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) | Common Issues |
| Data structures | [LORA_CALL_STACK.md](LORA_CALL_STACK.md) | Key Data Structures |
| State transitions | [LORA_CALL_STACK.md](LORA_CALL_STACK.md) | Critical State Transitions |

---

## ✅ Your Code Review

Your implementation in `sampler_specialized.py` (line 190+) is **correct**:

```python
combo_model, _ = comfy.sd.load_lora_for_models(combo_model, None, lora_data, lora_strength, 0)
# ✓ Loads LoRA into patches dictionary

samples_out = comfy.sample.sample(combo_model, noise, ...)
# ✓ Triggers CFGGuider → prepare_sampling() → patch application
```

If LoRAs aren't showing visual effect, use [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) to debug.

---

## 📝 Notes

- All line numbers reference the ComfyUI codebase as of the analysis date
- All code samples are compatible with your custom node implementation
- All documentation assumes standard PyTorch/CUDA setup

---

## 🚀 Quick Start

1. **Problem:** LoRA not working
   → Go to [LORA_DIAGNOSTIC_GUIDE.md](LORA_DIAGNOSTIC_GUIDE.md) Snippet 1

2. **Question:** How patches work
   → Read [LORA_SUMMARY.md](LORA_SUMMARY.md) Three Key Facts

3. **Want:** Code examples
   → Copy from [LORA_CODE_SNIPPETS.md](LORA_CODE_SNIPPETS.md)

4. **Need:** Full understanding
   → Read [LORA_PATCH_ANALYSIS.md](LORA_PATCH_ANALYSIS.md) in order

---

**Total documentation:** ~2,500 lines of analysis and examples
**Scope:** Complete understanding of LoRA patch application in ComfyUI
**Target:** Your custom model comparison sampler

