# ComfyUI Model Compare

A comprehensive custom node package for ComfyUI that enables side-by-side comparison of different models, VAEs, CLIPs, LoRAs, and prompts with intelligent grid generation.

## Features

- 🔄 **Multi-Model Comparison**: Compare FLUX, FLUX2, SDXL, WAN 2.1/2.2, Hunyuan 1.0/1.5, QWEN, Lumina2 models side-by-side
- ⚡ **Lazy Loading**: Models load on-demand per combination, minimizing VRAM usage
- 📊 **LoRA Testing**: Test multiple LoRAs at different strength values with AND/OR logic
- 🎨 **VAE/CLIP Variations**: Compare different VAE and CLIP configurations per model
- 📝 **Prompt Comparison**: Test multiple prompts with cross-product or paired modes
- ⚙️ **Config Chains**: Fine-tune sampling parameters per model variation with chainable nodes
- 🖼️ **Smart Grid Layouts**: Automatic hierarchical grid generation with customizable presets
- 🌐 **Web Gallery**: Browse and filter all generated grids via web interface
- ✏️ **Grid Builder**: Interactive drag-and-drop editor to reconfigure existing grids
- 🎥 **Video Support**: Generate MP4/GIF/WebM grids for video models
- 📤 **Multi-Format Export**: HTML (interactive), PNG, JSON, CSV, PDF formats
- 📈 **Histogram Analysis**: Analyze and compare image histograms
- 📊 **Progress Tracking**: Real-time monitoring with VRAM usage and ETA display

## Installation

### ComfyUI Manager (Recommended)
1. Open ComfyUI Manager
2. Search for "Model Compare"
3. Click Install

### Manual Installation
```bash
cd ComfyUI/custom_nodes/
git clone https://github.com/tlennon-ie/comfyui-model-compare.git
pip install -r comfyui-model-compare/requirements.txt
```

## Quick Start

**Simplest workflow (3 nodes):**

```
Model Compare Loaders → Sampler Compare Advanced → Grid Compare
```

1. Add **Model Compare Loaders** node
   - Set `preset` to your model architecture (FLUX, SDXL, etc.)
   - Select 2+ models to compare in `diffusion_model` and `diffusion_model_variation_1`
   
2. Add **Sampler Compare Advanced** node
   - Connect `config` output from Loaders to `config` input
   - Set sampling parameters (steps, cfg, seed)
   
3. Add **Grid Compare** node
   - Connect `images` and `config` from Sampler
   - Set output folder and filename
   - Execute workflow

**Result:** A labeled comparison grid showing both models' outputs side-by-side.

## Core Concepts

### Configuration Passing (Not Model Loading)

Unlike traditional nodes, **Model Compare Loaders** doesn't load models immediately. Instead, it builds a **configuration object** describing all combinations to test. Models are loaded lazily by **Sampler Compare Advanced** only when needed.

**Benefits:**
- Minimal VRAM usage (only 1 model loaded at a time)
- Fast workflow setup
- Easy to add/remove variations

### Config Chains (Per-Variation Settings)

Use **Sampling Config Chain** nodes to customize settings per model variation:

```
Model Compare Loaders → Chain (var 0) → Chain (var 1) → Sampler
```

Each chain node specifies which `variation_index` it configures, allowing different sampling parameters, dimensions, or model-specific settings per model.

### Custom Data Types

- **MODEL_COMPARE_CONFIG**: Master configuration with all combinations
- **LORA_COMPARE_CONFIG**: LoRA configurations with AND/OR logic
- **VAE_COMPARE_CONFIG**: VAE variations per chain
- **CLIP_COMPARE_CONFIG**: CLIP variations (single or dual CLIP)
- **PROMPT_COMPARE_CONFIG**: Prompt variations with pairing modes
- **GRID_LAYOUT**: Row/column hierarchy for rendering
- **GRID_FORMAT_CONFIG**: Visual styling configuration
- **VIDEO_GRID_CONFIG**: Video export settings

## Node Reference

All nodes are under the **Model Compare** menu category in ComfyUI.

### Configuration Nodes

