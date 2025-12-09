"""
Grid Utilities Module

Shared utilities for grid layout, LoRA expansion, and dimension detection.
Used by GridPreview, GridPresetFormula, and GridCompare for consistent behavior.

Key Features:
- LoRA mode-aware expansion (OR/AND/MIXED)
- Consistent dimension detection
- Row grouping for LoRA combinations
- Text wrapping for prompts
"""

import itertools
import textwrap
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class LoraGroup:
    """Represents a group of LoRAs that are AND-combined."""
    loras: List[Dict]  # List of LoRA entries in this group
    label: str  # Combined label for display (e.g., "Cine + analog")
    strength_values: List[List[float]]  # List of strength lists per LoRA
    ignore_in_grid: bool = False  # If all LoRAs in group are ignored
    
    def get_strength_combinations(self) -> List[Tuple[float, ...]]:
        """Get cartesian product of all strength values."""
        if not self.strength_values:
            return [(1.0,)]
        return list(itertools.product(*self.strength_values))
    
    def format_strength_tuple(self, strengths: Tuple[float, ...]) -> str:
        """Format a strength tuple for display."""
        if len(strengths) == 1:
            return f"{strengths[0]:.1f}".rstrip('0').rstrip('.')
        return "(" + ",".join(f"{s:.1f}".rstrip('0').rstrip('.') for s in strengths) + ")"


def clean_lora_name(lora: Dict) -> str:
    """Extract and clean LoRA name for display."""
    name = lora.get('label', '') or lora.get('name', 'Unknown')
    if '\\' in name:
        name = name.split('\\')[-1]
    if name.endswith('.safetensors'):
        name = name[:-12]
    return name


def clean_model_name(name: str) -> str:
    """Clean model name for display."""
    if '\\' in name:
        name = name.split('\\')[-1]
    if name.endswith('.safetensors'):
        name = name[:-12]
    for prefix in ['[Diffusion] ', '[Checkpoint] ', 'extra\\']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def parse_lora_groups(loras: List[Dict]) -> List[LoraGroup]:
    """
    Parse LoRA list into groups based on combinator.
    
    Handles linear chain parsing:
    - '+' combinator: AND - combine with next LoRA into same group
    - ' ' combinator: OR - start a new group
    
    Examples:
    - A(+)B(+)C = One group: [A, B, C]
    - A( )B( )C = Three groups: [A], [B], [C]
    - A(+)B( )C(+)D = Two groups: [A, B], [C, D]
    
    Returns:
        List of LoraGroup objects
    """
    if not loras:
        return []
    
    groups = []
    current_group_loras = []
    
    for lora in loras:
        current_group_loras.append(lora)
        combinator = lora.get('combinator', '+')
        
        if combinator == ' ':  # OR - end current group, start new one
            if current_group_loras:
                groups.append(_create_lora_group(current_group_loras))
                current_group_loras = []
    
    # Don't forget the last group
    if current_group_loras:
        groups.append(_create_lora_group(current_group_loras))
    
    return groups


def _create_lora_group(loras: List[Dict]) -> LoraGroup:
    """Create a LoraGroup from a list of LoRAs."""
    # Build combined label
    labels = []
    strength_values = []
    all_ignored = True
    
    for lora in loras:
        name = clean_lora_name(lora)
        ignore = lora.get('ignore_in_grid', False)
        
        if not ignore:
            all_ignored = False
            labels.append(name)
        
        # Get strengths
        strengths = lora.get('strengths', [1.0])
        if not isinstance(strengths, list):
            strengths = [strengths]
        strength_values.append(strengths)
    
    label = ' + '.join(labels) if labels else 'Hidden LoRAs'
    
    return LoraGroup(
        loras=loras,
        label=label,
        strength_values=strength_values,
        ignore_in_grid=all_ignored
    )


