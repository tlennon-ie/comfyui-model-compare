"""
Grid Preset Analyzer Module

Analyzes model compare configurations to determine optimal grid layout.
Uses a scoring system based on:
- Number of varying fields (non-static dimensions)
- Number of unique values per field
- Field type priority (prompts outer, strengths on X-axis)

Generates layout recommendations with:
- X/Y axis assignments
- Nesting hierarchy (up to 5 levels)
- Pagination for large grids (max 500 images per grid)
"""

from typing import Dict, List, Any, Tuple, Optional, Set
from dataclasses import dataclass, field
import math


# Field priority for nesting order (higher = more outer/earlier in hierarchy)
# Prompts and models are typically the "grouping" dimensions
# Numeric values like strengths are best on X-axis for comparison
FIELD_PRIORITY = {
    'prompt': 100,
    'prompt_positive': 100,
    'prompt_index': 100,
    'model': 90,
    'model_index': 90,
    'vae': 80,
    'vae_name': 80,
    'clip': 75,
    'clip_variation': 75,
    'sampler_name': 60,
    'sampler': 60,
    'scheduler': 55,
    'lora_name': 50,
    'lora_display': 50,
    'lora_config': 50,
    'seed': 40,
    'cfg': 30,
    'steps': 25,
    'width': 22,
    'height': 21,
    'denoise': 20,
    'lora_strength': 15,
    'lumina_shift': 12,
    'qwen_shift': 11,
    'wan_shift': 10,
    'wan22_shift': 10,
    'hunyuan_shift': 10,
    'flux_guidance': 10,
}

# Fields best suited for X-axis (numeric, good for side-by-side comparison)
X_AXIS_PREFERRED = {
    'lora_strength', 'cfg', 'steps', 'denoise',
    'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift',
    'hunyuan_shift', 'flux_guidance', 'width', 'height'
}

# Fields best suited for Y-axis (categorical, row labels)
Y_AXIS_PREFERRED = {
    'scheduler', 'sampler_name', 'sampler', 'lora_name', 'lora_display',
    'seed'
}

# Fields best for outer nesting (create separate grid sections)
NEST_PREFERRED = {
    'prompt', 'prompt_positive', 'prompt_index',
    'model', 'model_index', 'vae', 'vae_name', 'clip',
    'sampler_name', 'sampler', 'scheduler'
}

# Display names for fields
FIELD_DISPLAY_NAMES = {
    'prompt': 'Prompt',
    'prompt_positive': 'Prompt',
    'prompt_index': 'Prompt',
    'model': 'Model',
    'model_index': 'Model',
    'vae': 'VAE',
    'vae_name': 'VAE',
    'clip': 'CLIP',
    'clip_variation': 'CLIP',
    'sampler_name': 'Sampler',
    'sampler': 'Sampler',
    'scheduler': 'Scheduler',
    'lora_name': 'LoRA',
    'lora_display': 'LoRA',
    'lora_config': 'LoRA Config',
    'lora_strength': 'LoRA Strength',
    'cfg': 'CFG',
    'steps': 'Steps',
    'seed': 'Seed',
    'width': 'Width',
    'height': 'Height',
    'denoise': 'Denoise',
    'lumina_shift': 'Lumina Shift',
    'qwen_shift': 'Qwen Shift',
    'wan_shift': 'WAN Shift',
    'wan22_shift': 'WAN 2.2 Shift',
    'hunyuan_shift': 'Hunyuan Shift',
    'flux_guidance': 'FLUX Guidance',
}


@dataclass
class FieldAnalysis:
    """Analysis of a single varying field."""
    name: str
    display_name: str
    values: List[Any]
    value_count: int
    priority: int
    is_numeric: bool
    is_x_axis_candidate: bool
    is_y_axis_candidate: bool
    is_nest_candidate: bool


@dataclass
class LayoutRecommendation:
    """Recommended grid layout configuration."""
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    nest_levels: List[str] = field(default_factory=list)
    total_combinations: int = 0
    images_per_grid: int = 0
    num_grids: int = 1
    grid_split_field: Optional[str] = None
    preview_text: str = ""
    field_options: List[str] = field(default_factory=list)
    analysis_summary: str = ""


