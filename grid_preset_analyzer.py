"""
Grid Preset Analyzer - Analyzes model comparison configurations and recommends optimal grid layouts.

Combination-count-based strategies:
- 1-25 combinations: Simple XY grid (no nesting)
- 26-100 combinations: 1 nest level
- 101-300 combinations: 2 nest levels  
- 300+ combinations: Paginate by outermost dimension
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
import math


# Priority weights for different fields (higher = more important to vary visually)
# Field names MUST match GridCompare dropdown options exactly:
# ["model", "vae", "clip", "lora_name", "lora_strength", "sampler_name", "scheduler", 
#  "lumina_shift", "qwen_shift", "wan_shift", "wan22_shift", "hunyuan_shift", "flux_guidance",
#  "cfg", "steps", "seed", "width", "height", "prompt_positive", "prompt_negative"]

# Valid field names that match GridCompare dropdown options
VALID_GRID_FIELDS = {
    'model', 'vae', 'clip', 'lora_name', 'lora_strength', 
    'sampler_name', 'scheduler', 'steps', 'cfg', 'seed',
    'width', 'height', 'prompt_positive', 'prompt_negative',
    'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift', 
    'hunyuan_shift', 'flux_guidance'
}

FIELD_PRIORITY = {
    'prompt_positive': 100,  # Most important - people want to see prompt differences
    'prompt_negative': 95,   # Negative prompt variations
    'model': 90,             # Second most important - comparing models is primary use case
    'vae': 85,               # VAE differences are significant
    'sampler_name': 60,      # Sampling differences are interesting
    'scheduler': 55,         # Related to sampler
    'steps': 40,             # Technical parameter
    'cfg': 35,               # Technical parameter
    'lora_name': 30,         # LoRA selection
    'lora_strength': 15,     # LoRA strength variations
    'seed': 5,               # Usually least important for visual comparison
}

# Fields that work well as row axes (typically fewer values, important differences)
ROW_AXIS_CANDIDATES = {'prompt_positive', 'prompt_negative', 'model', 'vae', 'sampler_name'}

# Fields that work well as column axes (can have more values)
COL_AXIS_CANDIDATES = {'model', 'sampler_name', 'scheduler', 'steps', 'cfg', 'lora_name', 'lora_strength'}

# Fields that work well as nest levels (grouping outer dimensions)
NEST_CANDIDATES = {'prompt_positive', 'model', 'vae', 'sampler_name', 'scheduler'}


@dataclass
class FieldAnalysis:
    """Analysis of a single varying field."""
    name: str
    display_name: str
    values: List[Any]
    value_count: int
    priority: int
    is_row_candidate: bool = False
    is_col_candidate: bool = False
    is_nest_candidate: bool = False


@dataclass 
class LayoutRecommendation:
    """Recommended grid layout based on analysis."""
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    nest_levels: List[str] = field(default_factory=list)
    total_combinations: int = 0
    combinations_per_grid: int = 0
    num_grids: int = 1
    strategy: str = "simple"  # simple, nested, paginated
    explanation: str = ""
    field_analysis: Dict[str, FieldAnalysis] = field(default_factory=dict)


def _extract_unique_values(items: List[Any], key: str = None) -> List[Any]:
    """Extract unique values from a list, optionally by key."""
    if not items:
        return []
    
    seen = set()
    unique = []
    for item in items:
        if key and isinstance(item, dict):
            val = item.get(key)
        else:
            val = item
        
        # Convert to hashable for set
        hashable = str(val) if isinstance(val, (dict, list)) else val
        if hashable not in seen:
            seen.add(hashable)
            unique.append(val)
    
    return unique


def _get_list_variations(items: List[Any], key: str) -> List[Any]:
    """Get unique values of a specific key from a list of dicts."""
    if not items:
        return []
    
    values = []
    for item in items:
        if isinstance(item, dict) and key in item:
            val = item[key]
            if isinstance(val, list):
                values.extend(val)
            else:
                values.append(val)
    
    return _extract_unique_values(values)


def _get_single_entry_variations(items: List[Any], key: str) -> List[Any]:
    """
    Get variations for a key, but ONLY if a single entry contains multiple values.
    
    This is important for sampling_params where multiple entries come from different
    SamplingConfigChain nodes - those aren't variations, they're different configs.
    Only if ONE entry has an array with multiple values is it a real variation.
    
    Example:
    - [{"scheduler": ["beta", "normal"]}] -> ["beta", "normal"] (real variation)
    - [{"scheduler": ["beta"]}, {"scheduler": ["normal"]}] -> [] (not a variation, different configs)
    """
    if not items:
        return []
    
    # Check each entry - if any single entry has multiple values for this key, those are variations
    for item in items:
        if isinstance(item, dict) and key in item:
            val = item[key]
            if isinstance(val, list) and len(val) > 1:
                # This single entry has multiple values - these are real variations
                return _extract_unique_values(val)
    
    # No single entry had multiple values - not a variation
    return []


def analyze_from_variation_lists(config: Dict[str, Any]) -> Dict[str, FieldAnalysis]:
    """
    Analyze a configuration with raw variation lists (before combinations are computed).
    
    Expected config structure from JS:
    {
        "model_variations": [{"model_name": "...", "vae_name": "..."}],
        "lora_config": [{"name": "...", "strength_model": [...], ...}],
        "sampling_params": [{"sampler_name": "...", "scheduler": "...", "steps": [...], "cfg": [...]}],
        "prompt_variations": [{"positive": "...", "negative": "..."}],
        "combinations": []  # May be empty
    }
    """
    analysis: Dict[str, FieldAnalysis] = {}
    
    # Analyze model variations
    model_variations = config.get('model_variations', [])
    if model_variations:
        # Extract model names
        models = _extract_unique_values(model_variations, 'model_name')
        models = [m for m in models if m]  # Filter None/empty
        if len(models) > 1:
            analysis['model'] = FieldAnalysis(
                name='model',
                display_name='Model',
                values=models,
                value_count=len(models),
                priority=FIELD_PRIORITY.get('model', 50),
                is_row_candidate='model' in ROW_AXIS_CANDIDATES,
                is_col_candidate='model' in COL_AXIS_CANDIDATES,
                is_nest_candidate='model' in NEST_CANDIDATES,
            )
        
        # Extract VAE names
        vaes = _extract_unique_values(model_variations, 'vae_name')
        vaes = [v for v in vaes if v and v != 'Default']
        if len(vaes) > 1:
            analysis['vae'] = FieldAnalysis(
                name='vae',
                display_name='VAE',
                values=vaes,
                value_count=len(vaes),
                priority=FIELD_PRIORITY.get('vae', 50),
                is_row_candidate='vae' in ROW_AXIS_CANDIDATES,
                is_col_candidate='vae' in COL_AXIS_CANDIDATES,
                is_nest_candidate='vae' in NEST_CANDIDATES,
            )
    
    # Analyze sampling params
    # IMPORTANT: Multiple sampling_params entries are from different SamplingConfigChain nodes.
    # We should only consider values as "variations" if they appear as arrays WITHIN a single entry,
    # not if different entries have different single values.
    sampling_params = config.get('sampling_params', [])
    if sampling_params:
        # For each sampling field, check if ANY single entry has multiple values (an array)
        # That indicates an actual variation, not just different configs from different nodes
        
        # Samplers - only count as variation if one entry has multiple samplers
        samplers = _get_single_entry_variations(sampling_params, 'sampler_name')
        if len(samplers) > 1:
            analysis['sampler_name'] = FieldAnalysis(
                name='sampler_name',
                display_name='Sampler',
                values=samplers,
                value_count=len(samplers),
                priority=FIELD_PRIORITY.get('sampler_name', 50),
                is_row_candidate='sampler_name' in ROW_AXIS_CANDIDATES,
                is_col_candidate='sampler_name' in COL_AXIS_CANDIDATES,
                is_nest_candidate='sampler_name' in NEST_CANDIDATES,
            )
        
        # Schedulers
        schedulers = _get_single_entry_variations(sampling_params, 'scheduler')
        if len(schedulers) > 1:
            analysis['scheduler'] = FieldAnalysis(
                name='scheduler',
                display_name='Scheduler',
                values=schedulers,
                value_count=len(schedulers),
                priority=FIELD_PRIORITY.get('scheduler', 50),
                is_row_candidate='scheduler' in ROW_AXIS_CANDIDATES,
                is_col_candidate='scheduler' in COL_AXIS_CANDIDATES,
                is_nest_candidate='scheduler' in NEST_CANDIDATES,
            )
        
        # Steps
        steps = _get_single_entry_variations(sampling_params, 'steps')
        if len(steps) > 1:
            analysis['steps'] = FieldAnalysis(
                name='steps',
                display_name='Steps',
                values=steps,
                value_count=len(steps),
                priority=FIELD_PRIORITY.get('steps', 50),
                is_row_candidate=False,
                is_col_candidate='steps' in COL_AXIS_CANDIDATES,
                is_nest_candidate='steps' in NEST_CANDIDATES,
            )
        
        # CFG
        cfgs = _get_single_entry_variations(sampling_params, 'cfg')
        if len(cfgs) > 1:
            analysis['cfg'] = FieldAnalysis(
                name='cfg',
                display_name='CFG Scale',
                values=cfgs,
                value_count=len(cfgs),
                priority=FIELD_PRIORITY.get('cfg', 50),
                is_row_candidate=False,
                is_col_candidate='cfg' in COL_AXIS_CANDIDATES,
                is_nest_candidate='cfg' in NEST_CANDIDATES,
            )
    
    # Analyze LoRA config
    lora_config = config.get('lora_config', [])
    if lora_config:
        # LoRA names - use 'lora_name' to match GridCompare dropdown
        lora_names = _extract_unique_values(lora_config, 'name')
        lora_names = [n for n in lora_names if n and n != 'None']
        if len(lora_names) > 1:
            analysis['lora_name'] = FieldAnalysis(
                name='lora_name',
                display_name='LoRA',
                values=lora_names,
                value_count=len(lora_names),
                priority=FIELD_PRIORITY.get('lora_name', 50),
                is_row_candidate='lora_name' in ROW_AXIS_CANDIDATES,
                is_col_candidate='lora_name' in COL_AXIS_CANDIDATES,
                is_nest_candidate='lora_name' in NEST_CANDIDATES,
            )
        
        # LoRA strengths (collect all unique strengths across all LoRAs)
        all_strengths = set()
        for lora in lora_config:
            if isinstance(lora, dict):
                for key in ['strength_model', 'strength_clip', 'strength', 'strengths']:
                    strengths = lora.get(key, [])
                    if isinstance(strengths, list):
                        all_strengths.update(strengths)
                    elif strengths is not None:
                        all_strengths.add(strengths)
        
        all_strengths = sorted([s for s in all_strengths if s is not None])
        if len(all_strengths) > 1:
            analysis['lora_strength'] = FieldAnalysis(
                name='lora_strength',
                display_name='LoRA Strength',
                values=all_strengths,
                value_count=len(all_strengths),
                priority=FIELD_PRIORITY.get('lora_strength', 50),
                is_row_candidate=False,
                is_col_candidate='lora_strength' in COL_AXIS_CANDIDATES,
                is_nest_candidate='lora_strength' in NEST_CANDIDATES,
            )
    
    # Analyze prompt variations - use 'prompt_positive' to match GridCompare dropdown
    prompt_variations = config.get('prompt_variations', [])
    if prompt_variations and len(prompt_variations) > 1:
        # Use index as identifier since prompts can be long
        prompt_labels = [f"Prompt {i+1}" for i in range(len(prompt_variations))]
        analysis['prompt_positive'] = FieldAnalysis(
            name='prompt_positive',
            display_name='Prompt',
            values=prompt_labels,
            value_count=len(prompt_variations),
            priority=FIELD_PRIORITY.get('prompt_positive', 100),
            is_row_candidate='prompt_positive' in ROW_AXIS_CANDIDATES,
            is_col_candidate='prompt_positive' in COL_AXIS_CANDIDATES,
            is_nest_candidate='prompt_positive' in NEST_CANDIDATES,
        )
    
    return analysis


def calculate_total_combinations(analysis: Dict[str, FieldAnalysis]) -> int:
    """Calculate total number of combinations from analyzed fields."""
    if not analysis:
        return 1
    
    total = 1
    for field_analysis in analysis.values():
        total *= field_analysis.value_count
    
    return total


def generate_optimal_layout(
    analysis: Dict[str, FieldAnalysis],
    max_per_grid: int = 500,
    client_estimated_combinations: Optional[int] = None
) -> LayoutRecommendation:
    """
    Generate optimal grid layout based on field analysis.
    
    Combination-count-based strategies:
    - 1-25: Simple XY grid (no nesting)
    - 26-100: 1 nest level (outer group)
    - 101-300: 2 nest levels
    - 300+: Paginate by outermost dimension
    
    Args:
        analysis: Dict of field analyses
        max_per_grid: Maximum images per grid page
        client_estimated_combinations: Client-side calculated combination count (more accurate)
    """
    if not analysis:
        return LayoutRecommendation(
            explanation="No varying fields detected. Using default layout."
        )
    
    # Use client estimate if provided (JS calculates this more accurately for complex workflows)
    # Otherwise fall back to multiplying all field counts (may overcount)
    if client_estimated_combinations and client_estimated_combinations > 0:
        total_combos = client_estimated_combinations
    else:
        total_combos = calculate_total_combinations(analysis)
    
    # Sort fields by priority (highest first)
    sorted_fields = sorted(
        analysis.values(),
        key=lambda f: (f.priority, f.value_count),
        reverse=True
    )
    
    # Determine strategy based on combination count
    if total_combos <= 25:
        return _simple_xy_layout(sorted_fields, total_combos, analysis)
    elif total_combos <= 100:
        return _single_nest_layout(sorted_fields, total_combos, max_per_grid, analysis)
    elif total_combos <= 300:
        return _double_nest_layout(sorted_fields, total_combos, max_per_grid, analysis)
    else:
        return _paginated_layout(sorted_fields, total_combos, max_per_grid, analysis)


def _simple_xy_layout(
    sorted_fields: List[FieldAnalysis],
    total_combos: int,
    analysis: Dict[str, FieldAnalysis]
) -> LayoutRecommendation:
    """
    Simple XY grid for 1-25 combinations.
    Best field goes to rows (y_axis), second best to columns (x_axis).
    """
    x_axis = None
    y_axis = None
    
    # Find best row candidate (y_axis)
    for f in sorted_fields:
        if f.is_row_candidate:
            y_axis = f.name
            break
    
    # If no row candidate, use highest priority field
    if not y_axis and sorted_fields:
        y_axis = sorted_fields[0].name
    
    # Find best column candidate (x_axis) that isn't already used
    for f in sorted_fields:
        if f.name != y_axis and f.is_col_candidate:
            x_axis = f.name
            break
    
    # If no column candidate, use second highest priority field
    if not x_axis:
        for f in sorted_fields:
            if f.name != y_axis:
                x_axis = f.name
                break
    
    # Build explanation
    parts = []
    if y_axis:
        parts.append(f"Rows: {analysis[y_axis].display_name}")
    if x_axis:
        parts.append(f"Columns: {analysis[x_axis].display_name}")
    
    return LayoutRecommendation(
        x_axis=x_axis,
        y_axis=y_axis,
        nest_levels=[],
        total_combinations=total_combos,
        combinations_per_grid=total_combos,
        num_grids=1,
        strategy="simple",
        explanation=f"Simple grid with {total_combos} combinations. " + ", ".join(parts),
        field_analysis=analysis,
    )


def _single_nest_layout(
    sorted_fields: List[FieldAnalysis],
    total_combos: int,
    max_per_grid: int,
    analysis: Dict[str, FieldAnalysis]
) -> LayoutRecommendation:
    """
    Single nest level for 26-100 combinations.
    Highest priority field becomes outer nest, next two become X/Y.
    """
    nest_levels = []
    x_axis = None
    y_axis = None
    
    available = list(sorted_fields)
    
    # Pick nest level (prefer nest candidates)
    for i, f in enumerate(available):
        if f.is_nest_candidate:
            nest_levels.append(f.name)
            available.pop(i)
            break
    
    # If no nest candidate found, use highest priority
    if not nest_levels and available:
        nest_levels.append(available.pop(0).name)
    
    # Pick Y axis (row)
    for i, f in enumerate(available):
        if f.is_row_candidate:
            y_axis = f.name
            available.pop(i)
            break
    if not y_axis and available:
        y_axis = available.pop(0).name
    
    # Pick X axis (column)
    for i, f in enumerate(available):
        if f.is_col_candidate:
            x_axis = f.name
            available.pop(i)
            break
    if not x_axis and available:
        x_axis = available.pop(0).name
    
    # Calculate combinations per nested grid
    nest_count = analysis[nest_levels[0]].value_count if nest_levels else 1
    combos_per_grid = total_combos // nest_count if nest_count > 0 else total_combos
    
    # Build explanation
    parts = []
    if nest_levels:
        parts.append(f"Grouped by: {analysis[nest_levels[0]].display_name}")
    if y_axis:
        parts.append(f"Rows: {analysis[y_axis].display_name}")
    if x_axis:
        parts.append(f"Columns: {analysis[x_axis].display_name}")
    
    return LayoutRecommendation(
        x_axis=x_axis,
        y_axis=y_axis,
        nest_levels=nest_levels,
        total_combinations=total_combos,
        combinations_per_grid=combos_per_grid,
        num_grids=nest_count,
        strategy="nested",
        explanation=f"Nested grid with {total_combos} combinations across {nest_count} groups. " + ", ".join(parts),
        field_analysis=analysis,
    )


def _double_nest_layout(
    sorted_fields: List[FieldAnalysis],
    total_combos: int,
    max_per_grid: int,
    analysis: Dict[str, FieldAnalysis]
) -> LayoutRecommendation:
    """
    Double nest level for 101-300 combinations.
    Two highest priority fields become outer nests, next two become X/Y.
    """
    nest_levels = []
    x_axis = None
    y_axis = None
    
    available = list(sorted_fields)
    
    # Pick first nest level
    for i, f in enumerate(available):
        if f.is_nest_candidate:
            nest_levels.append(f.name)
            available.pop(i)
            break
    if not nest_levels and available:
        nest_levels.append(available.pop(0).name)
    
    # Pick second nest level
    for i, f in enumerate(available):
        if f.is_nest_candidate:
            nest_levels.append(f.name)
            available.pop(i)
            break
    if len(nest_levels) < 2 and available:
        nest_levels.append(available.pop(0).name)
    
    # Pick Y axis (row)
    for i, f in enumerate(available):
        if f.is_row_candidate:
            y_axis = f.name
            available.pop(i)
            break
    if not y_axis and available:
        y_axis = available.pop(0).name
    
    # Pick X axis (column)
    for i, f in enumerate(available):
        if f.is_col_candidate:
            x_axis = f.name
            available.pop(i)
            break
    if not x_axis and available:
        x_axis = available.pop(0).name
    
    # Calculate combinations per nested grid
    nest_count = 1
    for n in nest_levels:
        if n in analysis:
            nest_count *= analysis[n].value_count
    combos_per_grid = total_combos // nest_count if nest_count > 0 else total_combos
    
    # Build explanation
    parts = []
    if nest_levels:
        nest_names = [analysis[n].display_name for n in nest_levels]
        parts.append(f"Grouped by: {' → '.join(nest_names)}")
    if y_axis:
        parts.append(f"Rows: {analysis[y_axis].display_name}")
    if x_axis:
        parts.append(f"Columns: {analysis[x_axis].display_name}")
    
    return LayoutRecommendation(
        x_axis=x_axis,
        y_axis=y_axis,
        nest_levels=nest_levels,
        total_combinations=total_combos,
        combinations_per_grid=combos_per_grid,
        num_grids=nest_count,
        strategy="nested",
        explanation=f"Double-nested grid with {total_combos} combinations across {nest_count} groups. " + ", ".join(parts),
        field_analysis=analysis,
    )


def _paginated_layout(
    sorted_fields: List[FieldAnalysis],
    total_combos: int,
    max_per_grid: int,
    analysis: Dict[str, FieldAnalysis]
) -> LayoutRecommendation:
    """
    Paginated layout for 300+ combinations.
    Uses nesting and pagination by outermost dimension.
    """
    # Start with double nest layout as base
    layout = _double_nest_layout(sorted_fields, total_combos, max_per_grid, analysis)
    
    # Calculate pagination
    if layout.combinations_per_grid > max_per_grid:
        num_pages = math.ceil(layout.combinations_per_grid / max_per_grid)
        layout.num_grids = layout.num_grids * num_pages
        layout.combinations_per_grid = max_per_grid
    
    layout.strategy = "paginated"
    layout.explanation = (
        f"Paginated grid with {total_combos} total combinations. "
        f"Split into ~{layout.num_grids} grids of up to {max_per_grid} images each. "
        + layout.explanation.split(". ", 1)[-1] if ". " in layout.explanation else ""
    )
    
    return layout


def analyze_config(config: Dict[str, Any], max_per_grid: int = 500) -> LayoutRecommendation:
    """
    Main entry point: analyze a configuration and return layout recommendation.
    
    Works with both pre-computed combinations and raw variation lists.
    Uses client-side _estimated_combinations when available (more accurate for complex workflows).
    """
    # First try to analyze from combinations array (if populated)
    combinations = config.get('combinations', [])
    
    if combinations:
        # Use combinations-based analysis
        analysis = analyze_from_combinations(combinations)
    else:
        # Fall back to raw variation lists
        analysis = analyze_from_variation_lists(config)
    
    # Get client-side estimated combinations if available (JS calculates this more accurately)
    client_estimate = config.get('_estimated_combinations')
    
    return generate_optimal_layout(analysis, max_per_grid, client_estimate)


def analyze_from_combinations(combinations: List[Dict[str, Any]]) -> Dict[str, FieldAnalysis]:
    """
    Analyze from pre-computed combinations array.
    Each combination is a dict with field values.
    Only considers fields that are valid GridCompare dropdown options.
    """
    if not combinations:
        return {}
    
    analysis: Dict[str, FieldAnalysis] = {}
    
    # Collect all unique values for each field
    field_values: Dict[str, Set[Any]] = {}
    
    for combo in combinations:
        if not isinstance(combo, dict):
            continue
        for key, value in combo.items():
            # Skip internal/private fields (start with _)
            if key.startswith('_'):
                continue
            # Skip complex dict/list values that aren't hashable
            if isinstance(value, (dict, list)):
                continue
            if key not in field_values:
                field_values[key] = set()
            field_values[key].add(value)
    
    # Create FieldAnalysis for fields with multiple values
    for field_name, values in field_values.items():
        if len(values) > 1:
            # Map field name to canonical form
            canonical = _canonicalize_field_name(field_name)
            
            # Only include fields that are valid GridCompare dropdown options
            if canonical not in VALID_GRID_FIELDS:
                continue
            
            analysis[canonical] = FieldAnalysis(
                name=canonical,
                display_name=_get_display_name(canonical),
                values=list(values),
                value_count=len(values),
                priority=FIELD_PRIORITY.get(canonical, 50),
                is_row_candidate=canonical in ROW_AXIS_CANDIDATES,
                is_col_candidate=canonical in COL_AXIS_CANDIDATES,
                is_nest_candidate=canonical in NEST_CANDIDATES,
            )
    
    return analysis


def _canonicalize_field_name(name: str) -> str:
    """Convert field name to canonical form that matches GridCompare dropdown options."""
    name_lower = name.lower()
    
    # Map various input field names to GridCompare dropdown values
    mappings = {
        'model_name': 'model',
        'checkpoint': 'model',
        'vae_name': 'vae',
        # sampler_name stays as sampler_name (matches dropdown)
        'sampler': 'sampler_name',
        'positive': 'prompt_positive',
        'positive_prompt': 'prompt_positive',
        'negative': 'prompt_negative',
        'negative_prompt': 'prompt_negative',
        'prompt': 'prompt_positive',
        'strength_model': 'lora_strength',
        'strength_clip': 'lora_strength',
        'lora': 'lora_name',
    }
    
    return mappings.get(name_lower, name_lower)


def _get_display_name(canonical: str) -> str:
    """Get display name for canonical field name."""
    display_names = {
        'model': 'Model',
        'vae': 'VAE',
        'sampler_name': 'Sampler',
        'scheduler': 'Scheduler',
        'steps': 'Steps',
        'cfg': 'CFG Scale',
        'prompt_positive': 'Pos Prompt',
        'prompt_negative': 'Neg Prompt',
        'lora_name': 'LoRA',
        'lora_strength': 'LoRA Strength',
        'seed': 'Seed',
    }
    
    return display_names.get(canonical, canonical.replace('_', ' ').title())
