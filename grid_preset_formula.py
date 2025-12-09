"""
Grid Preset Formula Node

Analyzes model comparison configurations and outputs optimal grid layout settings
using a weighted priority algorithm for hierarchical pivot-table rendering.

The formula determines:
- row_hierarchy: List of fields for row grouping (outer → inner)
- col_hierarchy: List of fields for column grouping (outer → inner)

Weighting Logic:
- Higher weight = innermost (leaf, adjacent to images)
- Lower weight = outermost (container, big grouped headers)
- Dimensions are sorted by weight and distributed alternating between col/row
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

# Import shared utilities
from .grid_utils import (
    expand_combinations_with_lora_modes,
    detect_varying_dimensions as utils_detect_varying_dimensions,
    get_combo_field_value as utils_get_combo_field_value,
    get_dimension_weight,
    clean_lora_name,
)


# =============================================================================
# VALID GRID FIELDS
# =============================================================================

VALID_GRID_FIELDS = {
    'model', 'vae', 'clip', 'lora_name', 'lora_strength', 'lora_group_label',
    'sampler_name', 'scheduler', 'steps', 'cfg', 'seed',
    'width', 'height', 'prompt_positive', 'prompt_negative',
    'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift', 
    'hunyuan_shift', 'flux_guidance', 'denoise'
}


@dataclass
class LayoutResult:
    """
    Result of layout analysis with hierarchical row/column structure.
    
    Hierarchies are ordered from OUTERMOST (container) to INNERMOST (leaf/adjacent to images).
    Example: row_hierarchy = ['model', 'sampler_name'] means:
        - 'model' is the outer row grouping (big container headers)
        - 'sampler_name' is the inner row grouping (directly next to images)
    
    The hierarchy order is determined by priority weights:
        - Lowest weight = outermost (container)
        - Highest weight = innermost (leaf)
    """
    row_hierarchy: List[str] = field(default_factory=list)  # Ordered outer→inner
    col_hierarchy: List[str] = field(default_factory=list)  # Ordered outer→inner
    backup_split_field: Optional[str] = None
    total_combinations: int = 0
    strategy: str = "hierarchical"
    formula_text: str = ""
    explanation: str = ""
    warnings: List[str] = field(default_factory=list)
    # Metadata for debugging/display
    detected_dimensions: List[str] = field(default_factory=list)
    dimension_weights: Dict[str, int] = field(default_factory=dict)


class GridPresetFormula:
    """
    Analyzes configuration and outputs optimal grid layout with hierarchical structure.
    
    NEW Weighted Hierarchy Logic:
    1. Detect all varying dimensions from the configuration
    2. Apply priority weights to each dimension (higher weight = innermost/leaf)
    3. Sort dimensions by weight ASCENDING (lowest = outermost container)
    4. Distribute to row_hierarchy and col_hierarchy alternating (highest→col, 2nd→row, 3rd→col, etc.)
    5. If force_row_axis or force_col_axis is set, lock that dimension to that axis
    
    Output:
    - row_hierarchy: List of fields ordered outer→inner for row headers
    - col_hierarchy: List of fields ordered outer→inner for column headers
    """
    
    CATEGORY = "Model Compare/Grid"
    
    # Default priority weights (higher = innermost/leaf, lower = outermost/container)
    DEFAULT_WEIGHTS = {
        'lora_strength': 100,    # HIGHEST - always innermost columns
        'lora_name': 95,         # Second highest
        'cfg': 90,
        'steps': 88,
        'sampler_name': 85,
        'denoise': 82,
        'scheduler': 80,
        'model': 70,             # Models are usually outer containers
        'vae': 65,
        'clip': 60,
        'prompt_positive': 50,   # Prompts as outer grouping
        'prompt_negative': 45,
        'width': 40,
        'height': 38,
        'seed': 10,              # Seed usually least important for visual grouping
    }
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "max_images_per_grid": ("INT", {
                    "default": 500,
                    "min": 4,
                    "max": 2000,
                    "step": 4,
                    "tooltip": "Maximum images before splitting into multiple grids"
                }),
            },
            "optional": {
                # Explicit axis locks - these override auto-sorting
                "force_row_axis": (["auto", "model", "vae", "clip", "lora_name", 
                                   "sampler_name", "scheduler", "prompt_positive", "prompt_negative"], {
                    "default": "auto",
                    "tooltip": "Lock specific field to row hierarchy (innermost row level)"
                }),
                "force_col_axis": (["auto", "lora_strength", "cfg", "steps", 
                                   "denoise", "width", "height", "sampler_name", "scheduler"], {
                    "default": "auto",
                    "tooltip": "Lock specific field to column hierarchy (innermost column level)"
                }),
                
                # Priority weights - higher weight = more inner (closer to images)
                "lora_strength_weight": ("INT", {
                    "default": 100,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for lora_strength (higher = innermost)"
                }),
                "lora_name_weight": ("INT", {
                    "default": 95,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for lora_name"
                }),
                "sampler_weight": ("INT", {
                    "default": 85,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for sampler_name"
                }),
                "model_weight": ("INT", {
                    "default": 70,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for model"
                }),
                "scheduler_weight": ("INT", {
                    "default": 80,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for scheduler"
                }),
                "cfg_weight": ("INT", {
                    "default": 90,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for cfg"
                }),
                "steps_weight": ("INT", {
                    "default": 88,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for steps"
                }),
                "prompt_weight": ("INT", {
                    "default": 50,
                    "min": 0,
                    "max": 100,
                    "tooltip": "Priority weight for prompt variations"
                }),
            },
        }
    
    RETURN_TYPES = ("GRID_LAYOUT", "STRING", "STRING")
    RETURN_NAMES = ("layout", "formula", "explanation")
    FUNCTION = "analyze"
    
    def analyze(
        self,
        config: Dict[str, Any],
        max_images_per_grid: int,
        force_row_axis: str = "auto",
        force_col_axis: str = "auto",
        lora_strength_weight: int = 100,
        lora_name_weight: int = 95,
        sampler_weight: int = 85,
        model_weight: int = 70,
        scheduler_weight: int = 80,
        cfg_weight: int = 90,
        steps_weight: int = 88,
        prompt_weight: int = 50,
    ) -> Tuple[Dict, str, str]:
        """
        Analyze configuration and return optimal hierarchical layout.
        
        NEW Algorithm:
        1. Detect varying dimensions from combinations
        2. Build weight map from user inputs + defaults
        3. Lock forced axes if specified
        4. Sort remaining by weight, distribute: highest→col, 2nd→row, 3rd→col, etc.
        5. Output row_hierarchy and col_hierarchy for pivot-table rendering
        """
        
        # Step 1: Extract varying dimensions
        # IMPORTANT: Expand combinations with LoRA modes before detection
        combinations = config.get('combinations', [])
        
        # Expand LoRA variations using shared utility
        expanded_combinations = expand_combinations_with_lora_modes(combinations, config)
        print(f"[GridPresetFormula] Expanded {len(combinations)} -> {len(expanded_combinations)} combinations")
        
        varying = self._detect_varying_dimensions(expanded_combinations, config)
        print(f"[GridPresetFormula] Detected {len(varying)} varying dimensions: {list(varying.keys())}")
        
        # Step 2: Build weight map from user inputs
        user_weights = {
            'lora_strength': lora_strength_weight,
            'lora_name': lora_name_weight,
            'sampler_name': sampler_weight,
            'model': model_weight,
            'scheduler': scheduler_weight,
            'cfg': cfg_weight,
            'steps': steps_weight,
            'prompt_positive': prompt_weight,
            'prompt_negative': prompt_weight - 5,
        }
        
        # Merge with defaults (user weights take precedence)
        weights = {**self.DEFAULT_WEIGHTS, **user_weights}
        
        # Add weights for dynamically created per-LoRA dimensions
        # Per-LoRA strength dimensions inherit from lora_strength_weight
        # Per-LoRA name dimensions inherit from lora_name_weight  
        for dim_name in varying.keys():
            if dim_name.endswith('_strength') and dim_name not in weights:
                weights[dim_name] = lora_strength_weight
                print(f"[GridPresetFormula] Dynamic dimension '{dim_name}' assigned weight {lora_strength_weight}")
            elif dim_name.endswith('_name') and dim_name.startswith('lora') and dim_name not in weights:
                weights[dim_name] = lora_name_weight
                print(f"[GridPresetFormula] Dynamic dimension '{dim_name}' assigned weight {lora_name_weight}")
        
        # Step 3: Calculate total combinations
        total_combos = len(combinations) if combinations else self._estimate_combinations(config)
        
        # Step 4: Generate hierarchical layout
        result = self._build_hierarchical_layout(
            varying=varying,
            weights=weights,
            total_combos=total_combos,
            max_per_grid=max_images_per_grid,
            force_row=force_row_axis,
            force_col=force_col_axis,
        )
        
        # Step 5: Generate formula text
        formula_text = self._generate_formula_text(result, varying, weights)
        
        # Step 6: Build layout dict for GridCompare
        # Include varying_dims with actual values so GridCompare can reconstruct combinations
        varying_dims_with_values = {}
        for field, values in varying.items():
            varying_dims_with_values[field] = {
                'values': values,
                'count': len(values)
            }
        
        layout_dict = {
            'row_hierarchy': result.row_hierarchy,
            'col_hierarchy': result.col_hierarchy,
            'backup_split_field': result.backup_split_field,
            'total_combinations': result.total_combinations,
            'strategy': result.strategy,
            'warnings': result.warnings,
            'detected_dimensions': result.detected_dimensions,
            'dimension_weights': result.dimension_weights,
            'varying_dims': varying_dims_with_values,  # Include actual values for grid reconstruction
        }
        
        print(f"[GridPresetFormula] Layout: rows={result.row_hierarchy}, cols={result.col_hierarchy}")
        
        return (layout_dict, formula_text, result.explanation)
    
    def _detect_varying_dimensions(
        self, combinations: List[Dict], config: Dict
    ) -> Dict[str, List[Any]]:
        """
        Detect which fields have multiple unique values.
        
        For multi-LoRA AND mode setups:
        - Creates separate dimensions for each LoRA's name and strength
        - e.g., 'lora1_name', 'lora1_strength', 'lora2_name', 'lora2_strength'
        - This allows proper 2D matrix display (LoRA1 strength × LoRA2 strength)
        """
        if not combinations:
            return {}
        
        field_values = {f: set() for f in VALID_GRID_FIELDS}
        model_variations = config.get('model_variations', [])
        
        # Track per-LoRA dimensions for multi-LoRA AND mode
        per_lora_names = {}  # lora_index -> set of names
        per_lora_strengths = {}  # lora_index -> set of strengths
        num_loras_in_combo = 0
        
        for combo in combinations:
            override = combo.get('_sampling_override', {})
            
            # Model
            model_idx = combo.get('model_index', 0)
            if model_idx < len(model_variations):
                model_entry = model_variations[model_idx]
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
            
            # LoRA - track per-LoRA dimensions for multi-LoRA setups
            lora_config = combo.get('lora_config', {})
            loras = lora_config.get('loras', [])
            
            if loras:
                num_loras_in_combo = max(num_loras_in_combo, len(loras))
                
                for i, lora in enumerate(loras):
                    # Track name per LoRA slot
                    if i not in per_lora_names:
                        per_lora_names[i] = set()
                    name = lora.get('label', lora.get('name', ''))
                    if name:
                        # Clean up name
                        if '\\' in name:
                            name = name.split('\\')[-1]
                        if name.endswith('.safetensors'):
                            name = name[:-12]
                        per_lora_names[i].add(name)
                    
                    # Track strength per LoRA slot
                    if i not in per_lora_strengths:
                        per_lora_strengths[i] = set()
                    strength = lora.get('strength', 1.0)
                    per_lora_strengths[i].add(strength)
            
            # Sampling params
            for field in ['sampler_name', 'scheduler', 'steps', 'cfg', 'denoise', 'seed',
                         'width', 'height', 'lumina_shift', 'qwen_shift', 'wan_shift',
                         'wan22_shift', 'hunyuan_shift', 'flux_guidance']:
                value = override.get(field, combo.get(field))
                if value is not None:
                    field_values[field].add(value)
            
            # LoRA top-level fields (set by expand_combinations_with_lora_modes)
            # IMPORTANT: These are set on expanded combos for OR/AND mode support
            for field in ['lora_name', 'lora_strength', 'lora_group_label']:
                value = combo.get(field)
                if value is not None:
                    # Handle tuple strengths for AND mode
                    if isinstance(value, (list, tuple)):
                        value = tuple(value)  # Make hashable
                    field_values[field].add(value)
            
            # Prompts
            for field in ['prompt_positive', 'prompt_negative']:
                value = combo.get(field)
                if value:
                    field_values[field].add(value)
        
        # Return only fields with >1 value
        varying = {}
        for field, values in field_values.items():
            if len(values) > 1:
                try:
                    varying[field] = sorted(list(values))
                except TypeError:
                    varying[field] = list(values)
        
        # Process per-LoRA dimensions for multi-LoRA AND mode
        # If we have multiple LoRAs with varying strengths, create separate dimensions
        if num_loras_in_combo > 1:
            # Check if individual LoRAs have varying strengths
            has_per_lora_strength_variation = any(
                len(strengths) > 1 for strengths in per_lora_strengths.values()
            )
            
            if has_per_lora_strength_variation:
                # Create separate dimension for each LoRA's strength
                for i in sorted(per_lora_strengths.keys()):
                    strengths = per_lora_strengths[i]
                    if len(strengths) > 1:
                        # Get the LoRA name for this slot
                        lora_names_for_slot = per_lora_names.get(i, set())
                        lora_label = list(lora_names_for_slot)[0] if len(lora_names_for_slot) == 1 else f"LoRA{i+1}"
                        
                        # Use lora name as the dimension key for better readability
                        dim_key = f"{lora_label}_strength"
                        varying[dim_key] = sorted(list(strengths))
                        
                        print(f"[GridPresetFormula] Created per-LoRA dimension: {dim_key} = {varying[dim_key]}")
                
                # Also track individual LoRA names if they vary
                for i in sorted(per_lora_names.keys()):
                    names = per_lora_names[i]
                    if len(names) > 1:
                        dim_key = f"lora{i+1}_name"
                        varying[dim_key] = sorted(list(names))
                        print(f"[GridPresetFormula] Created per-LoRA name dimension: {dim_key} = {varying[dim_key]}")
        
        # Debug: show what was detected
        print(f"[GridPresetFormula] Detected varying dimensions: {list(varying.keys())}")
        for k, v in varying.items():
            if len(v) <= 5:
                print(f"[GridPresetFormula]   {k}: {v}")
            else:
                print(f"[GridPresetFormula]   {k}: {len(v)} values")
        
        return varying
    
    def _estimate_combinations(self, config: Dict) -> int:
        """Estimate total combinations from config structure."""
        total = 1
        
        model_vars = config.get('model_variations', [])
        if model_vars:
            total *= len(model_vars)
        
        prompt_vars = config.get('prompt_variations', [])
        if prompt_vars:
            total *= len(prompt_vars)
        
        # Rough estimate for other variations
        sampling_params = config.get('sampling_params', [])
        if sampling_params:
            for param in sampling_params:
                if isinstance(param, dict):
                    for key in ['sampler_name', 'scheduler', 'steps', 'cfg']:
                        val = param.get(key)
                        if isinstance(val, list) and len(val) > 1:
                            total *= len(val)
        
        return max(1, total)
    
    def _build_hierarchical_layout(
        self,
        varying: Dict[str, List],
        weights: Dict[str, int],
        total_combos: int,
        max_per_grid: int,
        force_row: str,
        force_col: str,
    ) -> LayoutResult:
        """
        Build hierarchical layout using weighted sorting algorithm.
        
        Algorithm:
        1. If force_row_axis is set (not "auto"), lock it to innermost row
        2. If force_col_axis is set (not "auto"), lock it to innermost column
        3. Sort remaining dimensions by weight DESCENDING (highest first)
        4. Distribute alternating: 1st→col (innermost), 2nd→row (innermost), 
           3rd→col (2nd inner), 4th→row (2nd inner), etc.
        5. Result: hierarchies are ordered outer→inner
        
        Args:
            varying: Dict of field → list of unique values
            weights: Dict of field → priority weight (higher = inner)
            total_combos: Total number of image combinations
            max_per_grid: Max images before splitting
            force_row: Field to lock to row axis ("auto" for none)
            force_col: Field to lock to column axis ("auto" for none)
        
        Returns:
            LayoutResult with row_hierarchy and col_hierarchy populated
        """
        result = LayoutResult()
        result.total_combinations = total_combos
        result.detected_dimensions = list(varying.keys())
        result.dimension_weights = {f: weights.get(f, 50) for f in varying.keys()}
        
        # Track which fields have been assigned
        used_fields = set()
        
        # Hierarchies will be built inner→outer, then reversed at the end
        row_inner_to_outer = []
        col_inner_to_outer = []
        
        # Helper: Map generic field names to per-LoRA dimensions
        def map_to_per_lora(field_name: str) -> List[str]:
            """Map lora_strength/lora_name to matching per-LoRA dimensions."""
            if field_name == "lora_strength":
                # Return all *_strength dimensions (except lora_strength itself)
                return [f for f in varying.keys() if f.endswith('_strength') and f != 'lora_strength']
            elif field_name == "lora_name":
                # Return all *_name dimensions for LoRAs
                return [f for f in varying.keys() if f.endswith('_name') and f.startswith('lora')]
            return [field_name] if field_name in varying else []
        
        # Step 1: Lock forced axes to innermost position
        # Handle mapping for per-LoRA dimensions
        if force_row != "auto":
            mapped = map_to_per_lora(force_row)
            if mapped:
                # Lock ALL matching dimensions to row (innermost first)
                for m in mapped:
                    if m not in used_fields:
                        row_inner_to_outer.append(m)
                        used_fields.add(m)
                        print(f"[GridPresetFormula] Locked '{m}' (mapped from '{force_row}') to innermost row")
            elif force_row in varying:
                row_inner_to_outer.append(force_row)
                used_fields.add(force_row)
                print(f"[GridPresetFormula] Locked '{force_row}' to innermost row")
        
        if force_col != "auto":
            mapped = map_to_per_lora(force_col)
            if mapped:
                # Lock ALL matching dimensions to col (innermost first)
                for m in mapped:
                    if m not in used_fields:
                        col_inner_to_outer.append(m)
                        used_fields.add(m)
                        print(f"[GridPresetFormula] Locked '{m}' (mapped from '{force_col}') to innermost col")
            elif force_col in varying:
                col_inner_to_outer.append(force_col)
                used_fields.add(force_col)
                print(f"[GridPresetFormula] Locked '{force_col}' to innermost column")
        
        # Step 2: Sort remaining dimensions by weight DESCENDING (highest = will be assigned first = innermost)
        remaining = [f for f in varying.keys() if f not in used_fields]
        remaining.sort(key=lambda f: weights.get(f, 50), reverse=True)
        
        print(f"[GridPresetFormula] Remaining dimensions sorted by weight (desc): {remaining}")
        print(f"[GridPresetFormula] Weights: {[(f, weights.get(f, 50)) for f in remaining]}")
        
        # Step 3: Distribute alternating - col first (if no forced col), then row, then col, etc.
        # This creates the most balanced "square-ish" grid
        assign_to_col = len(col_inner_to_outer) == 0  # Start with col if no forced col
        
        for field in remaining:
            if assign_to_col:
                col_inner_to_outer.append(field)
                print(f"[GridPresetFormula] Assigned '{field}' (weight={weights.get(field, 50)}) → column hierarchy")
            else:
                row_inner_to_outer.append(field)
                print(f"[GridPresetFormula] Assigned '{field}' (weight={weights.get(field, 50)}) → row hierarchy")
            assign_to_col = not assign_to_col
        
        # Step 4: Reverse to get outer→inner ordering
        # The first field assigned (highest weight) becomes innermost
        # After reversal, it's at the end of the list (inner position)
        result.row_hierarchy = list(reversed(row_inner_to_outer))
        result.col_hierarchy = list(reversed(col_inner_to_outer))
        
        # Step 5: Calculate grid metrics
        row_count = 1
        for field in result.row_hierarchy:
            if field in varying:
                row_count *= len(varying[field])
        
        col_count = 1
        for field in result.col_hierarchy:
            if field in varying:
                col_count *= len(varying[field])
        
        total_cells = row_count * col_count
        
        # Step 6: Determine backup split field (outermost dimension)
        if result.row_hierarchy:
            result.backup_split_field = result.row_hierarchy[0]  # Outermost row
        elif result.col_hierarchy:
            result.backup_split_field = result.col_hierarchy[0]  # Outermost col
        else:
            result.backup_split_field = None
        
        # Step 7: Determine strategy and warnings
        depth = max(len(result.row_hierarchy), len(result.col_hierarchy))
        if depth == 0:
            result.strategy = "single_image"
        elif depth == 1:
            result.strategy = "simple_xy"
        else:
            result.strategy = f"hierarchical_{depth}_levels"
        
        if total_combos > max_per_grid:
            result.warnings.append(
                f"Grid has {total_combos} images, exceeds limit of {max_per_grid}. "
                f"Consider splitting by '{result.backup_split_field}'."
            )
        
        if total_combos > 1000:
            result.warnings.append(
                f"Very large grid ({total_combos} images). May be slow to render."
            )
        
        # Step 8: Build explanation
        parts = []
        if result.row_hierarchy:
            parts.append(f"Row hierarchy: {' → '.join(result.row_hierarchy)} (outer→inner)")
        if result.col_hierarchy:
            parts.append(f"Col hierarchy: {' → '.join(result.col_hierarchy)} (outer→inner)")
        parts.append(f"Grid: {row_count} rows × {col_count} cols = {total_cells} cells")
        parts.append(f"Strategy: {result.strategy}")
        
        result.explanation = " | ".join(parts)
        
        return result
    
    def _generate_formula_text(
        self,
        result: LayoutResult,
        varying: Dict[str, List],
        weights: Dict[str, int],
    ) -> str:
        """Generate code-like formula text explaining the layout decision."""
        lines = [
            "# Grid Layout Formula (Hierarchical Pivot-Table)",
            "",
            "# Input Analysis:",
            f"total_combinations = {result.total_combinations}",
            f"varying_dimensions = {result.detected_dimensions}",
            "",
            "# Priority Weights (higher = innermost/leaf):",
        ]
        
        for field in result.detected_dimensions:
            weight = weights.get(field, 50)
            lines.append(f"  {field}: {weight}")
        
        lines.extend([
            "",
            "# Sorting: dimensions sorted by weight DESCENDING",
            "# Distribution: alternate col→row→col→row (innermost first)",
            "",
            "# Result:",
        ])
        
        if result.row_hierarchy:
            lines.append(f"row_hierarchy = {result.row_hierarchy}  # outer → inner")
        else:
            lines.append("row_hierarchy = []  # No row dimensions")
        
        if result.col_hierarchy:
            lines.append(f"col_hierarchy = {result.col_hierarchy}  # outer → inner")
        else:
            lines.append("col_hierarchy = []  # No column dimensions")
        
        lines.extend([
            "",
            f"strategy = '{result.strategy}'",
        ])
        
        if result.backup_split_field:
            lines.append(f"backup_split_field = '{result.backup_split_field}'")
        
        if result.warnings:
            lines.extend(["", "# Warnings:"])
            for warning in result.warnings:
                lines.append(f"# ⚠️ {warning}")
        
        return "\n".join(lines)


# Node registration
NODE_CLASS_MAPPINGS = {
    "GridPresetFormula": GridPresetFormula,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GridPresetFormula": "Ⓜ️ Model Compare - Grid Preset Formula",
}