| Node | Purpose | Key Features |
|------|---------|--------------|
| **Model Compare Loaders** | Configure base models and architecture | Supports 12 architectures, up to 10 model variations, AUTO_PAIR mode for WAN 2.2 |
| **Prompt Compare** | Define prompt variations | Manual or file input, cross-product/paired modes, up to 20 prompts |
| **LoRA Compare** | Configure LoRAs with strengths | Multi-value strengths (0.5,0.75,1.0), AND (+) or OR (space) combinators, chainable |
| **VAE Config** | VAE variations per model | Up to 10 VAEs, `__baked__` option for checkpoint VAE |
| **CLIP Config** | CLIP variations | Single/dual CLIP support, CPU offloading option, architecture-specific types |
| **Sampling Config Chain** | Per-variation sampling params | Chainable, model-specific settings, multi-value expansion (comma-separated) |

### Sampling & Analysis

| Node | Purpose | Key Features |
|------|---------|--------------|
| **Sampler Compare Advanced** | Main sampling engine | Lazy loading, per-combo caching, internal latent generation, global overrides |
| **Compare Tracker** | Progress monitoring | Real-time progress, VRAM/RAM usage, speed metrics, ETA calculation |

### Grid Generation

| Node | Purpose | Key Features |
|------|---------|--------------|
| **Grid Compare** | Create comparison grids | Hierarchical ragged grids, video output (MP4/GIF/WebM), HTML export, individual images |
| **Grid Preset Formula** | Analyze and optimize layout | Weighted priority algorithm, auto-detect varying dimensions, smart axis assignment |
| **Grid Format Config** | Visual styling | Color palettes, fonts, spacing, borders, depth-based coloring |
| **Grid Preview** | Preview without sampling | Numbered placeholders, real labels, verify structure before expensive sampling |
| **Video Grid Config** | Video export settings | Format (MP4/GIF/WebM), codec, CRF quality control |

### Analysis & Preview

| Node | Purpose | Key Features |
|------|---------|--------------|
| **Histogram Analyzer** | Analyze image histograms | RGB, individual, luminance, hue, HSV, combined output, statistics |
| **Histogram Comparator** | Compare two histograms | Side-by-side comparison, difference metrics |
| **Video Preview** | Preview video files | ComfyUI-native video display |
| **Video Grid Preview** | Preview image/video grids | Combined image and video grid preview |

## Workflow Patterns

### Pattern 1: Simple Model Comparison

**Use Case:** Compare 2-3 models with identical settings

```
Model Compare Loaders → Sampler Compare Advanced → Grid Compare
```

**Setup:**
1. Model Compare Loaders: Set `num_diffusion_models: 2`, select models
2. Sampler: Set seed, steps, cfg
3. Grid: Configure output

**Result:** 2-3 column grid, one model per column

---

### Pattern 2: LoRA Strength Testing

**Use Case:** Find optimal LoRA strength (0.0 → 1.5)

```
LoRA Compare → Model Compare Loaders → Sampler → Grid Compare
```

**Setup:**
1. LoRA Compare: Select LoRA, set strengths `0.0, 0.5, 0.75, 1.0, 1.25, 1.5`
2. Loaders: Connect `lora_config` to `lora_variation_0`
3. Sampler & Grid as usual

**Result:** 6 column grid showing strength progression left→right

**Grid Layout:**
- **Columns:** lora_strength (shows progression)
- **Rows:** Other varying params (if any)

---

### Pattern 3: Multi-LoRA AND/OR Logic

**Use Case:** Compare LoRA A + B combined vs separate

```
LoRA Compare → Model Compare Loaders → Sampler → Grid Compare
```

**AND Example (combinator: `+`):**
- LoRA A strengths: `0.5, 1.0`
- LoRA B strengths: `0.5, 1.0`
- Combinator: `+`
- **Result:** 4 combinations (0.5+0.5, 0.5+1.0, 1.0+0.5, 1.0+1.0)

**OR Example (combinator: ` ` space):**
- LoRA A strengths: `0.5, 1.0`
- LoRA B strengths: `0.5, 1.0`
- Combinator: ` ` (space)
- **Result:** 4 separate rows (A@0.5, A@1.0, B@0.5, B@1.0)

---

### Pattern 4: Per-Model VAE/CLIP Comparison

**Use Case:** Test different VAEs or CLIPs per model variation

```
VAE Config ─────┐
                ├─→ Sampling Config Chain (var 0) ─┐
CLIP Config ────┘                                   │
                                                    ├─→ Chain (var 1) → Sampler → Grid
Model Compare Loaders ──────────────────────────────┘
```

