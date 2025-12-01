"""
Variation Expander Utility Module

Handles expansion of multi-value fields (comma-separated) into full
cartesian product of variations for the Model Compare system.
"""

import itertools
from typing import Dict, List, Any, Tuple, Optional, Union
import comfy.samplers


# === Validation Lists (Dynamic from ComfyUI) ===

def get_valid_samplers() -> set:
    """Get valid sampler names from ComfyUI."""
    return set(comfy.samplers.KSampler.SAMPLERS)


def get_valid_schedulers() -> set:
    """Get valid scheduler names from ComfyUI."""
    return set(comfy.samplers.KSampler.SCHEDULERS)


# === Parsing Functions ===

def parse_string_list(value: Union[str, List[str]], valid_set: Optional[set] = None, 
                      default: str = None) -> List[str]:
    """
    Parse a comma-separated string into a list of values.
    
    Args:
        value: String like "euler, dpmpp_2m" or already a list
        valid_set: Optional set of valid values to filter against
        default: Default value if parsing fails or results empty
    
    Returns:
        List of string values
    """
    if isinstance(value, list):
        values = value
    elif isinstance(value, str):
        values = [v.strip() for v in value.split(",") if v.strip()]
    else:
        values = [str(value)] if value else []
    
    # Filter against valid set if provided
    if valid_set:
        values = [v for v in values if v in valid_set]
    
    # Return default if empty
    if not values and default:
        return [default]
    
    return values if values else []


def parse_numeric_list(value: Union[str, int, float, List], cast_fn: type,
                       default: Any, min_val: Optional[float] = None, 
                       max_val: Optional[float] = None) -> List:
    """
    Parse a comma-separated string of numbers into a list.
    
    Args:
        value: String like "1024, 768, 512" or single value or list
        cast_fn: int or float
        default: Default value if parsing fails
        min_val: Optional minimum value (values below are clamped)
        max_val: Optional maximum value (values above are clamped)
    
    Returns:
        List of numeric values
    """
    if isinstance(value, list):
        raw_values = value
    elif isinstance(value, str):
        raw_values = [v.strip() for v in value.split(",") if v.strip()]
    else:
        # Single numeric value
        raw_values = [value] if value is not None else []
    
    values = []
    for v in raw_values:
        try:
            num = cast_fn(v)
            # Apply bounds if specified
            if min_val is not None:
                num = max(min_val, num)
            if max_val is not None:
                num = min(max_val, num)
            values.append(num)
        except (ValueError, TypeError):
            continue
    
    return values if values else [default]


def parse_samplers(value: Union[str, List[str]], default: str = "euler") -> List[str]:
    """Parse comma-separated sampler names with validation."""
    return parse_string_list(value, get_valid_samplers(), default)


def parse_schedulers(value: Union[str, List[str]], default: str = "normal") -> List[str]:
    """Parse comma-separated scheduler names with validation."""
    return parse_string_list(value, get_valid_schedulers(), default)


def parse_steps(value: Union[str, int, List], default: int = 20) -> List[int]:
    """Parse comma-separated step values."""
    return parse_numeric_list(value, int, default, min_val=1, max_val=10000)


def parse_cfg(value: Union[str, float, List], default: float = 7.0) -> List[float]:
    """Parse comma-separated CFG values."""
    return parse_numeric_list(value, float, default, min_val=0.0, max_val=100.0)


def parse_denoise(value: Union[str, float, List], default: float = 1.0) -> List[float]:
    """Parse comma-separated denoise values."""
    return parse_numeric_list(value, float, default, min_val=0.0, max_val=1.0)


def parse_dimensions(value: Union[str, int, List], default: int = 1024) -> List[int]:
    """Parse comma-separated dimension values (width/height)."""
    return parse_numeric_list(value, int, default, min_val=64, max_val=8192)


def parse_shift(value: Union[str, float, List], default: float = 3.0) -> List[float]:
    """Parse comma-separated shift values."""
    return parse_numeric_list(value, float, default, min_val=0.0, max_val=20.0)


def parse_frames(value: Union[str, int, List], default: int = 81) -> List[int]:
    """Parse comma-separated frame count values."""
    return parse_numeric_list(value, int, default, min_val=1, max_val=1000)


def parse_fps(value: Union[str, int, List], default: int = 24) -> List[int]:
    """Parse comma-separated FPS values."""
    return parse_numeric_list(value, int, default, min_val=1, max_val=120)


# === Expansion Functions ===

# Fields that can have multiple values (will be expanded)
EXPANDABLE_FIELDS = {
    # Dropdown fields (string lists)
    "sampler_name": ("sampler_names", parse_samplers, "euler"),
    "scheduler": ("schedulers", parse_schedulers, "normal"),
    
    # Numeric fields
    "steps": ("steps_list", parse_steps, 20),
    "cfg": ("cfg_list", parse_cfg, 7.0),
    "denoise": ("denoise_list", parse_denoise, 1.0),
    "width": ("width_list", parse_dimensions, 1024),
    "height": ("height_list", parse_dimensions, 1024),
    
    # Video fields
    "num_frames": ("num_frames_list", parse_frames, 81),
    "fps": ("fps_list", parse_fps, 24),
    
    # Shift fields
    "lumina_shift": ("lumina_shift_list", parse_shift, 3.0),
    "qwen_shift": ("qwen_shift_list", parse_shift, 1.15),
    "wan_shift": ("wan_shift_list", parse_shift, 8.0),
    "wan22_shift": ("wan22_shift_list", parse_shift, 8.0),
    "hunyuan_shift": ("hunyuan_shift_list", parse_shift, 7.0),
    "flux_guidance": ("flux_guidance_list", lambda v, d=3.5: parse_numeric_list(v, float, d, 0.0, 100.0), 3.5),
}