def expand_combinations_with_lora_modes(
    base_combinations: List[Dict],
    config: Dict
) -> List[Dict]:
    """
    Expand combinations based on LoRA modes (OR/AND/MIXED).
    
    This is the main entry point for LoRA expansion. It handles:
    - OR mode: Each LoRA becomes a separate row
    - AND mode: LoRAs are combined, strength tuples become columns
    - MIXED mode: OR-separated groups become rows, AND within groups
    
    Args:
        base_combinations: Initial combinations (model × prompt)
        config: Full config with chain_lora_configs
        
    Returns:
        Expanded list of combinations with proper LoRA data
    """
    chain_lora_configs = config.get('chain_lora_configs', {})
    
    if not chain_lora_configs:
        return base_combinations
    
    expanded = []
    
    for combo in base_combinations:
        model_idx = combo.get('model_index', 0)
        lora_config = chain_lora_configs.get(model_idx, {})
        loras = lora_config.get('loras', [])
        
        if not loras:
            # No LoRAs - keep combo as-is
            expanded.append(combo)
            continue
        
        # Parse into groups based on combinators
        groups = parse_lora_groups(loras)
        
        if not groups:
            expanded.append(combo)
            continue
        
        # Expand based on groups
        for group in groups:
            strength_combos = group.get_strength_combinations()
            
            for strength_tuple in strength_combos:
                new_combo = dict(combo)
                
                # Build expanded LoRA list with specific strengths
                expanded_loras = []
                lora_names = []
                lora_strengths = []
                
                for lora, strength in zip(group.loras, strength_tuple):
                    name = clean_lora_name(lora)
                    new_lora = dict(lora)
                    new_lora['strength'] = strength
                    new_lora['label'] = name
                    expanded_loras.append(new_lora)
                    
                    if not lora.get('ignore_in_grid', False):
                        lora_names.append(name)
                        lora_strengths.append(strength)
                
                new_combo['lora_config'] = {
                    'loras': expanded_loras,
                    'lora_names': lora_names,
                    'lora_strengths': lora_strengths,
                    'display': ' + '.join(f"{n}:{s}" for n, s in zip(lora_names, lora_strengths)),
                    'group_label': group.label,
                    'is_and_group': len(group.loras) > 1,
                }
                
                # Set top-level fields for easier access
                new_combo['lora_name'] = group.label
                new_combo['lora_strength'] = strength_tuple if len(strength_tuple) > 1 else strength_tuple[0]
                new_combo['lora_group_label'] = group.label
                
                expanded.append(new_combo)
    
    return expanded


def detect_varying_dimensions(
    combinations: List[Dict],
    config: Dict
) -> Dict[str, List[Any]]:
    """
    Detect which fields have multiple unique values across combinations.
    
    Returns a dict of field_name -> sorted list of unique values.
    Only includes fields with 2+ unique values.
    
    Special handling for:
    - Per-LoRA strength dimensions (e.g., 'Cine_strength')
    - LoRA group labels
    - Tuple-based strength values for AND mode
    """
    fields = [
        'model', 'vae', 'clip', 'lora_name', 'lora_strength',
        'sampler_name', 'scheduler', 'steps', 'cfg', 'seed',
        'width', 'height', 'prompt_positive', 'prompt_negative',
        'lumina_shift', 'qwen_shift', 'wan_shift', 'hunyuan_shift', 'flux_guidance',
        'lora_group_label'
    ]
    
    field_values = {f: set() for f in fields}
    
    # Track per-LoRA dimensions for AND mode
    per_lora_strengths = {}  # lora_name -> set of strengths
    
    for combo in combinations:
        # Extract standard fields
        for field in fields:
            val = get_combo_field_value(combo, config, field)
            if val is not None:
                # Make hashable
                if isinstance(val, (list, dict)):
                    val = str(val)
                field_values[field].add(val)
        
        # Track per-LoRA strengths for AND mode display
        lora_config = combo.get('lora_config', {})
        loras = lora_config.get('loras', [])
        
        if len(loras) > 1:  # AND mode with multiple LoRAs
            for lora in loras:
                if lora.get('ignore_in_grid', False):
                    continue
                name = clean_lora_name(lora)
                strength = lora.get('strength', 1.0)
                if name not in per_lora_strengths:
                    per_lora_strengths[name] = set()
                per_lora_strengths[name].add(strength)
    
    # Build result with only varying dimensions
    varying = {}
    
    for field, values in field_values.items():
        if len(values) > 1:
            try:
                # Handle tuples
                if values and isinstance(next(iter(values)), tuple):
                    varying[field] = sorted(list(values))
                else:
                    varying[field] = sorted(list(values))
            except TypeError:
                varying[field] = list(values)
    
    # Add per-LoRA strength dimensions for AND mode
    for lora_name, strengths in per_lora_strengths.items():
        if len(strengths) > 1:
            dim_key = f"{lora_name}_strength"
            varying[dim_key] = sorted(list(strengths))
    
    return varying


