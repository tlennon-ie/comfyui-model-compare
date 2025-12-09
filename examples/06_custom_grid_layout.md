# Example 6: Custom Grid Layout with Styling

**Difficulty:** ⭐⭐⭐ Advanced  
**Use Case:** Control row/column hierarchy and visual styling  
**Expected Output:** Grid with custom organization and branding

## Goal

Override the automatic grid layout algorithm to force specific dimensions to rows/columns and apply custom visual styling.

## Workflow Structure

```
Grid Preset Formula ────┐
Grid Format Config ─────┼──→ Grid Compare
Model/Sampler ──────────┘
```

## When to Use Custom Layout

**Automatic layout works well for:**
- Simple comparisons (2-10 images)
- Standard LoRA strength testing
- Model comparisons

**Custom layout needed when:**
- You want specific field order (e.g., prompts as rows, models as columns)
- Automatic algorithm creates confusing hierarchy
- You need consistent layout across multiple grids
- Branding/styling requirements (colors, fonts)

---

## Step-by-Step Setup

### 1. Create Your Comparison (Standard Setup)

**Example:** 3 models × 2 prompts × 2 LoRA strengths = 12 images

**Setup:**
- Prompt Compare: 2 prompts
- LoRA Compare: 2 strengths
- Model Loaders: 3 models
- Sampler: Generate 12 images

---

### 2. Add Grid Preset Formula Node

**Location:** Right-click → Model Compare → Grid → Grid Preset Formula

**Purpose:** Analyze config and suggest/force optimal layout

**Settings:**
- `force_row_dimensions`: `prompt_positive, model` (comma-separated)
  - Forces these fields to rows in this order
  - Outer rows = first field, inner rows = last field
- `force_column_dimensions`: `lora_strength` (comma-separated)
  - Forces these fields to columns
- `pagination_fallback`: `model` (optional)
  - If >500 combos, paginate by this field

**Connections:**
- Connect `config` from Sampler → `config` input

**Output:** `grid_layout` (GRID_LAYOUT with row/col hierarchy)

**Result:**
```
grid_layout = {
  "row_dimensions": ["prompt_positive", "model"],
  "column_dimensions": ["lora_strength"]
}
```

---

### 3. Add Grid Format Config Node

**Location:** Right-click → Model Compare → Grid → Grid Format Config

**Purpose:** Visual styling separate from layout logic

**Settings:**

**Colors:**
- `color_palette`: `#2563eb, #7c3aed, #db2777, #ea580c, #ca8a04`
  - Comma-separated hex colors
  - Used for header depth levels (outer → inner)
  - First color = outermost container
- `use_depth_coloring`: `True`
  - Apply different colors per nesting level

**Typography:**
- `header_font_size`: `16` (outer header text)
- `label_font_size`: `12` (cell labels)

**Spacing:**
- `header_padding`: `12` (padding inside headers)
- `cell_padding`: `8` (padding around images)

**Borders:**
- `border_width`: `2`
- `border_color`: `#cbd5e1`

**Transparency:**
- `header_opacity`: `0.95` (0.0-1.0)

**Output:** `format_config` (GRID_FORMAT_CONFIG)

---

### 4. Update Grid Compare Node

**Existing Settings:** Keep your normal settings

**New Connections:**
- Connect `grid_layout` from Formula → `grid_layout` input on Grid Compare
- Connect `format_config` from Format Config → `format_config` input on Grid Compare

**Effect:** Grid uses custom layout and styling instead of automatic

---

## Expected Result

**Without Custom Layout (Automatic):**
```
Auto-detect varying dimensions
Apply priority weights
May create unexpected hierarchy
```

**With Custom Layout (Forced):**
```
Rows (outer → inner):
  1. prompt_positive (2 values)
  2. model (3 values)

Columns:
  1. lora_strength (2 values)

Visual:
             LoRA 0.5    LoRA 1.0
Prompt 1
  Model A    [Image]     [Image]
  Model B    [Image]     [Image]
  Model C    [Image]     [Image]

Prompt 2
  Model A    [Image]     [Image]
  Model B    [Image]     [Image]
  Model C    [Image]     [Image]
```