**Setup:**
1. VAE Config: Configure 2-3 VAEs
2. CLIP Config: Configure 2-3 CLIPs
3. Chain (var 0): Connect VAE/CLIP configs, set `variation_index: 0`
4. Chain (var 1): Different VAE/CLIP, set `variation_index: 1`
5. Loaders: Connect chains

**Result:** Grid showing each model with different VAE/CLIP combinations

---

### Pattern 5: Custom Grid Layout

**Use Case:** Control row/column hierarchy for complex comparisons

```
Grid Preset Formula ─────┐
Grid Format Config ──────┼─→ Grid Compare
Model/Sampler ───────────┘
```

**Setup:**
1. Grid Preset Formula: Connect `config` from sampler
   - Optionally lock dimensions: `force_row_dimensions`, `force_column_dimensions`
2. Grid Format Config: Set colors, fonts, spacing
3. Grid Compare: Connect `grid_layout` and `format_config`

**Result:** Optimized grid with custom styling

**Formula Algorithm:**
- Analyzes all varying dimensions
- Higher priority = innermost (adjacent to images)
- Lower priority = outermost (container headers)
- `lora_strength` always innermost columns
- `lora_name` (with OR) always rows

---

### Pattern 6: Cross-Architecture Comparison

**Use Case:** Compare FLUX vs QWEN vs WAN 2.1 directly

```
Model Compare Loaders → Chain (FLUX) → Chain (QWEN) → Chain (WAN) → Sampler → Grid
```

**Setup:**
1. Loaders: Set `num_diffusion_models: 3`
   - Model 0: FLUX
   - Model 1: QWEN
   - Model 2: WAN 2.1
2. Chain (var 0): `config_type: FLUX`, set flux-specific params
3. Chain (var 1): `config_type: QWEN`, set `qwen_shift: 1.15`
4. Chain (var 2): `config_type: WAN2.1`, set `wan_shift: 8.0`, dimensions

**Result:** 3 column grid, each with architecture-specific settings

---

### Pattern 7: Prompt × Model Matrix

**Use Case:** Test 5 prompts across 3 models

```
Prompt Compare → Model Compare Loaders → Sampler → Grid Compare
```

**Setup:**
1. Prompt Compare: Add 5 positive prompts, mode: `cross_product`
2. Loaders: Set `num_diffusion_models: 3`
3. Sampler: 3 models × 5 prompts = 15 images

**Result:** 5 row × 3 column grid
- **Rows:** prompt_positive
- **Columns:** model

---

### Pattern 8: Video Model Comparison

**Use Case:** Compare WAN 2.1 vs Hunyuan Video

```
Video Grid Config ─────┐
                       ├─→ Grid Compare → Video Preview
Model/Sampler ─────────┘
```

**Setup:**
1. Loaders: Select video models (WAN, Hunyuan)
2. Chain: Set `num_frames: 25-81`
3. Video Grid Config: Set `output_type: video_only`, `format: mp4`
4. Grid Compare: Connect `video_config`
5. Video Preview: Connect `video_path`

**Result:** MP4 grid with all combinations playing simultaneously

## Web Features

### Gallery Viewer

**Access:** Navigate to `http://127.0.0.1:8188/model-compare/gallery` (adjust port if needed)

**Features:**
- Browse all generated HTML grids
- Thumbnail preview with metadata
- Search and filter by title, date
- Click to open grid in full browser
- Automatic scanning of output directories

**Configuration:**
- Scans paths defined in `gallery_routes.py`
- Default: `ComfyUI/output/` directory

---

### Grid Builder / Editor

**Access:** Two ways to open:
1. Click "Edit Grid" button in any generated HTML grid
2. Navigate directly: `http://127.0.0.1:8188/model-compare/grid-editor.html?path=<base64_path>`

**Features:**
- **Hierarchy Editor:** Drag-and-drop dimensions between rows/columns/nesting levels
- **Label Configurator:** Customize titles, headers, cell labels with {variable} syntax
- **Subtitle Configurator:** Select which parameters appear as cell subtitles
- **Style Configurator:** Color palettes, fonts, spacing, field-specific colors
- **Live Preview:** See changes immediately
- **Re-Export:** Save with new layout/styling without re-sampling

**Use Cases:**
- Reorganize grid after generation
- Fix suboptimal auto-layout
- Create multiple views of same data
- Custom branding/colors

---

### API Endpoints

**Preset Analysis:**
```
POST /model-compare/analyze_config
Body: {config: MODEL_COMPARE_CONFIG}
Returns: {varying_dimensions, suggested_layout, combination_count}
```