def parse_sampling_config(sampling_cfg: Dict) -> Dict:
    """
    Parse a sampling config and convert multi-value fields to lists.
    
    Args:
        sampling_cfg: Raw sampling config with possible comma-separated values
    
    Returns:
        Config with list values for expandable fields
    """
    result = dict(sampling_cfg)
    
    for field_name, (list_name, parser, default) in EXPANDABLE_FIELDS.items():
        if field_name in result:
            raw_value = result[field_name]
            parsed = parser(raw_value, default) if callable(parser) else parser(raw_value)
            result[list_name] = parsed
            # Keep original field name pointing to first value for backward compat
            result[field_name] = parsed[0] if parsed else default
    
    return result


def expand_sampling_config(sampling_cfg: Dict) -> Tuple[List[Dict], List[str]]:
    """
    Expand a sampling config with multi-value fields into all combinations.
    
    Args:
        sampling_cfg: Parsed sampling config with list values
    
    Returns:
        Tuple of:
        - List of individual configs (one per combination)
        - List of variation descriptions for labeling
    """
    # Identify which fields have multiple values
    expansion_fields = []
    expansion_values = []
    
    for field_name, (list_name, _, default) in EXPANDABLE_FIELDS.items():
        if list_name in sampling_cfg:
            values = sampling_cfg[list_name]
            if len(values) > 1:
                expansion_fields.append(field_name)
                expansion_values.append(values)
    
    # If no fields have multiple values, return single config
    if not expansion_fields:
        return [sampling_cfg], [""]
    
    # Generate all combinations
    expanded_configs = []
    variation_labels = []
    
    for combo in itertools.product(*expansion_values):
        # Create new config with this combination
        new_cfg = dict(sampling_cfg)
        label_parts = []
        
        for field_name, value in zip(expansion_fields, combo):
            new_cfg[field_name] = value
            # Add to label
            label_parts.append(f"{_format_field_label(field_name)}:{_format_value(value)}")
        
        expanded_configs.append(new_cfg)
        variation_labels.append(" | ".join(label_parts))
    
    return expanded_configs, variation_labels


def count_variations(sampling_cfg: Dict) -> int:
    """
    Count total number of variations without fully expanding.
    
    Args:
        sampling_cfg: Parsed sampling config with list values
    
    Returns:
        Total number of combinations
    """
    count = 1
    
    for field_name, (list_name, _, _) in EXPANDABLE_FIELDS.items():
        if list_name in sampling_cfg:
            values = sampling_cfg[list_name]
            count *= len(values)
    
    return count


def _format_field_label(field_name: str) -> str:
    """Format field name for display in labels."""
    label_map = {
        "sampler_name": "S",
        "scheduler": "Sch",
        "steps": "st",
        "cfg": "cfg",
        "denoise": "dn",
        "width": "w",
        "height": "h",
        "num_frames": "fr",
        "fps": "fps",
        "lumina_shift": "lsh",
        "qwen_shift": "qsh",
        "wan_shift": "wsh",
        "wan22_shift": "w22sh",
        "hunyuan_shift": "hsh",
        "flux_guidance": "fg",
    }
    return label_map.get(field_name, field_name[:3])


def _format_value(value: Any) -> str:
    """Format a value for display in labels."""
    if isinstance(value, float):
        # Remove trailing zeros
        return f"{value:.2f}".rstrip('0').rstrip('.')
    return str(value)


# === Warning System ===

WARNING_THRESHOLD = 20


def check_variation_warning(total_variations: int) -> Optional[str]:
    """
    Check if variation count exceeds warning threshold.
    
    Args:
        total_variations: Total number of variations
    
    Returns:
        Warning message if threshold exceeded, None otherwise
    """
    if total_variations > WARNING_THRESHOLD:
        return f"⚠️ High variation count: {total_variations} combinations will be generated. This may take a long time and use significant memory."
    return None


def calculate_total_combinations(configs: List[Dict], lora_combos: int = 1, 
                                  prompt_variations: int = 1) -> Tuple[int, Optional[str]]:
    """
    Calculate total combinations across all configs and check for warning.
    
    Args:
        configs: List of parsed sampling configs
        lora_combos: Number of LoRA strength combinations
        prompt_variations: Number of prompt variations
    
    Returns:
        Tuple of (total_count, warning_message_or_None)
    """
    total = 0
    
    for cfg in configs:
        cfg_variations = count_variations(cfg)
        total += cfg_variations * lora_combos * prompt_variations
    
    warning = check_variation_warning(total)
    return total, warning