**Custom Colors:**
- Prompt headers: Blue (#2563eb)
- Model headers: Purple (#7c3aed)
- Clear visual hierarchy

---

## Understanding force_row_dimensions

**Order Matters:**

```python
force_row_dimensions: "model, prompt_positive"
→ Outer: model, Inner: prompt_positive

force_row_dimensions: "prompt_positive, model"
→ Outer: prompt_positive, Inner: model
```

**Visual Difference:**

**Option 1 (model outer):**
```
Model A
  Prompt 1: [Images]
  Prompt 2: [Images]
Model B
  Prompt 1: [Images]
  Prompt 2: [Images]
```

**Option 2 (prompt outer):**
```
Prompt 1
  Model A: [Images]
  Model B: [Images]
Prompt 2
  Model A: [Images]
  Model B: [Images]
```

---

## Color Palette Examples

### Professional (Blues)
```
color_palette: "#1e40af, #3b82f6, #60a5fa, #93c5fd, #dbeafe"
```

### Vibrant (Rainbow)
```
color_palette: "#dc2626, #ea580c, #ca8a04, #16a34a, #2563eb, #9333ea"
```

### Monochrome (Grays)
```
color_palette: "#111827, #374151, #6b7280, #9ca3af, #d1d5db"
```

### Dark Theme
```
color_palette: "#1e293b, #334155, #475569, #64748b, #94a3b8"
border_color: "#475569"
```

---

## Advanced Customization

### Three-Level Nesting

**Force 3 dimensions to rows:**
```
force_row_dimensions: "sampler_name, model, prompt_positive"
```

**Result:**
- Outer: sampler_name
- Middle: model
- Inner: prompt_positive

**Use Case:** Testing samplers across models and prompts

### Lock One Dimension, Auto-Detect Rest

**Only force columns:**
```
force_column_dimensions: "lora_strength"
force_row_dimensions: (empty)
```

**Effect:**
- Columns: lora_strength (forced)
- Rows: Auto-detect from remaining dimensions

### Pagination for Large Grids

**500+ combinations:**
```
pagination_fallback: "model"
```

**Effect:**
- Creates multiple grid files
- One file per model
- Prevents single massive grid

---

## Grid Preview Before Sampling

**Use Grid Preview node to verify layout:**

1. Add **Grid Preview** node
2. Connect `config` from chains/loaders
3. Connect `grid_layout` from Formula
4. Execute preview only

**Result:** Numbered placeholder grid showing exact structure

**Benefits:**
- See layout without expensive sampling
- Verify row/col assignment
- Adjust Formula before committing

---

## Common Layout Patterns

### Pattern A: Prompts × Models
```
force_row_dimensions: "prompt_positive"
force_column_dimensions: "model"
```
Use when: Comparing how models interpret different prompts

### Pattern B: LoRA Strength Progression
```
force_row_dimensions: "model, lora_name"
force_column_dimensions: "lora_strength"
```
Use when: Standard LoRA testing (strength left→right)

### Pattern C: Sampler Matrix
```
force_row_dimensions: "sampler_name"
force_column_dimensions: "scheduler"
```
Use when: Testing sampler/scheduler combinations

### Pattern D: Resolution Tests
```
force_row_dimensions: "model"
force_column_dimensions: "width"
```
Use when: Testing multiple resolutions per model

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Formula ignored | Check connections: Formula → Grid Compare `grid_layout` input |
| Wrong dimensions in formula | Field names must match exactly (case-sensitive) |
| Colors not applying | Verify `format_config` connected to Grid Compare |
| Too many nesting levels | Reduce dimensions in `force_row_dimensions` |
| Pagination not working | Check combination count >500, verify `pagination_fallback` field exists |
| Grid still looks auto | Disconnect `grid_layout` input to revert to automatic |

---

## Comparison: Auto vs Custom

**Automatic (No Formula):**
- ✅ Quick setup
- ✅ Generally good results
- ❌ Unpredictable for complex grids
- ❌ Can't force specific organization

**Custom (With Formula):**
- ✅ Full control over hierarchy
- ✅ Consistent across multiple grids
- ✅ Custom branding/colors
- ❌ Requires understanding of dimensions
- ❌ More nodes to configure

---

## Next Steps

- **Export Customization:** HTML grids can be re-edited in Grid Builder web interface
- **Theme Variants:** Create multiple Format Config nodes for different styles
- **Template Reuse:** Save Formula settings for common patterns