**View Grid:**
```
GET /model-compare/view/<base64_encoded_path>
Returns: HTML grid file
```

**Gallery Data:**
```
GET /model-compare/gallery
Returns: JSON list of all grids with metadata
```

---

## Export Formats

Grid Compare node supports multiple export formats:

### 1. PNG/JPEG (Grid Image)
- High-resolution static grid
- Optional: Embed workflow metadata in PNG
- Optional: Save individual cell images
- **Best for:** Sharing, archiving, printing

### 2. HTML (Interactive)
- Self-contained with base64 embedded images
- Features: filtering, sorting, lightbox, metadata display
- Dark/light theme toggle
- Shareable via URL hash parameters
- **Best for:** Interactive exploration, web sharing

### 3. MP4/GIF/WebM (Video Grid)
- For video model comparisons
- All cells play simultaneously
- Codec options: libx264, libx265
- CRF quality control (1-51, lower = better)
- **Best for:** Video model comparisons (WAN, Hunyuan)

### 4. JSON (Configuration)
- Complete config export
- All metadata and parameters
- **Best for:** Programmatic analysis, archiving settings

### 5. CSV (Parameter Table)
- Parameter table only (no images)
- One row per combination
- **Best for:** Spreadsheet analysis, statistical comparisons

### 6. PDF (Report)
- Requires `reportlab` library
- Grid image + metadata table
- **Best for:** Documentation, reports

**Export Options:**
- Set in Grid Compare node inputs
- `save_individual_images`: Save each cell separately
- `embed_workflow`: Include workflow JSON in PNG metadata
- `output_format`: Grid image format (PNG/JPEG)

---

## Supported Models

| Preset | Model Type | Latent | Notes |
|--------|-----------|--------|-------|
| FLUX | FLUX Dev/Schnell | 16ch | Standard FLUX |
| FLUX2 | FLUX.2 | 128ch | New architecture |
| FLUX_KONTEXT | FLUX Kontext | 16ch | Reference image support |
| SDXL | SDXL 1.0 | 4ch | Standard SDXL |
| PONY | Pony Diffusion | 4ch | SDXL-based |
| WAN2.1 | WAN 2.1 | 16ch | Video, shift=8.0 |
| WAN2.2 | WAN 2.2 | 16ch | Video, two-phase, shift=5.0 |
| HUNYUAN_VIDEO | Hunyuan Video 1.0 | 16ch | Video model |
| HUNYUAN_VIDEO_15 | Hunyuan Video 1.5 | 16ch | Video model |
| QWEN | QWEN | 16ch | AuraFlow, shift=1.15 |
| QWEN_EDIT | QWEN Edit | 16ch | Image editing with references |
| Z_IMAGE | Lumina2 | 16ch | AuraFlow sampling |

**CLIP Types:**
- **Single CLIP:** FLUX, SDXL, QWEN, WAN 2.1
- **Dual CLIP:** FLUX (T5+CLIP), Hunyuan Video (CLIP+LLAVA), FLUX Kontext

## Advanced Features

### Multi-Value Expansion

Many Sampling Config Chain inputs accept **comma-separated values** for automatic expansion:

```python
sampler_name: "euler, dpmpp_2m, dpmpp_3m_sde"
scheduler: "simple, normal"
cfg: "3.5, 5.0, 7.0"
```

**Result:** 3 samplers × 2 schedulers × 3 cfg = 18 combinations

**Supported Fields:**
- sampler_name, scheduler
- steps, cfg, denoise
- width, height (useful for resolution testing)

---

### LoRA Ignore in Grid

For LoRAs that should apply to all images but not appear in grid labels (e.g., Lightning LoRAs):

1. LoRA Compare node: Set `lora_0_ignore_in_grid: True`
2. Grid will hide this LoRA from labels
3. LoRA still applies to all generations

**Use Case:** Testing main LoRAs while keeping speed LoRA constant

---

### Global Parameter Overrides

**Sampler Compare Advanced** has global override slots (0-8):

```
global_param_type_1: "width"
global_value_1: "1024"

global_param_type_2: "height"
global_value_2: "1024"
```

**Effect:** Overrides width/height for ALL variations, ignoring chain configs

**Use Cases:**
- Quick resolution tests without reconfiguring chains
- Force consistent dimensions across different model types
- Override seed for reproducibility

---

### WAN 2.2 High/Low Pair Mode