def get_combo_field_value(combo: Dict, config: Dict, field: str) -> Any:
    """
    Extract field value from a combination.
    
    Handles:
    - Direct combo fields
    - Sampling overrides
    - LoRA config fields
    - Model variations
    - Per-LoRA strength dimensions
    """
    # Direct fields
    if field in combo:
        return combo[field]
    
    # Sampling override
    override = combo.get('_sampling_override', {})
    if field in override:
        return override[field]
    
    # LoRA fields
    lora_config = combo.get('lora_config', {})
    loras = lora_config.get('loras', [])
    
    if field == 'lora_name':
        names = lora_config.get('lora_names', [])
        if not names:
            names = [clean_lora_name(l) for l in loras if not l.get('ignore_in_grid', False)]
        if names:
            return names[0] if len(names) == 1 else ' + '.join(str(n) for n in names)
        return None
    
    if field == 'lora_strength':
        strengths = lora_config.get('lora_strengths', [])
        if not strengths:
            strengths = [l.get('strength', 1.0) for l in loras if not l.get('ignore_in_grid', False)]
        if strengths:
            return strengths[0] if len(strengths) == 1 else tuple(strengths)
        return None
    
    if field == 'lora_group_label':
        return lora_config.get('group_label') or combo.get('lora_group_label')
    
    # Per-LoRA strength dimensions (e.g., 'Cine_strength')
    if field.endswith('_strength') and field != 'lora_strength':
        lora_prefix = field[:-9]  # Remove '_strength'
        for lora in loras:
            if lora.get('ignore_in_grid', False):
                continue
            name = clean_lora_name(lora)
            if name == lora_prefix or name.lower() == lora_prefix.lower():
                return lora.get('strength', 1.0)
        return None
    
    # Model from model_variations
    if field == 'model':
        model_idx = combo.get('model_index', 0)
        model_vars = config.get('model_variations', [])
        if model_idx < len(model_vars):
            entry = model_vars[model_idx]
            return clean_model_name(entry.get('display_name', entry.get('name', f'Model {model_idx}')))
        return combo.get('model')
    
    return None


def build_lora_row_groups(
    combinations: List[Dict],
    config: Dict
) -> List[Dict]:
    """
    Build row grouping information for LoRA display.
    
    Returns list of row group info:
    - label: Display label for row header
    - lora_names: List of LoRA names in this group
    - is_and_group: Whether this is an AND-combined group
    - combinations: Combinations belonging to this row
    """
    row_groups = {}
    
    for combo in combinations:
        lora_config = combo.get('lora_config', {})
        group_label = lora_config.get('group_label', 'No LoRA')
        
        if group_label not in row_groups:
            row_groups[group_label] = {
                'label': group_label,
                'lora_names': lora_config.get('lora_names', []),
                'is_and_group': lora_config.get('is_and_group', False),
                'combinations': []
            }
        
        row_groups[group_label]['combinations'].append(combo)
    
    return list(row_groups.values())


def wrap_text(text: str, width: int = 80) -> List[str]:
    """
    Wrap text to specified character width.
    
    Args:
        text: Text to wrap
        width: Maximum characters per line
        
    Returns:
        List of wrapped lines
    """
    if not text:
        return []
    return textwrap.wrap(text, width=width, break_long_words=True, break_on_hyphens=True)


def format_strength_value(val: Any) -> str:
    """Format a strength value for display."""
    if val is None:
        return "N/A"
    if isinstance(val, float):
        return f"{val:.2f}".rstrip('0').rstrip('.')
    if isinstance(val, tuple):
        return '(' + ','.join(f"{v:.1f}".rstrip('0').rstrip('.') for v in val) + ')'
    return str(val)


def format_prompt_for_header(prompt: str, wrap_width: int = 80, max_lines: int = 0) -> List[str]:
    """
    Format prompt for display in header, with wrapping.
    No truncation - show full prompt wrapped across multiple lines.
    
    Args:
        prompt: Full prompt text
        wrap_width: Characters per line (0 = no wrap)
        max_lines: Maximum lines (0 = unlimited)
        
    Returns:
        List of lines to display
    """
    if not prompt:
        return []
    
    if wrap_width <= 0:
        return [prompt]
    
    wrapped = wrap_text(prompt, wrap_width)
    
    if max_lines > 0 and len(wrapped) > max_lines:
        wrapped = wrapped[:max_lines]
        if wrapped:
            wrapped[-1] = wrapped[-1][:wrap_width - 3] + '...'
    
    return wrapped


# Weight constants for dimension prioritization
DEFAULT_DIMENSION_WEIGHTS = {
    'lora_strength': 100,    # Innermost (columns)
    'lora_name': 95,
    'lora_group_label': 93,
    'cfg': 90,
    'steps': 88,
    'sampler_name': 85,
    'denoise': 82,
    'scheduler': 80,
    'model': 70,
    'vae': 65,
    'clip': 60,
    'prompt_positive': 50,
    'prompt_negative': 45,
    'width': 40,
    'height': 38,
    'seed': 10,
}


def get_dimension_weight(field: str, user_weights: Dict[str, int] = None) -> int:
    """Get weight for a dimension, considering per-LoRA dimensions."""
    if user_weights and field in user_weights:
        return user_weights[field]
    
    # Per-LoRA strength dimensions inherit from lora_strength
    if field.endswith('_strength') and field not in DEFAULT_DIMENSION_WEIGHTS:
        base_weight = user_weights.get('lora_strength', 100) if user_weights else 100
        return base_weight
    
    return DEFAULT_DIMENSION_WEIGHTS.get(field, 50)