def analyze_variations(config: Dict[str, Any]) -> Dict[str, FieldAnalysis]:
    """
    Analyze a MODEL_COMPARE_CONFIG to find all varying dimensions.
    
    Args:
        config: The configuration dictionary from ModelCompareLoaders
        
    Returns:
        Dict mapping field name to FieldAnalysis with unique values
    """
    if not config:
        return {}
    
    combinations = config.get('combinations', [])
    if not combinations:
        return {}
    
    # Collect all values for each field across combinations
    field_values: Dict[str, Set] = {}
    
    # Fields to check
    check_fields = [
        'model_index', 'vae_name', 'prompt_index',
        'sampler_name', 'scheduler', 'steps', 'cfg', 'denoise',
        'width', 'height', 'seed',
        'lora_display', 'lora_strength',
        'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift',
        'hunyuan_shift', 'flux_guidance'
    ]
    
    for combo in combinations:
        # Check _sampling_override first (for expanded variations)
        override = combo.get('_sampling_override', {})
        
        for field_name in check_fields:
            value = override.get(field_name, combo.get(field_name))
            if value is not None:
                if field_name not in field_values:
                    field_values[field_name] = set()
                # Convert to hashable
                if isinstance(value, (list, dict)):
                    value = str(value)
                field_values[field_name].add(value)
        
        # Special handling for lora_config
        lora_config = combo.get('lora_config', {})
        if lora_config:
            display = lora_config.get('display', '')
            if display and display != 'No LoRA':
                if 'lora_display' not in field_values:
                    field_values['lora_display'] = set()
                field_values['lora_display'].add(display)
            
            # Extract individual lora strengths
            loras = lora_config.get('loras', [])
            for lora in loras:
                strength = lora.get('strength')
                if strength is not None:
                    if 'lora_strength' not in field_values:
                        field_values['lora_strength'] = set()
                    field_values['lora_strength'].add(strength)
        
        # Extract clip variation
        clip_var = combo.get('clip_variation')
        if clip_var:
            if clip_var.get('type') == 'pair':
                clip_str = f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
            else:
                clip_str = clip_var.get('model', clip_var.get('clip_type', ''))
            if clip_str:
                if 'clip' not in field_values:
                    field_values['clip'] = set()
                field_values['clip'].add(clip_str)
    
    # Convert model_index to model names if available
    model_variations = config.get('model_variations', [])
    if 'model_index' in field_values and model_variations:
        model_names = set()
        for idx in field_values['model_index']:
            if isinstance(idx, int) and idx < len(model_variations):
                name = model_variations[idx].get('display_name', 
                       model_variations[idx].get('name', f'Model {idx}'))
                if name.endswith('.safetensors'):
                    name = name[:-12]
                model_names.add(name)
        if model_names:
            field_values['model'] = model_names
            del field_values['model_index']
    
    # Convert prompt_index to prompt text if available
    prompt_variations = config.get('prompt_variations', [])
    if 'prompt_index' in field_values and prompt_variations:
        # Keep as index for filtering, but note we have prompts
        field_values['prompt'] = field_values['prompt_index']
        del field_values['prompt_index']
    
    # Filter to only varying fields (>1 unique value)
    varying_fields: Dict[str, FieldAnalysis] = {}
    
    for field_name, values in field_values.items():
        if len(values) > 1:
            sorted_values = _sort_values(list(values))
            is_numeric = all(isinstance(v, (int, float)) or 
                           (isinstance(v, str) and _is_numeric_string(v)) 
                           for v in sorted_values)
            
            varying_fields[field_name] = FieldAnalysis(
                name=field_name,
                display_name=FIELD_DISPLAY_NAMES.get(field_name, field_name.replace('_', ' ').title()),
                values=sorted_values,
                value_count=len(sorted_values),
                priority=FIELD_PRIORITY.get(field_name, 0),
                is_numeric=is_numeric,
                is_x_axis_candidate=field_name in X_AXIS_PREFERRED or is_numeric,
                is_y_axis_candidate=field_name in Y_AXIS_PREFERRED or not is_numeric,
                is_nest_candidate=field_name in NEST_PREFERRED,
            )
    
    return varying_fields