WAN 2.2 uses two-phase sampling (high noise + low noise models):

1. Model Compare Loaders: Set `pair_mode: AUTO_PAIR`
2. Select high noise model in `diffusion_model`
3. Select low noise model in `diffusion_model_low`
4. LoRA Compare: Set `pair_mode: HIGH_LOW_PAIR`
   - `lora_0`: High noise LoRA
   - `lora_0_low`: Low noise LoRA

**Result:** Properly paired models and LoRAs for WAN 2.2

---

### Grid Hierarchy System

**Ragged Grid Support:** Handles non-uniform branches (different LoRA combinations per model)

**Tree-Based Rendering:** Not Cartesian product, uses actual tree structure

**Priority Algorithm:**
1. Detect all varying dimensions
2. Assign weights (higher = innermost):
   - lora_strength: 1000 (always innermost columns)
   - Numeric fields: 100
   - Short categorical: 50
   - Long categorical: 10
   - lora_name (with OR): -1000 (always rows)
3. Sort by weight and distribute alternating to rows/columns
4. Nesting levels based on combination count:
   - 1-25: Simple XY
   - 26-100: 1 nest level
   - 101-500: 2 nest levels
   - 500+: 3+ nest levels

**Manual Override:** Use Grid Preset Formula's `force_row_dimensions` and `force_column_dimensions`

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No images generated | Check model paths exist and preset matches model type |
| Wrong combination count | Verify `num_diffusion_models`, check LoRA combinator logic (+ vs space) |
| VRAM issues | Lazy loading should help - try fewer combinations, enable CLIP CPU offloading |
| Cache not invalidating | Change model label or any sampling parameter to force re-generation |
| Video not generating | Ensure `num_frames > 1` in chain config and video model selected |
| Gallery empty | Check `output/` directory has HTML grids, verify paths in `gallery_routes.py` |
| Grid Builder shows 0 fields | Grid must have varying dimensions (not all static values) |
| Export failed | Check disk space, file permissions, verify export format support |
| Hierarchy looks wrong | Use Grid Preset Formula to force specific dimensions to rows/columns |

---

## Performance Tips

1. **Start Small:** Test with 2-4 combinations before scaling up
2. **Use Grid Preview:** Verify layout before expensive sampling
3. **Ignore Static LoRAs:** Set `ignore_in_grid: True` for speed LoRAs
4. **CLIP CPU Offloading:** In CLIP Config, set `clip_device: cpu` to save VRAM
5. **Cache Leverage:** Re-run with only 1 parameter changed to reuse cached results
6. **Global Overrides:** Use global params to test resolution without reconfiguring chains
7. **Pagination:** For 500+ combos, grid will auto-paginate into multiple files

---

## Requirements

**Required:**
- ComfyUI (latest recommended)
- Python 3.10+
- Pillow
- NumPy

**Optional:**
- `imageio`, `imageio-ffmpeg` (video support)
- `reportlab` (PDF export)

---

## Credits

**Author:** tlennon-ie  
**Repository:** https://github.com/tlennon-ie/comfyui-model-compare  
**License:** MIT

---

## Changelog

### v3.2.0 (Current - Dec 2025)
- **Smart Grid Builder**: Interactive web-based grid editor with drag-and-drop hierarchy
- **Gallery Viewer**: Web interface for browsing all generated grids
- **Grid Preset Formula**: Automatic layout optimization with weighted priority algorithm
- **Ragged Grid Support**: Handle non-uniform hierarchies properly
- **VAE/CLIP Config Nodes**: Per-variation VAE and CLIP configuration
- **Compare Tracker**: Real-time progress monitoring with VRAM usage
- **Multi-Format Export**: HTML (interactive), PNG, JSON, CSV, PDF
- **Grid Format Config**: Separate visual styling from layout logic
- **Grid Preview**: Preview layout before sampling
- **API Endpoints**: REST API for preset analysis and grid management
- **Theme System**: Dark/light themes across all web interfaces
- **Base64 URL Encoding**: Shareable grid URLs

### v3.1.0 (Nov 2025)
- Added Prompt Compare node
- Custom model labels
- Separate prompt grid saving
- File-based prompt loading

### v3.0.0 (Oct 2025)
- FLUX/FLUX2 support
- Grouped comparison mode
- Complete sampler rewrite with lazy loading
- Sampling Config Chain architecture
- Video grid support (MP4/GIF/WebM)
- Histogram analysis nodes
