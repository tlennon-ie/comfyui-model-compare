"""
Grid Preset Analyzer - Robust algorithm for optimal grid layouts.

NEW FORMULA (v2.0):
- lora_strength → ALWAYS columns when varying (shows progression left→right)
- lora_name → ALWAYS rows when OR combinator creates branches
- Nest priority: sampler_name → model → prompt_positive → scheduler → vae → clip
- Split field used when grid exceeds limits

Combination-count-based strategies:
- 1-25 combinations: Simple XY grid (no nesting)
- 26-100 combinations: 1 nest level
- 101-500 combinations: 2 nest levels  
- 500+ combinations: 3+ nest levels with pagination
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
import math
import itertools


# =============================================================================
# NEW AXIS ASSIGNMENT RULES
# =============================================================================

# REQUIRED axis assignments - these MUST be honored when the field is varying
AXIS_REQUIRED = {
    'lora_strength': 'COLUMN',    # ALWAYS columns - shows strength progression left→right
    'lora_name': 'ROW',           # ALWAYS rows when OR combinator creates branches
}

# Secondary column candidates (prefer these for X axis when lora_strength not varying)
# Numeric progression fields are ideal for columns (left→right shows gradual change)
AXIS_PREFERRED_COLUMN = [
    'lora_strength',  # Highest priority - always show strength progression left→right
    'cfg', 'steps', 'denoise', 'lumina_shift', 'qwen_shift', 
    'wan_shift', 'wan22_shift', 'hunyuan_shift', 'flux_guidance',
    'height', 'width'
]

# Secondary row candidates (prefer these for Y axis when lora_name not varying)
AXIS_PREFERRED_ROW = ['scheduler', 'sampler_name', 'model', 'vae']

# Nest level priority order - highest visual impact first
NEST_PRIORITY = [
    'model',             # Priority 1 - base model architecture creates major differences
    'sampler_name',      # Priority 2 - sampling method creates visual differences
    'prompt_positive',   # Priority 3 - content difference
    'scheduler',         # Priority 4 - if not used as row
    'vae',               # Priority 5 - subtle visual changes
    'clip',              # Priority 6 - encoding differences
    'prompt_negative',   # Priority 7 - negative prompt variations
]

# All valid grid fields (must match GridCompare dropdown options)
VALID_GRID_FIELDS = {
    'model', 'vae', 'clip', 'lora_name', 'lora_strength', 
    'sampler_name', 'scheduler', 'steps', 'cfg', 'seed',
    'width', 'height', 'prompt_positive', 'prompt_negative',
    'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift', 
    'hunyuan_shift', 'flux_guidance', 'denoise'
}

# Priority weights (used for fallback sorting)
FIELD_PRIORITY = {
    'lora_strength': 100,    # HIGHEST - always columns
    'lora_name': 95,         # Second highest - always rows
    'sampler_name': 90,      # Nest 1
    'model': 85,             # Nest 2
    'prompt_positive': 80,   # Nest 3
    'scheduler': 60,         
    'vae': 55,               
    'clip': 50,
    'steps': 45,             
    'cfg': 40,               
    'denoise': 35,
    'prompt_negative': 30,
    'seed': 5,               
}


@dataclass
class LoraInfo:
    """Information about LoRA configuration."""
    has_or_combinator: bool = False
    lora_names: List[str] = field(default_factory=list)
    lora_strengths: List[float] = field(default_factory=list)
    or_branch_count: int = 0


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
    x_axis: Optional[str] = None       # Column axis
    y_axis: Optional[str] = None       # Row axis
    nest_levels: List[str] = field(default_factory=list)
    backup_split_field: Optional[str] = None
    total_combinations: int = 0
    combinations_per_grid: int = 0
    num_grids: int = 1
    strategy: str = "simple"  # simple, nested, paginated
    explanation: str = ""
    formula_text: str = ""
    warnings: List[str] = field(default_factory=list)
    field_analysis: Dict[str, FieldAnalysis] = field(default_factory=dict)
    lora_info: Optional[LoraInfo] = None


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


def _get_single_entry_variations(items: List[Any], key: str) -> List[Any]:
    """
    Get variations for a key, but ONLY if a single entry contains multiple values.
    
    Multiple sampling_params entries are from different SamplingConfigChain nodes.
    Only if ONE entry has an array with multiple values is it a real variation.
    """
    if not items:
        return []
    
    for item in items:
        if isinstance(item, dict) and key in item:
            val = item[key]
            if isinstance(val, list) and len(val) > 1:
                return _extract_unique_values(val)
    
    return []


def analyze_lora_structure(config: Dict[str, Any]) -> LoraInfo:
    """
    Analyze LoRA configuration for OR/AND combinators.
    
    OR combinator (' ') = each LoRA becomes a separate row
    AND combinator ('+') = all LoRAs applied together in one cell
    """
    result = LoraInfo()
    
    combinations = config.get('combinations', [])
    seen_loras = {}  # name -> set of strengths
    or_branches = set()
    
    for combo in combinations:
        lora_config = combo.get('lora_config', {})
        loras = lora_config.get('loras', [])
        display = lora_config.get('display', '')
        
        # Check for OR indicator
        if ' OR ' in display or lora_config.get('has_or', False):
            result.has_or_combinator = True
        
        for lora in loras:
            name = lora.get('label', lora.get('name', ''))
            strength = lora.get('strength')
            combinator = lora.get('combinator', '+')
            
            if combinator == ' ':  # Space = OR
                result.has_or_combinator = True
                or_branches.add(name)
            
            if name:
                if name not in seen_loras:
                    seen_loras[name] = set()
                if strength is not None:
                    seen_loras[name].add(strength)
    
    # Also check raw lora_config list
    raw_lora_config = config.get('lora_config', [])
    if isinstance(raw_lora_config, list):
        for lora in raw_lora_config:
            if isinstance(lora, dict):
                combinator = lora.get('combinator', '+')
                if combinator == ' ':
                    result.has_or_combinator = True
                name = lora.get('name', lora.get('label', ''))
                if name:
                    or_branches.add(name)
    
    result.lora_names = list(seen_loras.keys())
    all_strengths = set()
    for strengths in seen_loras.values():
        all_strengths.update(strengths)
    result.lora_strengths = sorted(list(all_strengths))
    result.or_branch_count = len(or_branches)
    
    return result


def analyze_from_variation_lists(config: Dict[str, Any]) -> Dict[str, FieldAnalysis]:
    """
    Analyze a configuration with raw variation lists (before combinations are computed).
    """
    analysis: Dict[str, FieldAnalysis] = {}
    
    # Analyze model variations
    model_variations = config.get('model_variations', [])
    if model_variations:
        # Extract model names
        models = _extract_unique_values(model_variations, 'model_name')
        models = [m for m in models if m]
        if len(models) > 1:
            analysis['model'] = FieldAnalysis(
                name='model',
                display_name='Model',
                values=models,
                value_count=len(models),
                priority=FIELD_PRIORITY.get('model', 50),
                is_row_candidate=True,
                is_col_candidate=False,
                is_nest_candidate=True,
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
                is_row_candidate=True,
                is_col_candidate=False,
                is_nest_candidate=True,
            )
    
    # Analyze sampling params
    sampling_params = config.get('sampling_params', [])
    if sampling_params:
        # Samplers
        samplers = _get_single_entry_variations(sampling_params, 'sampler_name')
        if len(samplers) > 1:
            analysis['sampler_name'] = FieldAnalysis(
                name='sampler_name',
                display_name='Sampler',
                values=samplers,
                value_count=len(samplers),
                priority=FIELD_PRIORITY.get('sampler_name', 50),
                is_row_candidate=True,
                is_col_candidate=False,
                is_nest_candidate=True,
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
                is_row_candidate=True,
                is_col_candidate=False,
                is_nest_candidate=True,
            )
        
        # Steps - numeric, good for columns
        steps = _get_single_entry_variations(sampling_params, 'steps')
        if len(steps) > 1:
            analysis['steps'] = FieldAnalysis(
                name='steps',
                display_name='Steps',
                values=steps,
                value_count=len(steps),
                priority=FIELD_PRIORITY.get('steps', 50),
                is_row_candidate=False,
                is_col_candidate=True,
                is_nest_candidate=False,
            )
        
        # CFG - numeric, good for columns
        cfgs = _get_single_entry_variations(sampling_params, 'cfg')
        if len(cfgs) > 1:
            analysis['cfg'] = FieldAnalysis(
                name='cfg',
                display_name='CFG Scale',
                values=cfgs,
                value_count=len(cfgs),
                priority=FIELD_PRIORITY.get('cfg', 50),
                is_row_candidate=False,
                is_col_candidate=True,
                is_nest_candidate=False,
            )
        
        # Denoise
        denoise = _get_single_entry_variations(sampling_params, 'denoise')
        if len(denoise) > 1:
            analysis['denoise'] = FieldAnalysis(
                name='denoise',
                display_name='Denoise',
                values=denoise,
                value_count=len(denoise),
                priority=FIELD_PRIORITY.get('denoise', 50),
                is_row_candidate=False,
                is_col_candidate=True,
                is_nest_candidate=False,
            )
    
    # Analyze LoRA config
    lora_config = config.get('lora_config', [])
    if lora_config:
        # Check for OR mode (space combinator)
        has_or_mode = any(
            lora.get('combinator', '+') == ' ' 
            for lora in lora_config if isinstance(lora, dict)
        )
        
        lora_names = _extract_unique_values(lora_config, 'name')
        lora_names = [n for n in lora_names if n and n != 'None']
        
        if has_or_mode:
            # OR MODE: Each LoRA is a separate branch
            # lora_name IS a varying dimension (each LoRA is a row)
            if len(lora_names) > 1:
                analysis['lora_name'] = FieldAnalysis(
                    name='lora_name',
                    display_name='LoRA',
                    values=lora_names,
                    value_count=len(lora_names),
                    priority=FIELD_PRIORITY.get('lora_name', 50),
                    is_row_candidate=True,  # ALWAYS rows in OR mode
                    is_col_candidate=False,
                    is_nest_candidate=False,
                )
            
            # lora_strength is individual values, not tuples
            # Collect ALL unique strength values across all LoRAs
            all_strengths = set()
            for lora in lora_config:
                if isinstance(lora, dict):
                    for key in ['strengths', 'strength_model', 'strength_clip', 'strength']:
                        val = lora.get(key, [])
                        if isinstance(val, list):
                            all_strengths.update(val)
                        elif val is not None:
                            all_strengths.add(val)
            
            sorted_strengths = sorted([s for s in all_strengths if s is not None])
            if len(sorted_strengths) > 1:
                analysis['lora_strength'] = FieldAnalysis(
                    name='lora_strength',
                    display_name='LoRA Strength',
                    values=sorted_strengths,  # Individual values, not tuples
                    value_count=len(sorted_strengths),
                    priority=FIELD_PRIORITY.get('lora_strength', 100),
                    is_row_candidate=False,
                    is_col_candidate=True,  # ALWAYS columns
                    is_nest_candidate=False,
                )
        else:
            # AND MODE: All LoRAs applied together
            # lora_name is NOT a varying dimension (same LoRAs in every combo)
            # (don't add to analysis)
            
            # LoRA strengths - compute the CARTESIAN PRODUCT of all LoRA strengths
            # This gives us the actual number of unique strength tuples
            # e.g., 3 LoRAs with [0,1] each = 2^3 = 8 unique tuples
            strength_lists = []
            for lora in lora_config:
                if isinstance(lora, dict):
                    strengths = None
                    for key in ['strengths', 'strength_model', 'strength_clip', 'strength']:
                        val = lora.get(key, [])
                        if isinstance(val, list) and val:
                            strengths = val
                            break
                        elif val is not None and not isinstance(val, list):
                            strengths = [val]
                            break
                    if strengths:
                        strength_lists.append(strengths)
            
            if strength_lists:
                # Compute cartesian product to get all unique strength tuples
                strength_tuples = list(itertools.product(*strength_lists))
                if len(strength_tuples) > 1:
                    analysis['lora_strength'] = FieldAnalysis(
                        name='lora_strength',
                        display_name='LoRA Strength',
                        values=strength_tuples,  # Store actual tuples
                        value_count=len(strength_tuples),
                        priority=FIELD_PRIORITY.get('lora_strength', 100),
                        is_row_candidate=False,
                        is_col_candidate=True,  # ALWAYS columns
                        is_nest_candidate=False,
                    )
    
    # Analyze prompt variations
    prompt_variations = config.get('prompt_variations', [])
    if prompt_variations and len(prompt_variations) > 1:
        prompt_labels = [f"Prompt {i+1}" for i in range(len(prompt_variations))]
        analysis['prompt_positive'] = FieldAnalysis(
            name='prompt_positive',
            display_name='Prompt',
            values=prompt_labels,
            value_count=len(prompt_variations),
            priority=FIELD_PRIORITY.get('prompt_positive', 80),
            is_row_candidate=True,
            is_col_candidate=False,
            is_nest_candidate=True,
        )
    
    return analysis


def analyze_from_combinations(combinations: List[Dict[str, Any]], config: Dict[str, Any] = None) -> Dict[str, FieldAnalysis]:
    """
    Analyze from pre-computed combinations array with proper LoRA extraction.
    """
    if not combinations:
        return {}
    
    analysis: Dict[str, FieldAnalysis] = {}
    field_values: Dict[str, Set] = {f: set() for f in VALID_GRID_FIELDS}
    
    for combo in combinations:
        if not isinstance(combo, dict):
            continue
        
        # Extract sampling override values
        override = combo.get('_sampling_override', {})
        
        # Model
        model_idx = combo.get('model_index', 0)
        model_vars = (config or {}).get('model_variations', [])
        if model_idx < len(model_vars):
            model_entry = model_vars[model_idx]
            model_name = model_entry.get('display_name', model_entry.get('name', ''))
            if model_name:
                if model_name.endswith('.safetensors'):
                    model_name = model_name[:-12]
                field_values['model'].add(model_name)
        
        # VAE
        vae_name = combo.get('vae_name', '')
        if vae_name:
            if vae_name.endswith('.safetensors'):
                vae_name = vae_name[:-12]
            field_values['vae'].add(vae_name)
        
        # LoRA - extract strength TUPLES and check for OR mode
        # IMPORTANT: We store lora_strength as a TUPLE of all LoRA strengths,
        # not individual strength values. This makes each unique combination
        # (like (0,0,1) vs (0,1,0)) a separate grid column.
        #
        # lora_name is ONLY a varying dimension in OR mode (different LoRAs
        # in different combinations). In AND mode (all LoRAs applied together),
        # lora_name should NOT be a grid axis.
        lora_config = combo.get('lora_config', {})
        loras = lora_config.get('loras', [])
        
        # Collect the SET of LoRA names for this combo (as a frozen set for hashing)
        # This way, we can detect if different combos have different LoRA sets (OR mode)
        combo_lora_names = frozenset(
            lora.get('label', lora.get('name', '')) for lora in loras if lora.get('label', lora.get('name', ''))
        )
        if combo_lora_names:
            field_values['lora_name'].add(combo_lora_names)
        
        # Collect strength TUPLE (not individual values)
        if loras:
            strengths = tuple(lora.get('strength', 1.0) for lora in loras)
            field_values['lora_strength'].add(strengths)
        
        # Sampling params from override or combo
        for field in ['sampler_name', 'scheduler', 'steps', 'cfg', 'denoise', 'seed',
                     'width', 'height', 'lumina_shift', 'qwen_shift', 'wan_shift',
                     'wan22_shift', 'hunyuan_shift', 'flux_guidance']:
            value = override.get(field, combo.get(field))
            if value is not None:
                field_values[field].add(value)
        
        # Prompts
        for field in ['prompt_positive', 'prompt_negative']:
            value = combo.get(field)
            if value:
                # Truncate long prompts for display
                if len(value) > 50:
                    value = value[:47] + "..."
                field_values[field].add(value)
    
    # Create FieldAnalysis for fields with >1 unique value
    for field_name, values in field_values.items():
        if len(values) > 1:
            # Convert frozensets to readable strings for lora_name
            if field_name == 'lora_name':
                # Convert each frozenset to a joined string for display
                display_values = []
                for v in values:
                    if isinstance(v, frozenset):
                        # Sort for consistent display, join with ' + '
                        display_values.append(' + '.join(sorted(v)))
                    else:
                        display_values.append(v)
                try:
                    sorted_values = sorted(display_values)
                except TypeError:
                    sorted_values = display_values
            else:
                try:
                    sorted_values = sorted(list(values))
                except TypeError:
                    sorted_values = list(values)
            
            # Determine axis candidacy based on NEW rules
            is_row = field_name in AXIS_PREFERRED_ROW or field_name == 'lora_name'
            is_col = field_name in AXIS_PREFERRED_COLUMN or field_name == 'lora_strength'
            is_nest = field_name in NEST_PRIORITY
            
            analysis[field_name] = FieldAnalysis(
                name=field_name,
                display_name=_get_display_name(field_name),
                values=sorted_values,
                value_count=len(sorted_values),
                priority=FIELD_PRIORITY.get(field_name, 50),
                is_row_candidate=is_row,
                is_col_candidate=is_col,
                is_nest_candidate=is_nest,
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
    lora_info: LoraInfo,
    max_per_grid: int = 64,
    client_estimated_combinations: Optional[int] = None
) -> LayoutRecommendation:
    """
    Generate optimal grid layout using the NEW FORMULA algorithm.
    
    Rules (in order of priority):
    1. lora_strength → ALWAYS columns when varying (shows progression left→right)
    2. lora_name → ALWAYS rows when OR combinator used OR when multiple loras
    3. Remaining fields assigned to row/col/nest by priority
    4. Split by backup_split_field when grid exceeds limits
    """
    if not analysis:
        return LayoutRecommendation(
            explanation="No varying fields detected. Using default layout."
        )
    
    # Use client estimate if provided
    if client_estimated_combinations and client_estimated_combinations > 0:
        total_combos = client_estimated_combinations
    else:
        total_combos = calculate_total_combinations(analysis)
    
    result = LayoutRecommendation()
    result.total_combinations = total_combos
    result.field_analysis = analysis
    result.lora_info = lora_info
    
    used_fields = set()
    
    # ==========================================================================
    # RULE 1: LoRA strength MUST be columns when varying (HIGHEST PRIORITY)
    # This shows the gradual effect of the LoRA as strength increases left→right
    # ==========================================================================
    if 'lora_strength' in analysis and analysis['lora_strength'].value_count > 1:
        result.x_axis = 'lora_strength'
        used_fields.add('lora_strength')
        print(f"[GridPresetAnalyzer] RULE 1: lora_strength → columns ({analysis['lora_strength'].value_count} values)")
    
    # ==========================================================================
    # RULE 2: LoRA name MUST be rows when OR combinator or multiple loras
    # ==========================================================================
    if lora_info.has_or_combinator and len(lora_info.lora_names) > 1:
        result.y_axis = 'lora_name'
        used_fields.add('lora_name')
        print(f"[GridPresetAnalyzer] RULE 2: lora_name → rows (OR combinator, {len(lora_info.lora_names)} loras)")
    elif 'lora_name' in analysis and analysis['lora_name'].value_count > 1:
        # Even without OR combinator, multiple lora_names should be rows
        result.y_axis = 'lora_name'
        used_fields.add('lora_name')
        print(f"[GridPresetAnalyzer] RULE 2b: lora_name → rows ({analysis['lora_name'].value_count} values)")
    
    # ==========================================================================
    # RULE 3: Fill remaining axes with preferred candidates
    # ==========================================================================
    
    # If no column axis yet, use preferred columns (numeric progressions work best)
    if result.x_axis is None:
        for field in AXIS_PREFERRED_COLUMN:
            if field in analysis and field not in used_fields:
                result.x_axis = field
                used_fields.add(field)
                print(f"[GridPresetAnalyzer] RULE 3a: {field} → columns (preferred)")
                break
    
    # If no row axis yet, use preferred rows
    if result.y_axis is None:
        for field in AXIS_PREFERRED_ROW:
            if field in analysis and field not in used_fields:
                result.y_axis = field
                used_fields.add(field)
                print(f"[GridPresetAnalyzer] RULE 3b: {field} → rows (preferred)")
                break
    
    # Fallback: use any remaining varying field
    remaining = [f for f in analysis if f not in used_fields]
    remaining.sort(key=lambda f: analysis[f].priority, reverse=True)
    
    if result.x_axis is None and remaining:
        field = remaining.pop(0)
        result.x_axis = field
        used_fields.add(field)
        print(f"[GridPresetAnalyzer] RULE 3c: {field} → columns (fallback)")
    
    if result.y_axis is None and remaining:
        field = remaining.pop(0)
        result.y_axis = field
        used_fields.add(field)
        print(f"[GridPresetAnalyzer] RULE 3d: {field} → rows (fallback)")
    
    # ==========================================================================
    # RULE 4: Assign nest levels by NEST_PRIORITY
    # ==========================================================================
    
    # Calculate max_nests based on NUMBER OF VARYING DIMENSIONS, not just combo count
    # This ensures all dimensions get assigned to axes (row, col, or nest)
    num_varying_dims = len(analysis)
    num_unassigned = num_varying_dims - len(used_fields)  # Dimensions not yet assigned to row/col
    
    # We need enough nest levels to cover ALL remaining dimensions
    # Otherwise we get grid cell collisions and lose images
    if num_unassigned <= 0:
        max_nests = 0
    elif num_unassigned <= 2:
        max_nests = num_unassigned
    elif num_unassigned <= 6:
        max_nests = num_unassigned  # All remaining dims become nest levels
    else:
        max_nests = 6  # Cap at 6 for reasonable display, use pagination beyond
    
    # Also consider combo count for reasonable grid sizes
    # But prioritize dimension coverage to prevent image loss
    if total_combos <= 25 and num_varying_dims <= 2:
        max_nests = 0  # Simple grid is fine for small counts with few dimensions
    
    print(f"[GridPresetAnalyzer] Dimension analysis: {num_varying_dims} varying, {len(used_fields)} assigned to row/col, {num_unassigned} need nesting")
    print(f"[GridPresetAnalyzer] Setting max_nests={max_nests} (was combo-based, now dimension-based)")
    
    result.nest_levels = []
    for field in NEST_PRIORITY:
        if len(result.nest_levels) >= max_nests:
            break
        if field in analysis and field not in used_fields:
            result.nest_levels.append(field)
            used_fields.add(field)
            print(f"[GridPresetAnalyzer] RULE 4: {field} → nest level {len(result.nest_levels)}")
    
    # ==========================================================================
    # RULE 5: Set backup split field
    # ==========================================================================
    if result.nest_levels:
        result.backup_split_field = result.nest_levels[0]
    elif result.y_axis:
        result.backup_split_field = result.y_axis
    else:
        result.backup_split_field = 'model' if 'model' in analysis else None
    
    # ==========================================================================
    # Calculate grid metrics
    # ==========================================================================
    row_count = analysis[result.y_axis].value_count if result.y_axis and result.y_axis in analysis else 1
    col_count = analysis[result.x_axis].value_count if result.x_axis and result.x_axis in analysis else 1
    result.combinations_per_grid = row_count * col_count
    
    nest_multiplier = 1
    for nest_field in result.nest_levels:
        if nest_field in analysis:
            nest_multiplier *= analysis[nest_field].value_count
    result.num_grids = nest_multiplier
    
    # Determine strategy
    if result.nest_levels:
        result.strategy = f"nested_{len(result.nest_levels)}"
    else:
        result.strategy = "simple"
    
    if result.combinations_per_grid > max_per_grid:
        result.strategy = "paginated"
        result.warnings.append(
            f"Inner grid has {result.combinations_per_grid} images, exceeds limit of {max_per_grid}. "
            f"Will split by {result.backup_split_field}."
        )
    
    if total_combos > 500:
        result.warnings.append(
            f"Large grid with {total_combos} combinations. Consider reducing variations."
        )
    
    # Build explanation
    parts = []
    if result.nest_levels:
        nest_names = [analysis[n].display_name for n in result.nest_levels if n in analysis]
        parts.append(f"Nest: {' → '.join(nest_names)}")
    if result.y_axis:
        parts.append(f"Rows: {analysis[result.y_axis].display_name if result.y_axis in analysis else result.y_axis}")
    if result.x_axis:
        parts.append(f"Cols: {analysis[result.x_axis].display_name if result.x_axis in analysis else result.x_axis}")
    parts.append(f"Total: {total_combos} images in {result.num_grids} grid(s)")
    
    result.explanation = " | ".join(parts)
    
    # Generate formula text
    result.formula_text = _generate_formula_text(result, analysis, lora_info)
    
    return result


def _generate_formula_text(
    result: LayoutRecommendation,
    analysis: Dict[str, FieldAnalysis],
    lora_info: LoraInfo
) -> str:
    """Generate code-like formula text for display."""
    lines = [
        "# Grid Layout Formula v2.0",
        "",
        "# Input Analysis:",
        f"total_combinations = {result.total_combinations}",
        f"varying_fields = {list(analysis.keys())}",
        "",
    ]
    
    if lora_info.lora_names:
        lines.extend([
            "# LoRA Analysis:",
            f"lora_names = {lora_info.lora_names}",
            f"lora_strengths = {lora_info.lora_strengths}",
            f"has_or_combinator = {lora_info.has_or_combinator}",
            "",
        ])
    
    lines.extend([
        "# Axis Assignment Rules:",
    ])
    
    if result.x_axis == 'lora_strength':
        lines.append("IF 'lora_strength' IN varying THEN x_axis = 'lora_strength'  # Progression left→right")
    elif result.x_axis:
        lines.append(f"x_axis = '{result.x_axis}'")
    
    if result.y_axis == 'lora_name' and lora_info.has_or_combinator:
        lines.append("IF has_or_combinator THEN y_axis = 'lora_name'  # One LoRA per row")
    elif result.y_axis:
        lines.append(f"y_axis = '{result.y_axis}'")
    
    if result.nest_levels:
        lines.append("")
        lines.append("# Nest Levels (outer → inner):")
        for i, nest in enumerate(result.nest_levels):
            lines.append(f"nest_{i+1} = '{nest}'")
    
    lines.extend([
        "",
        "# Result:",
        f"strategy = '{result.strategy}'",
        f"images_per_grid = {result.combinations_per_grid}",
        f"num_grids = {result.num_grids}",
    ])
    
    if result.backup_split_field:
        lines.append(f"backup_split_field = '{result.backup_split_field}'")
    
    if result.warnings:
        lines.extend(["", "# Warnings:"])
        for warning in result.warnings:
            lines.append(f"# ⚠️ {warning}")
    
    return "\n".join(lines)


def analyze_config(config: Dict[str, Any], max_per_grid: int = 64) -> LayoutRecommendation:
    """
    Main entry point: analyze a configuration and return layout recommendation.
    
    Works with both pre-computed combinations and raw variation lists.
    Uses client-side _estimated_combinations when available.
    """
    # Analyze LoRA structure first
    lora_info = analyze_lora_structure(config)
    
    # Then analyze field variations
    combinations = config.get('combinations', [])
    
    if combinations:
        analysis = analyze_from_combinations(combinations, config)
    else:
        analysis = analyze_from_variation_lists(config)
    
    # Get client-side estimated combinations if available
    client_estimate = config.get('_estimated_combinations')
    
    return generate_optimal_layout(analysis, lora_info, max_per_grid, client_estimate)


def _get_display_name(canonical: str) -> str:
    """Get display name for canonical field name."""
    display_names = {
        'model': 'Model',
        'vae': 'VAE',
        'clip': 'CLIP',
        'sampler_name': 'Sampler',
        'scheduler': 'Scheduler',
        'steps': 'Steps',
        'cfg': 'CFG',
        'denoise': 'Denoise',
        'prompt_positive': 'Prompt',
        'prompt_negative': 'Neg Prompt',
        'lora_name': 'LoRA',
        'lora_strength': 'LoRA Strength',
        'seed': 'Seed',
        'width': 'Width',
        'height': 'Height',
        'lumina_shift': 'Lumina Shift',
        'qwen_shift': 'Qwen Shift',
        'wan_shift': 'WAN Shift',
        'wan22_shift': 'WAN 2.2 Shift',
        'hunyuan_shift': 'Hunyuan Shift',
        'flux_guidance': 'FLUX Guidance',
    }
    
    return display_names.get(canonical, canonical.replace('_', ' ').title())


def _canonicalize_field_name(name: str) -> str:
    """Convert field name to canonical form that matches GridCompare dropdown options."""
    name_lower = name.lower()
    
    mappings = {
        'model_name': 'model',
        'checkpoint': 'model',
        'vae_name': 'vae',
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