def _sort_values(values: List[Any]) -> List[Any]:
    """Sort values, handling mixed types."""
    try:
        # Try numeric sort first
        numeric = [(float(v) if isinstance(v, str) else v, v) for v in values]
        numeric.sort(key=lambda x: x[0])
        return [v[1] for v in numeric]
    except (ValueError, TypeError):
        # Fall back to string sort
        try:
            return sorted(values, key=str)
        except TypeError:
            return list(values)


def _is_numeric_string(s: str) -> bool:
    """Check if string represents a number."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def calculate_total_combinations(analysis: Dict[str, FieldAnalysis]) -> int:
    """Calculate total number of image combinations from varying fields."""
    if not analysis:
        return 1
    
    total = 1
    for field_analysis in analysis.values():
        total *= field_analysis.value_count
    return total


def generate_optimal_layout(
    analysis: Dict[str, FieldAnalysis],
    max_per_grid: int = 500,
    config: Dict[str, Any] = None
) -> LayoutRecommendation:
    """
    Generate optimal grid layout based on variation analysis.
    
    Algorithm:
    1. Sort fields by priority (high priority = outer nesting)
    2. Assign lowest priority numeric field to X-axis
    3. Assign next lowest categorical field to Y-axis
    4. Remaining high-priority fields become nest levels (outer to inner)
    5. If total > max_per_grid, determine split point
    
    Args:
        analysis: Dict of field name to FieldAnalysis
        max_per_grid: Maximum images per grid page (default 500)
        config: Optional config for additional context
        
    Returns:
        LayoutRecommendation with axis assignments and nesting
    """
    result = LayoutRecommendation()
    
    if not analysis:
        result.preview_text = "No varying dimensions detected"
        result.analysis_summary = "Static configuration - single image"
        return result
    
    # Get actual combination count from config if available
    if config and 'combinations' in config:
        result.total_combinations = len(config['combinations'])
    else:
        result.total_combinations = calculate_total_combinations(analysis)
    
    # Build list of fields sorted by priority (high to low for nesting)
    fields_by_priority = sorted(
        analysis.values(),
        key=lambda f: (-f.priority, f.value_count)
    )
    
    result.field_options = [f.name for f in fields_by_priority]
    
    # Special case: only 1 varying field
    if len(fields_by_priority) == 1:
        field = fields_by_priority[0]
        result.x_axis = field.name
        result.y_axis = None
        result.images_per_grid = min(field.value_count, max_per_grid)
        result.num_grids = math.ceil(field.value_count / max_per_grid)
        result.preview_text = _format_simple_preview(field)
        result.analysis_summary = f"Single dimension: {field.display_name} ({field.value_count} values)"
        return result
    
    # Special case: only 2 varying fields - simple XY grid
    if len(fields_by_priority) == 2:
        # Put numeric/strength on X, categorical on Y
        if fields_by_priority[1].is_x_axis_candidate:
            result.x_axis = fields_by_priority[1].name
            result.y_axis = fields_by_priority[0].name
        else:
            result.x_axis = fields_by_priority[0].name if fields_by_priority[0].is_x_axis_candidate else fields_by_priority[1].name
            result.y_axis = fields_by_priority[1].name if result.x_axis == fields_by_priority[0].name else fields_by_priority[0].name
        
        result.images_per_grid = min(result.total_combinations, max_per_grid)
        result.num_grids = math.ceil(result.total_combinations / max_per_grid)
        result.preview_text = _format_xy_preview(
            analysis[result.x_axis], 
            analysis[result.y_axis]
        )
        result.analysis_summary = f"2 dimensions: {analysis[result.x_axis].display_name} × {analysis[result.y_axis].display_name}"
        return result
    
    # Complex case: 3+ varying fields - need nesting
    assigned = set()
    
    # 1. Find best X-axis field (lowest priority numeric field)
    x_candidates = [f for f in reversed(fields_by_priority) if f.is_x_axis_candidate]
    if x_candidates:
        result.x_axis = x_candidates[0].name
        assigned.add(result.x_axis)
    
    # 2. Find best Y-axis field (low priority categorical)
    y_candidates = [f for f in reversed(fields_by_priority) 
                   if f.is_y_axis_candidate and f.name not in assigned]
    if y_candidates:
        result.y_axis = y_candidates[0].name
        assigned.add(result.y_axis)
    elif not result.x_axis:
        # No X assigned yet, use first two fields
        result.x_axis = fields_by_priority[-1].name
        assigned.add(result.x_axis)
        if len(fields_by_priority) > 1:
            result.y_axis = fields_by_priority[-2].name
            assigned.add(result.y_axis)
    
    # 3. Remaining fields become nest levels (highest priority = outermost)
    nest_candidates = [f for f in fields_by_priority if f.name not in assigned]
    result.nest_levels = [f.name for f in nest_candidates[:5]]  # Max 5 nest levels
    
    # 4. Calculate pagination
    result.images_per_grid = min(result.total_combinations, max_per_grid)
    
    if result.total_combinations > max_per_grid and result.nest_levels:
        # Split by outermost nest level
        result.grid_split_field = result.nest_levels[0]
        split_field = analysis[result.grid_split_field]
        result.num_grids = split_field.value_count
        result.images_per_grid = result.total_combinations // result.num_grids
    else:
        result.num_grids = math.ceil(result.total_combinations / max_per_grid)
    
    # 5. Generate preview
    result.preview_text = _format_nested_preview(analysis, result)
    result.analysis_summary = _format_analysis_summary(analysis, result)
    
    return result


def _format_simple_preview(field: FieldAnalysis) -> str:
    """Format preview for single-dimension grid."""
    values_str = ", ".join(str(v) for v in field.values[:5])
    if len(field.values) > 5:
        values_str += f", ... ({len(field.values)} total)"
    
    return f"""Layout Preview:
