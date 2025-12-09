# Example 3: Multi-LoRA AND Logic

**Difficulty:** ⭐⭐ Intermediate  
**Use Case:** Test combinations of LoRA A + LoRA B together  
**Expected Output:** Grid showing all combined strength permutations

## Goal

Test how two (or more) LoRAs interact when applied together using AND logic (`+` combinator).

## Workflow Structure

```
LoRA Compare → Model Compare Loaders → Sampler Compare Advanced → Grid Compare
```

## AND vs OR Logic

**AND (`+` combinator):** Combine LoRAs together
- LoRA A @ 0.5 **+** LoRA B @ 0.5
- LoRA A @ 0.5 **+** LoRA B @ 1.0
- LoRA A @ 1.0 **+** LoRA B @ 0.5
- LoRA A @ 1.0 **+** LoRA B @ 1.0
- **Result:** 4 combinations (Cartesian product)

**OR (` ` space combinator):** Test LoRAs separately
- LoRA A @ 0.5
- LoRA A @ 1.0
- LoRA B @ 0.5
- LoRA B @ 1.0
- **Result:** 4 separate tests

---

## Step-by-Step Setup (AND Logic)

### 1. Add LoRA Compare Node

**Location:** Right-click → Model Compare → Loaders → LoRA Compare

**Settings:**
- `num_loras`: `2` (or more for complex combinations)
- `pair_mode`: `SINGLE`

**LoRA A:**
- `lora_0`: Select first LoRA (e.g., style LoRA)
- `lora_0_strengths`: `0.5, 1.0`
- `lora_0_label`: `StyleLoRA`
- `lora_0_combinator`: `+` (**AND - this is key!**)

**LoRA B:**
- `lora_1`: Select second LoRA (e.g., character LoRA)
- `lora_1_strengths`: `0.5, 1.0`
- `lora_1_label`: `CharacterLoRA`
- `lora_1_combinator`: Leave empty (last LoRA doesn't need combinator)

**Output:** `lora_config` with 2×2=4 combinations

---

### 2. Add Model Compare Loaders Node

**Settings:**
- `preset`: `FLUX` (or your model architecture)
- `num_diffusion_models`: `1`
- `diffusion_model`: Select model

**Connections:**
- Connect `lora_config` from LoRA Compare → `lora_variation_0`

---

### 3. Add Sampler Compare Advanced Node

**Settings:**
- `seed`: `12345`
- `seed_mode`: `fixed` (important - shows interaction clearly)
- `steps`: `20`
- `cfg`: `3.5`
- `sampler_name`: `euler`

**Connections:**
- Connect `config` from Loaders → `config`

**Note:** Generates 4 images (2 strengths × 2 strengths)

---

### 4. Add Grid Compare Node

**Settings:**
- `output_folder`: `lora_combinations`
- `output_filename`: `style_character_combination`
- `cell_size`: `512`

**Connections:**
- Connect `images` and `config` from Sampler

---

## Expected Result

**Grid Layout:**
- **Columns:** Inner LoRA strength (LoRA B - CharacterLoRA)
  - 0.5, 1.0
- **Rows:** Outer LoRA strength (LoRA A - StyleLoRA)
  - 0.5, 1.0

**Visual Matrix:**
```
                CharacterLoRA 0.5    CharacterLoRA 1.0
StyleLoRA 0.5   [Image]               [Image]
StyleLoRA 1.0   [Image]               [Image]
```

**Labels:**
- Cell format: `StyleLoRA 0.5 + CharacterLoRA 0.5`
- Shows both LoRAs in each label

---

## Three LoRA Example

For even more complex testing:

**Settings:**
```
num_loras: 3

lora_0: Base style LoRA
lora_0_strengths: "0.5, 1.0"
lora_0_combinator: "+"

lora_1: Character LoRA
lora_1_strengths: "0.5, 1.0"
lora_1_combinator: "+"

lora_2: Lighting LoRA
lora_2_strengths: "0.5, 1.0"
lora_2_combinator: (empty)
```

**Result:** 2×2×2 = 8 combinations

**Grid Layout:**
- **Nested structure** with 3 levels
- Innermost: Lighting LoRA strength
- Middle: Character LoRA strength
- Outermost: Base style LoRA strength

---

## Variations

### Asymmetric Strengths

Test LoRA A heavily, LoRA B lightly:
```
lora_0_strengths: "0.3, 0.5, 0.7, 1.0"
lora_1_strengths: "0.2, 0.3"
```
Result: 4×2 = 8 combinations

### Fixed Base + Variable Test

Keep one LoRA constant, vary the other:
```
lora_0_strengths: "1.0" (single value - constant)
lora_0_combinator: "+"
lora_1_strengths: "0.0, 0.3, 0.5, 0.7, 1.0"
```
Result: 5 combinations showing how LoRA B affects the base (LoRA A @ 1.0)

### Compare AND vs OR in Same Workflow

**Not possible in single node**, but you can:
1. Create workflow with AND logic → Save grid as `combination_test.png`
2. Change combinator from `+` to ` ` (space)
3. Execute again → Save as `separate_test.png`
4. Compare both grids manually

---

## Understanding the Grid Layout

The **Grid Preset Formula** automatically decides hierarchy:

**Priority Algorithm:**
1. **lora_strength** always innermost columns (shows progression)
2. **lora_name** (with OR) always rows (categorical grouping)
3. With AND logic, creates nested structure based on combination count

**4 Combinations (2×2):**
- Simple 2×2 grid
- Rows: First LoRA strength
- Columns: Second LoRA strength

**8+ Combinations:**
- May create nested grid with depth levels
- Use Grid Preset Formula to customize

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Only 2 images instead of 4 | Check `lora_0_combinator: +` (not space) |
| LoRAs not combining | Verify both LoRAs are compatible with model |
| Grid layout confusing | Use Grid Preview node to verify structure first |
| Too many combinations | Reduce strength values (e.g., 2 values each instead of 4) |

---

## Performance Considerations

**Combination Count:**
- 2 LoRAs × 2 strengths each = 4 images ✅ Fast
- 2 LoRAs × 4 strengths each = 16 images ⚠️ Moderate
- 3 LoRAs × 3 strengths each = 27 images ⏰ Slow
- 4 LoRAs × 3 strengths each = 81 images ❌ Very slow

**Tips:**
1. Start with 2 values per LoRA for quick testing
2. Use Grid Preview node to verify layout before sampling
3. For many LoRAs, test pairs first, then combine winners

---

## Next Steps

- **OR Logic:** See Example 3 variation or create separate workflow
- **Per-Model LoRA Chains:** Apply different LoRA combinations per model (Advanced)
- **Custom Layout:** Use Grid Preset Formula to force specific hierarchy (Example 6)