─ {field.display_name} [X-axis]
  └─ Values: {values_str}
  └─ {field.value_count} images in row"""


def _format_xy_preview(x_field: FieldAnalysis, y_field: FieldAnalysis) -> str:
    """Format preview for simple XY grid."""
    x_vals = ", ".join(str(v) for v in x_field.values[:4])
    if len(x_field.values) > 4:
        x_vals += "..."
    
    y_vals = ", ".join(str(v) for v in y_field.values[:4])
    if len(y_field.values) > 4:
        y_vals += "..."
    
    return f"""Layout Preview ({x_field.value_count * y_field.value_count} images):
┌─ {y_field.display_name} [Y-axis: {y_field.value_count} rows]
│  └─ {y_vals}
└─ {x_field.display_name} [X-axis: {x_field.value_count} columns]
   └─ {x_vals}

Grid: {y_field.value_count} rows × {x_field.value_count} columns"""


def _format_nested_preview(
    analysis: Dict[str, FieldAnalysis], 
    layout: LayoutRecommendation
) -> str:
    """Format preview for nested grid layout."""
    lines = [f"Layout Preview ({layout.total_combinations} images, {layout.num_grids} grid(s)):"]
    
    indent = ""
    
    # Nest levels (outermost first)
    for i, nest_field in enumerate(layout.nest_levels):
        field = analysis[nest_field]
        marker = "┌" if i == 0 else "├"
        lines.append(f"{indent}{marker}─ {field.display_name} ({field.value_count} sections)")
        
        # Show first few values
        vals = ", ".join(str(v)[:20] for v in field.values[:3])
        if len(field.values) > 3:
            vals += "..."
        lines.append(f"{indent}│  └─ {vals}")
        
        if i == 0 and layout.grid_split_field == nest_field:
            lines.append(f"{indent}│  ⚡ [Grid split point]")
        
        indent += "│  "
    
    # Y-axis
    if layout.y_axis:
        y_field = analysis[layout.y_axis]
        lines.append(f"{indent}├─ {y_field.display_name} [Y-axis: {y_field.value_count} rows]")
    
    # X-axis
    if layout.x_axis:
        x_field = analysis[layout.x_axis]
        lines.append(f"{indent}└─ {x_field.display_name} [X-axis: {x_field.value_count} columns]")
    
    # Summary line
    if layout.y_axis and layout.x_axis:
        x_count = analysis[layout.x_axis].value_count
        y_count = analysis[layout.y_axis].value_count
        lines.append(f"\nInner grid: {y_count} rows × {x_count} columns = {y_count * x_count} images")
    
    return "\n".join(lines)


def _format_analysis_summary(
    analysis: Dict[str, FieldAnalysis],
    layout: LayoutRecommendation
) -> str:
    """Format a brief summary of the analysis."""
    parts = [f"{len(analysis)} varying dimensions"]
    parts.append(f"{layout.total_combinations} total combinations")
    
    if layout.num_grids > 1:
        parts.append(f"split into {layout.num_grids} grids")
    
    dims = []
    for nest in layout.nest_levels:
        dims.append(f"{analysis[nest].display_name}({analysis[nest].value_count})")
    if layout.y_axis:
        dims.append(f"{analysis[layout.y_axis].display_name}({analysis[layout.y_axis].value_count})")
    if layout.x_axis:
        dims.append(f"{analysis[layout.x_axis].display_name}({analysis[layout.x_axis].value_count})")
    
    if dims:
        parts.append("→ " + " × ".join(dims))
    
    return " | ".join(parts)


def get_field_options_for_dropdown(analysis: Dict[str, FieldAnalysis]) -> List[Tuple[str, str]]:
    """
    Get field options formatted for dropdown widgets.
    
    Returns:
        List of (value, display_label) tuples
    """
    options = [("auto", "Auto"), ("none", "None")]
    
    for field_name, field_analysis in sorted(
        analysis.items(),
        key=lambda x: -x[1].priority
    ):
        label = f"{field_analysis.display_name} ({field_analysis.value_count} values)"
        options.append((field_name, label))
    
    return options


def validate_layout(
    layout: LayoutRecommendation,
    analysis: Dict[str, FieldAnalysis]
) -> List[str]:
    """
    Validate a layout configuration and return any warnings.
    
    Returns:
        List of warning messages (empty if valid)
    """
    warnings = []
    
    # Check for duplicate assignments
    assigned = []
    if layout.x_axis and layout.x_axis != 'auto' and layout.x_axis != 'none':
        assigned.append(layout.x_axis)
    if layout.y_axis and layout.y_axis != 'auto' and layout.y_axis != 'none':
        assigned.append(layout.y_axis)
    for nest in layout.nest_levels:
        if nest and nest != 'auto' and nest != 'none':
            assigned.append(nest)
    
    if len(assigned) != len(set(assigned)):
        warnings.append("Warning: Same field assigned to multiple positions")
    
    # Check for missing fields
    assigned_set = set(assigned)
    unassigned = [f for f in analysis.keys() if f not in assigned_set]
    if unassigned:
        warnings.append(f"Note: {len(unassigned)} field(s) not explicitly assigned: {', '.join(unassigned)}")
    
    # Check for large grids
    if layout.total_combinations > 500:
        warnings.append(f"Large grid: {layout.total_combinations} images will be split into {layout.num_grids} pages")
    
    # Check X-axis assignment
    if layout.x_axis and layout.x_axis in analysis:
        field = analysis[layout.x_axis]
        if not field.is_x_axis_candidate and field.value_count > 10:
            warnings.append(f"Consider: {field.display_name} has many values ({field.value_count}) - may be wide")
    
    return warnings


# Export for API
__all__ = [
    'analyze_variations',
    'generate_optimal_layout',
    'calculate_total_combinations',
    'get_field_options_for_dropdown',
    'validate_layout',
    'FieldAnalysis',
    'LayoutRecommendation',
    'FIELD_PRIORITY',
    'FIELD_DISPLAY_NAMES',
]
