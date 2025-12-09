"""
Grid Compare Node
Takes the output images from SamplerCompare and arranges them into
a customizable comparison grid with labels and styling.
"""

import os
import re
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
from typing import Dict, List, Tuple, Any
from pathlib import Path
import folder_paths
import json
import comfy.cli_args
args = comfy.cli_args.args

# Import smart preset analyzer
try:
    from .grid_preset_analyzer import analyze_config as smart_analyze_config
except ImportError:
    # Fallback if not available
    smart_analyze_config = None

# Import shared grid utilities
from .grid_utils import (
    expand_combinations_with_lora_modes,
    detect_varying_dimensions,
    get_combo_field_value as utils_get_combo_field_value,
    clean_lora_name,
    clean_model_name,
    wrap_text,
    format_prompt_for_header,
    parse_lora_groups,
    LoraGroup,
)

# Import ragged grid renderer for tree-based hierarchical grids
try:
    from .ragged_grid_renderer import RaggedHierarchyGrid
    HAS_RAGGED_RENDERER = True
except ImportError as e:
    print(f"[GridCompare] Warning: Could not import RaggedHierarchyGrid: {e}")
    HAS_RAGGED_RENDERER = False


def sanitize_filename(name: str) -> str:
    """
    Sanitize a string to be safe for use in filenames.
    Removes or replaces characters invalid in Windows/Unix filenames.
    """
    # Characters invalid in Windows filenames: < > : " / \ | ? *
    # Also remove control characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', str(name))
    # Replace multiple underscores with single
    sanitized = re.sub(r'_+', '_', sanitized)
    # Remove leading/trailing underscores and spaces
    sanitized = sanitized.strip('_ ')
    return sanitized if sanitized else "unnamed"


class GridCompare:
    """
    Create a hierarchical comparison grid from sampled images.
    
    Uses GRID_LAYOUT from GridPresetFormula for row/column hierarchies.
    Uses GRID_FORMAT_CONFIG from GridFormatConfig for visual styling.
    Both inputs are optional with sensible defaults.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "config": ("MODEL_COMPARE_CONFIG",),
                "save_location": ("STRING", {
                    "default": "model-compare",
                    "multiline": False,
                    "tooltip": "Output folder path for saving grid",
                }),
                "grid_title": ("STRING", {
                    "default": "Model Comparison Grid",
                    "multiline": False,
                    "tooltip": "Name for the saved grid file",
                }),
                "output_prefix": ("STRING", {
                    "default": "compare",
                    "multiline": False,
                    "tooltip": "Prefix for individual image filenames"
                }),
                # Save options
                "save_individuals": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Save individual images in addition to grid",
                }),
                "save_metadata": ("BOOLEAN", {
                    "default": True,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Embed workflow metadata in PNG files",
                }),
                # Subtitle configuration
                "subtitle_fields": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Comma-separated subtitle fields: model,vae,clip,lora,lora_strength,sampler,scheduler,cfg,steps,seed,dimensions,prompt,negative_prompt"
                }),
                "subtitle_show_field_names": ("BOOLEAN", {
                    "default": True, 
                    "label_on": "yes", 
                    "label_off": "no", 
                    "tooltip": "Show field names in subtitle (e.g., 'Model: X' vs 'X')"
                }),
                # Grid splitting/nesting options
                "max_images_per_grid": ("INT", {
                    "default": 100,
                    "min": 4,
                    "max": 1000,
                    "step": 4,
                    "tooltip": "Maximum images per grid before splitting into multiple grids"
                }),
                "split_by_field": (["auto", "none", "model", "lora_name", "prompt_positive", "sampler_name", "cfg"], {
                    "default": "auto",
                    "tooltip": "Field to split into multiple grids when exceeding max_images_per_grid. 'auto' picks the best field, 'none' disables splitting"
                }),
                # HTML Grid output options
                "html_grid_output": ("BOOLEAN", {
                    "default": True,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Generate an interactive HTML grid with filters, lightbox, and metadata"
                }),
                "html_image_format": (["PNG", "JPEG"], {
                    "default": "PNG",
                    "tooltip": "Image format for HTML grid (PNG = lossless, JPEG = smaller file)"
                }),
                "html_image_quality": ("INT", {
                    "default": 100,
                    "min": 50,
                    "max": 100,
                    "step": 5,
                    "tooltip": "Image quality for HTML grid (higher = larger file)"
                }),
            },
            "optional": {
                "grid_layout": ("GRID_LAYOUT", {
                    "tooltip": "Layout from 'Grid Preset Formula' node - determines row/column hierarchies"
                }),
                "format_config": ("GRID_FORMAT_CONFIG", {
                    "tooltip": "Styling from 'Grid Format Config' node - determines colors, fonts, borders"
                }),
                "video_config": ("VIDEO_GRID_CONFIG", {
                    "tooltip": "Optional video configuration from 'Video Grid Config' node"
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    CATEGORY = "Model Compare/Grid"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("images", "save_path", "video_path", "html_path")
    OUTPUT_IS_LIST = (False, False, False, False)
    FUNCTION = "create_grid"
    OUTPUT_NODE = True
    
    # Label priority order - higher priority fields appear first in labels
    # When base model is same, LoRA info becomes more important
    LABEL_PRIORITY = [
        'model', 'vae', 'clip', 'lora_name', 'lora_strength', 'lora_display',
        'sampler_name', 'scheduler', 'lumina_shift', 'qwen_shift', 'wan_shift',
        'wan22_shift', 'hunyuan_shift', 'flux_guidance', 'cfg', 'steps', 
        'seed', 'width', 'height', 'prompt_positive', 'prompt_negative'
    ]
    
    def _split_by_field(
        self,
        images: List[Any],
        labels: List[str],
        combinations: List[Dict],
        config: Dict,
        split_field: str,
    ) -> List[Dict]:
        """
        Split images, labels, and combinations into groups by a field value.
        
        Returns list of dicts, each with:
        - 'images': List of PIL images for this group
        - 'labels': List of labels for this group  
        - 'combinations': List of combos for this group
        - 'split_value': The value of split_field for this group
        - 'group_title': A title suffix for this group
        """
        if not split_field or split_field == "none":
            return [{
                'images': images,
                'labels': labels,
                'combinations': combinations,
                'split_value': None,
                'group_title': ''
            }]
        
        # Group by split field value
        groups = {}  # value -> {'images': [], 'labels': [], 'combinations': []}
        
        for i, (img, label, combo) in enumerate(zip(images, labels, combinations)):
            value = self._get_combo_field_value(combo, config, split_field)
            
            # Format the value for grouping
            if value is None:
                value = 'Unknown'
            elif isinstance(value, float):
                value = f"{value:.2f}".rstrip('0').rstrip('.')
            else:
                value = str(value)
            
            if value not in groups:
                groups[value] = {'images': [], 'labels': [], 'combinations': []}
            
            groups[value]['images'].append(img)
            groups[value]['labels'].append(label)
            groups[value]['combinations'].append(combo)
        
        # Convert to list of dicts with group info
        result = []
        for value, data in sorted(groups.items()):
            display_name = self._get_field_display_name(split_field)
            result.append({
                'images': data['images'],
                'labels': data['labels'],
                'combinations': data['combinations'],
                'split_value': value,
                'group_title': f"{display_name}: {value}"
            })
        
        return result
    
    def _get_field_display_name(self, field: str) -> str:
        """Get a human-readable display name for a field."""
        names = {
            'model': 'Model',
            'vae': 'VAE',
            'clip': 'CLIP',
            'lora_name': 'LoRA',
            'lora_strength': 'LoRA Strength',
            'lora_display': 'LoRA',
            'sampler_name': 'Sampler',
            'scheduler': 'Scheduler',
            'steps': 'Steps',
            'cfg': 'CFG',
            'denoise': 'Denoise',
            'seed': 'Seed',
            'width': 'Width',
            'height': 'Height',
            'prompt_positive': 'Prompt',
            'prompt_negative': 'Neg Prompt',
            'lumina_shift': 'Lumina Shift',
            'qwen_shift': 'Qwen Shift',
            'wan_shift': 'WAN Shift',
            'wan22_shift': 'WAN 2.2 Shift',
            'hunyuan_shift': 'Hunyuan Shift',
            'flux_guidance': 'FLUX Guidance',
        }
        return names.get(field, field.replace('_', ' ').title())
    
    def _get_combo_field_value(self, combo: Dict, config: Dict, field: str) -> Any:
        """
        Extract the value of a specific field from a combination.
        Handles nested fields like lora_name, lora_strength from lora_config.
        Also handles per-LoRA dimensions like 'LoRA1_strength', 'Cine_strength', etc.
        """
        # Direct fields
        if field in combo:
            return combo[field]
        
        # Fields from model_variations
        model_vars = combo.get('model_variations', {})
        if field in model_vars:
            return model_vars[field]
        
        # LoRA fields from lora_config
        lora_config = combo.get('lora_config', {})
        loras = lora_config.get('loras', [])
        
        if field == 'lora_name':
            lora_names = lora_config.get('lora_names', [])
            if lora_names:
                # Return as sorted tuple for consistent grouping
                return tuple(sorted(lora_names)) if len(lora_names) > 1 else lora_names[0]
            return None
        
        if field == 'lora_strength':
            lora_strengths = lora_config.get('lora_strengths', [])
            if lora_strengths:
                # Return as tuple for consistent grouping
                return tuple(lora_strengths) if len(lora_strengths) > 1 else lora_strengths[0]
            return None
        
        if field == 'lora_display':
            lora_names = lora_config.get('lora_names', [])
            lora_strengths = lora_config.get('lora_strengths', [])
            if lora_names:
                displays = []
                for i, name in enumerate(lora_names):
                    short_name = Path(name).stem if name else 'None'
                    strength = lora_strengths[i] if i < len(lora_strengths) else 1.0
                    displays.append(f"{short_name}@{strength:.2f}")
                return ' + '.join(displays)
            return None
        
        # Handle per-LoRA dimensions (e.g., 'Cine_strength', 'analog_strength', 'lora1_name')
        if field.endswith('_strength') and loras:
            # Extract the LoRA name prefix (e.g., 'Cine' from 'Cine_strength')
            lora_prefix = field[:-9]  # Remove '_strength'
            
            # Try to match by LoRA name
            for lora in loras:
                lora_label = lora.get('label', lora.get('name', ''))
                # Clean the label for comparison
                clean_label = lora_label
                if '\\' in clean_label:
                    clean_label = clean_label.split('\\')[-1]
                if clean_label.endswith('.safetensors'):
                    clean_label = clean_label[:-12]
                
                if clean_label == lora_prefix or lora_prefix.lower() == clean_label.lower():
                    return lora.get('strength', 1.0)
            
            # Try to match by index (e.g., 'LoRA1_strength' → index 0)
            if lora_prefix.lower().startswith('lora'):
                try:
                    idx = int(lora_prefix[4:]) - 1  # 'LoRA1' → index 0
                    if 0 <= idx < len(loras):
                        return loras[idx].get('strength', 1.0)
                except ValueError:
                    pass
        
        # Handle per-LoRA name dimensions (e.g., 'lora1_name')
        if field.endswith('_name') and field.startswith('lora') and loras:
            try:
                idx = int(field[4:-5]) - 1  # 'lora1_name' → index 0
                if 0 <= idx < len(loras):
                    name = loras[idx].get('label', loras[idx].get('name', ''))
                    if '\\' in name:
                        name = name.split('\\')[-1]
                    if name.endswith('.safetensors'):
                        name = name[:-12]
                    return name
            except ValueError:
                pass
        
        # Check sampler_config
        sampler_config = combo.get('sampler_config', {})
        if field in sampler_config:
            return sampler_config[field]
        
        # Check prompt_config  
        prompt_config = combo.get('prompt_config', {})
        if field in prompt_config:
            return prompt_config[field]
        
        return None
    
    def _detect_varying_dimensions(self, combinations: List[Dict], config: Dict = None) -> Dict[str, List[Any]]:
        """
        Analyze combinations to find which dimensions have multiple unique values.
        Properly extracts nested data from lora_config, model_variations, etc.
        
        For multi-LoRA AND mode setups, creates separate per-LoRA dimensions.
        
        Returns dict of dimension_name -> list of unique values (sorted)
        """
        if not combinations:
            return {}
        
        # Initialize field value sets
        field_values = {
            'model': set(),
            'vae': set(),
            'clip': set(),
            'lora_name': set(),
            'lora_strength': set(),
            'lora_display': set(),
            'sampler_name': set(),
            'scheduler': set(),
            'steps': set(),
            'cfg': set(),
            'denoise': set(),
            'seed': set(),
            'width': set(),
            'height': set(),
            'lumina_shift': set(),
            'qwen_shift': set(),
            'wan_shift': set(),
            'wan22_shift': set(),
            'hunyuan_shift': set(),
            'flux_guidance': set(),
            'prompt_positive': set(),
            'prompt_negative': set(),
        }
        
        # Track per-LoRA dimensions for multi-LoRA AND mode
        per_lora_names = {}  # lora_index -> set of names
        per_lora_strengths = {}  # lora_index -> set of strengths
        num_loras_in_combo = 0
        
        # Get model variations for name lookup
        model_variations = config.get('model_variations', []) if config else []
        
        for combo in combinations:
            # Check _sampling_override first (for expanded variations)
            override = combo.get('_sampling_override', {})
            
            # Extract model name from model_index
            model_idx = combo.get('model_index', 0)
            if model_idx < len(model_variations):
                model_entry = model_variations[model_idx]
                model_name = model_entry.get('display_name', model_entry.get('name', f'Model {model_idx}'))
                # Clean up model name (remove .safetensors extension)
                if model_name.endswith('.safetensors'):
                    model_name = model_name[:-12]
                field_values['model'].add(model_name)
            
            # Extract VAE name
            vae_name = combo.get('vae_name')
            if vae_name:
                if vae_name.endswith('.safetensors'):
                    vae_name = vae_name[:-12]
                field_values['vae'].add(vae_name)
            
            # Extract CLIP info
            clip_var = combo.get('clip_variation')
            if clip_var:
                if clip_var.get('type') == 'pair':
                    clip_name = f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
                else:
                    clip_name = clip_var.get('model', clip_var.get('clip_type', ''))
                if clip_name:
                    field_values['clip'].add(clip_name)
            
            # Extract LoRA info from lora_config
            lora_config = combo.get('lora_config', {})
            loras = lora_config.get('loras', [])
            lora_display = lora_config.get('display', '')
            
            if loras:
                num_loras_in_combo = max(num_loras_in_combo, len(loras))
                
                # Track per-LoRA dimensions
                for i, lora in enumerate(loras):
                    # Track name per LoRA slot
                    if i not in per_lora_names:
                        per_lora_names[i] = set()
                    name = lora.get('label', lora.get('name', ''))
                    if name:
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
                
                # Also collect joined values for lora_name and lora_strength
                lora_names = [lora.get('label', lora.get('name', '')) for lora in loras if lora.get('label', lora.get('name', ''))]
                if lora_names:
                    joined_name = ' + '.join(lora_names)
                    field_values['lora_name'].add(joined_name)
                
                strengths = tuple(lora.get('strength', 1.0) for lora in loras)
                field_values['lora_strength'].add(strengths)
            
            if lora_display and lora_display != 'No LoRA':
                field_values['lora_display'].add(lora_display)
            
            # Extract sampling parameters from override or combo
            for field in ['sampler_name', 'scheduler', 'steps', 'cfg', 'denoise', 'seed',
                         'width', 'height', 'lumina_shift', 'qwen_shift', 'wan_shift',
                         'wan22_shift', 'hunyuan_shift', 'flux_guidance']:
                value = override.get(field, combo.get(field))
                if value is not None:
                    field_values[field].add(value)
            
            # Extract prompts
            for field in ['prompt_positive', 'prompt_negative']:
                value = combo.get(field)
                if value:
                    field_values[field].add(value)
        
        # Return only fields with >1 unique value
        varying = {}
        for field, values in field_values.items():
            if len(values) > 1:
                # Sort for consistent ordering
                try:
                    sorted_values = sorted(values)
                except TypeError:
                    sorted_values = list(values)
                varying[field] = sorted_values
        
        # Add per-LoRA dimensions for multi-LoRA AND mode
        if num_loras_in_combo > 1:
            has_per_lora_strength_variation = any(
                len(strengths) > 1 for strengths in per_lora_strengths.values()
            )
            
            if has_per_lora_strength_variation:
                for i in sorted(per_lora_strengths.keys()):
                    strengths = per_lora_strengths[i]
                    if len(strengths) > 1:
                        lora_names_for_slot = per_lora_names.get(i, set())
                        lora_label = list(lora_names_for_slot)[0] if len(lora_names_for_slot) == 1 else f"LoRA{i+1}"
                        dim_key = f"{lora_label}_strength"
                        varying[dim_key] = sorted(list(strengths))
                
                for i in sorted(per_lora_names.keys()):
                    names = per_lora_names[i]
                    if len(names) > 1:
                        dim_key = f"lora{i+1}_name"
                        varying[dim_key] = sorted(list(names))
        
        return varying
    
    def _reconstruct_combinations_from_layout(
        self,
        num_images: int,
        row_hierarchy: List[str],
        col_hierarchy: List[str],
        varying_dims: Dict[str, Dict],
    ) -> List[Dict]:
        """
        Reconstruct synthetic combinations when real combinations are not available.
        
        This creates combinations based on the grid layout structure,
        assuming images are ordered row-major (row by row, left to right).
        
        Args:
            num_images: Total number of images
            row_hierarchy: List of row fields (outer→inner)
            col_hierarchy: List of column fields (outer→inner)
            varying_dims: Dict of field → {'values': [...], 'count': N}
            
        Returns:
            List of synthetic combination dicts
        """
        from itertools import product
        
        # Get ordered values for each dimension
        all_dims = col_hierarchy + row_hierarchy  # Column-major traversal
        
        # Build value lists for each dimension
        dim_values = []
        dim_names = []
        for dim in all_dims:
            if dim in varying_dims:
                values = varying_dims[dim].get('values', ['default'])
                if not values:
                    values = ['default']
            else:
                values = ['default']
            dim_values.append(values)
            dim_names.append(dim)
        
        # Generate all combinations using cartesian product
        all_combos = list(product(*dim_values))
        
        # Create combination dicts
        combinations = []
        for i, combo_values in enumerate(all_combos):
            if i >= num_images:
                break
            combo = {}
            for dim_name, value in zip(dim_names, combo_values):
                combo[dim_name] = value
            combinations.append(combo)
        
        # Pad if we have more images than expected combinations
        while len(combinations) < num_images:
            combinations.append({'_extra': True})
        
        print(f"[GridCompare] Reconstructed combinations: {len(combinations)} entries")
        if combinations:
            print(f"[GridCompare] Sample combination: {combinations[0]}")
        
        return combinations
    
    def _get_priority_varying_dims(self, varying_dims: Dict[str, List[Any]]) -> List[str]:
        """Return varying dimensions sorted by label priority."""
        return [dim for dim in self.LABEL_PRIORITY if dim in varying_dims]
    
    def _generate_cell_label(self, combo: Dict, config: Dict, varying_dims: Dict[str, List[Any]], 
                             exclude_axes: List[str] = None, subtitle_filter: Dict[str, bool] = None,
                             show_field_names: bool = False) -> str:
        """
        Generate a concise label for a grid cell based on varying dimensions.
        Excludes dimensions already shown in row/col/nest headers.
        Uses priority ordering.
        
        Args:
            combo: The combination dict for this cell
            config: The full config dict
            varying_dims: Dict of field -> list of varying values
            exclude_axes: Fields to exclude (already shown in row/col headers)
            subtitle_filter: Optional dict mapping field -> bool to filter what's shown.
                            If None, shows all varying dimensions.
                            Keys: model, vae, clip, lora, lora_strength, sampler, scheduler,
                                  cfg, steps, seed, dimensions, prompt, negative_prompt
            show_field_names: If True, prefix values with field names (e.g., "Model: X")
        """
        if exclude_axes is None:
            exclude_axes = []
        
        # Map subtitle_filter keys to LABEL_PRIORITY field names
        filter_key_map = {
            'model': 'model',
            'vae': 'vae',
            'clip': 'clip',
            'lora': ['lora_name', 'lora_display'],  # 'lora' enables both
            'lora_strength': 'lora_strength',
            'sampler': 'sampler_name',
            'scheduler': 'scheduler',
            'cfg': 'cfg',
            'steps': 'steps',
            'seed': 'seed',
            'dimensions': ['width', 'height'],  # 'dimensions' enables both
            'prompt': 'prompt_positive',
            'negative_prompt': 'prompt_negative',
        }
        
        # Build set of allowed fields based on subtitle_filter
        # If filter is None or has no enabled fields, show all varying dimensions (original behavior)
        allowed_fields = None
        if subtitle_filter:
            temp_fields = set()
            for filter_key, enabled in subtitle_filter.items():
                if filter_key == 'show_field_names':
                    continue  # Skip non-field keys
                if enabled and filter_key in filter_key_map:
                    mapped = filter_key_map[filter_key]
                    if isinstance(mapped, list):
                        temp_fields.update(mapped)
                    else:
                        temp_fields.add(mapped)
            # Only apply filter if at least one field is enabled
            # Otherwise fall back to showing all varying dimensions
            if temp_fields:
                allowed_fields = temp_fields
        
        # Get model variations for name lookup
        model_variations = config.get('model_variations', []) if config else []
        override = combo.get('_sampling_override', {})
        
        label_parts = []
        
        # Go through priority order
        for field in self.LABEL_PRIORITY:
            # Skip if not varying or excluded by axes
            if field not in varying_dims or field in exclude_axes:
                continue
            
            # Skip if subtitle_filter is active and this field is not allowed
            if allowed_fields is not None and field not in allowed_fields:
                continue
            
            value = None
            
            if field == 'model':
                model_idx = combo.get('model_index', 0)
                if model_idx < len(model_variations):
                    model_entry = model_variations[model_idx]
                    value = model_entry.get('display_name', model_entry.get('name', f'Model {model_idx}'))
                    if value and value.endswith('.safetensors'):
                        value = value[:-12]
            elif field == 'vae':
                value = combo.get('vae_name', '')
                if value and value.endswith('.safetensors'):
                    value = value[:-12]
            elif field == 'clip':
                clip_var = combo.get('clip_variation')
                if clip_var:
                    if clip_var.get('type') == 'pair':
                        value = f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
                    else:
                        value = clip_var.get('model', clip_var.get('clip_type', ''))
            elif field == 'lora_display':
                lora_config = combo.get('lora_config', {})
                value = lora_config.get('display', '')
                if value == 'No LoRA':
                    value = None
            elif field == 'lora_name':
                lora_config = combo.get('lora_config', {})
                loras = lora_config.get('loras', [])
                if loras:
                    value = ', '.join(l.get('label', l.get('name', '')) for l in loras)
            elif field == 'lora_strength':
                lora_config = combo.get('lora_config', {})
                loras = lora_config.get('loras', [])
                if loras:
                    strengths = [str(l.get('strength', '')) for l in loras]
                    value = ', '.join(strengths)
            elif field in ['prompt_positive', 'prompt_negative']:
                value = combo.get(field, '')
                if value and len(value) > 30:
                    value = value[:27] + '...'
            else:
                # Standard field from override or combo
                value = override.get(field, combo.get(field))
            
            if value is not None and value != '':
                # Format the value
                if isinstance(value, float):
                    value = f"{value:.2f}".rstrip('0').rstrip('.')
                
                # Add field name prefix if requested
                if show_field_names:
                    # Human-readable field names
                    field_display_names = {
                        'model': 'Model',
                        'vae': 'VAE',
                        'clip': 'CLIP',
                        'lora_name': 'LoRA',
                        'lora_display': 'LoRA',
                        'lora_strength': 'Strength',
                        'sampler_name': 'Sampler',
                        'scheduler': 'Scheduler',
                        'cfg': 'CFG',
                        'steps': 'Steps',
                        'seed': 'Seed',
                        'width': 'W',
                        'height': 'H',
                        'prompt_positive': 'Prompt',
                        'prompt_negative': 'Neg',
                        'lumina_shift': 'LShift',
                        'qwen_shift': 'QShift',
                        'wan_shift': 'WShift',
                        'wan22_shift': 'W22Shift',
                        'hunyuan_shift': 'HYShift',
                        'flux_guidance': 'FluxG',
                    }
                    display_name = field_display_names.get(field, field)
                    label_parts.append(f"{display_name}: {value}")
                else:
                    label_parts.append(str(value))
        
        return ' | '.join(label_parts) if label_parts else ''
    
    def _get_combo_field_value(self, combo: Dict, config: Dict, field: str) -> Any:
        """Get a specific field value from a combo, handling nested structures.
        
        IMPORTANT: Return values must match the format used in _detect_varying_dimensions
        for grid mapping to work correctly.
        
        Also handles synthetic combinations where values are stored directly.
        Also handles per-LoRA dimensions like 'Cine_strength', 'analog_strength'.
        """
        # First check for direct field access (synthetic combinations)
        if field in combo and not isinstance(combo.get(field), dict):
            return combo[field]
        
        model_variations = config.get('model_variations', []) if config else []
        override = combo.get('_sampling_override', {})
        lora_config = combo.get('lora_config', {})
        loras = lora_config.get('loras', [])
        
        if field == 'model':
            model_idx = combo.get('model_index', 0)
            if model_idx < len(model_variations):
                model_entry = model_variations[model_idx]
                value = model_entry.get('display_name', model_entry.get('name', f'Model {model_idx}'))
                if value and value.endswith('.safetensors'):
                    value = value[:-12]
                return value
            return None
        elif field == 'vae':
            value = combo.get('vae_name', '')
            if value and value.endswith('.safetensors'):
                value = value[:-12]
            return value if value else None
        elif field == 'clip':
            clip_var = combo.get('clip_variation')
            if clip_var:
                if clip_var.get('type') == 'pair':
                    return f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
                return clip_var.get('model', clip_var.get('clip_type', ''))
            return None
        elif field == 'lora_display':
            value = lora_config.get('display', '')
            return value if value and value != 'No LoRA' else None
        elif field == 'lora_name':
            # Return joined name of ALL loras (matches _detect_varying_dimensions)
            if loras:
                names = [l.get('label', l.get('name', '')) for l in loras if l.get('label', l.get('name', ''))]
                if names:
                    return ' + '.join(names)
            return None
        elif field == 'lora_strength':
            # Return TUPLE of all lora strengths (matches _detect_varying_dimensions)
            if loras:
                strengths = tuple(l.get('strength', 1.0) for l in loras)
                return strengths[0] if len(strengths) == 1 else strengths
            return None
        elif field in ['prompt_positive', 'prompt_negative']:
            return combo.get(field, '')
        elif field.endswith('_strength') and loras:
            # Handle per-LoRA strength dimensions (e.g., 'Cine_strength', 'analog_strength')
            lora_prefix = field[:-9]  # Remove '_strength'
            
            # Try to match by LoRA name
            for lora in loras:
                lora_label = lora.get('label', lora.get('name', ''))
                clean_label = lora_label
                if '\\' in clean_label:
                    clean_label = clean_label.split('\\')[-1]
                if clean_label.endswith('.safetensors'):
                    clean_label = clean_label[:-12]
                
                if clean_label == lora_prefix or lora_prefix.lower() == clean_label.lower():
                    return lora.get('strength', 1.0)
            
            # Try to match by index (e.g., 'LoRA1_strength')
            if lora_prefix.lower().startswith('lora'):
                try:
                    idx = int(lora_prefix[4:]) - 1  # 'LoRA1' → index 0
                    if 0 <= idx < len(loras):
                        return loras[idx].get('strength', 1.0)
                except ValueError:
                    pass
            return None
        elif field.endswith('_name') and field.startswith('lora') and loras:
            # Handle per-LoRA name dimensions (e.g., 'lora1_name')
            try:
                idx = int(field[4:-5]) - 1  # 'lora1_name' → index 0
                if 0 <= idx < len(loras):
                    name = loras[idx].get('label', loras[idx].get('name', ''))
                    if '\\' in name:
                        name = name.split('\\')[-1]
                    if name.endswith('.safetensors'):
                        name = name[:-12]
                    return name
            except ValueError:
                pass
            return None
        else:
            return override.get(field, combo.get(field))
    
    def _create_xy_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        combinations: List[Dict],
        config: Dict[str, Any],
        row_axis: str,
        col_axis: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
        varying_dims: Dict[str, List[Any]] = None,
    ) -> Image.Image:
        """
        Create a smart XY grid with user-specified or auto-detected axes.
        
        Args:
            row_axis: Field to use for rows (y-axis), or "auto" to detect
            col_axis: Field to use for columns (x-axis), or "auto" to detect
            varying_dims: Pre-computed varying dimensions (optional, will detect if not provided)
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Use pre-computed varying dimensions or detect them
        varying = varying_dims if varying_dims is not None else self._detect_varying_dimensions(combinations, config)
        
        # Debug logging
        print(f"[_create_xy_grid] Input row_axis={row_axis}, col_axis={col_axis}")
        print(f"[_create_xy_grid] varying keys={list(varying.keys()) if varying else 'None'}")
        
        if not varying:
            # No variations detected - single row grid
            return self._create_row_grid(
                images, labels, gap_size, border_color, border_width,
                text_color, font_size, font_name, title
            )
        
        # Auto-detect axes if needed
        # Priority: scheduler > sampler > height > lumina_shift > width > cfg > steps
        priority = ['scheduler', 'sampler_name', 'height', 'lumina_shift', 'width', 'cfg', 'steps', 'model']
        
        actual_row_axis = row_axis
        actual_col_axis = col_axis
        
        # CRITICAL LoRA RULES - enforce lora_strength to columns and lora_name to rows
        # These take precedence over auto-detection when both are varying
        if row_axis == "auto" and col_axis == "auto":
            # Check for LoRA variations - enforce standard layout
            if 'lora_strength' in varying and len(varying['lora_strength']) > 1:
                actual_col_axis = 'lora_strength'
                print(f"[_create_xy_grid] RULE: lora_strength FORCED to columns (progression left→right)")
            
            if 'lora_name' in varying and len(varying['lora_name']) > 1:
                # Only force lora_name to rows if col isn't also lora_name
                if actual_col_axis != 'lora_name':
                    actual_row_axis = 'lora_name'
                    print(f"[_create_xy_grid] RULE: lora_name FORCED to rows (one LoRA per row)")
        
        if row_axis == "auto" and actual_row_axis == "auto":
            # Pick first available varying dimension for rows
            for p in priority:
                if p in varying and p != actual_col_axis:
                    actual_row_axis = p
                    break
            if actual_row_axis == "auto":
                # Use first non-col dimension
                for k in varying:
                    if k != actual_col_axis:
                        actual_row_axis = k
                        break
                if actual_row_axis == "auto":
                    actual_row_axis = list(varying.keys())[0] if varying else None
        
        if col_axis == "auto" and actual_col_axis == "auto":
            # Pick second varying dimension for columns
            for p in priority:
                if p in varying and p != actual_row_axis:
                    actual_col_axis = p
                    break
            if actual_col_axis == "auto":
                # Use remaining dimension
                for k in varying:
                    if k != actual_row_axis:
                        actual_col_axis = k
                        break
        
        # Get unique values for each axis
        # If axis isn't in varying dict (e.g., user explicitly selected an axis), 
        # extract unique values directly from combinations
        if actual_row_axis and actual_row_axis not in varying:
            # Extract unique values for this axis from combinations
            row_vals_set = set()
            for combo in combinations:
                val = self._get_combo_field_value(combo, config, actual_row_axis)
                if val is not None:
                    row_vals_set.add(val)
            if row_vals_set:
                try:
                    row_values = sorted(list(row_vals_set))
                except TypeError:
                    row_values = list(row_vals_set)
                # Also add to varying so subsequent code can use it
                varying[actual_row_axis] = row_values
            else:
                row_values = [None]
        else:
            row_values = varying.get(actual_row_axis, [None])
        
        if actual_col_axis and actual_col_axis not in varying:
            # Extract unique values for this axis from combinations
            col_vals_set = set()
            for combo in combinations:
                val = self._get_combo_field_value(combo, config, actual_col_axis)
                if val is not None:
                    col_vals_set.add(val)
            if col_vals_set:
                try:
                    col_values = sorted(list(col_vals_set))
                except TypeError:
                    col_values = list(col_vals_set)
                # Also add to varying so subsequent code can use it
                varying[actual_col_axis] = col_values
            else:
                col_values = [None]
        else:
            col_values = varying.get(actual_col_axis, [None])
        
        # If we only have one axis, make it columns
        if actual_row_axis and not actual_col_axis:
            actual_col_axis = actual_row_axis
            col_values = row_values
            actual_row_axis = None
            row_values = [None]
        
        # Debug logging
        print(f"[_create_xy_grid] actual_row_axis={actual_row_axis}, actual_col_axis={actual_col_axis}")
        print(f"[_create_xy_grid] row_values={row_values}, col_values={col_values}")
        
        # Create mapping from (row_val, col_val) -> image index
        grid_map = {}
        for idx, combo in enumerate(combinations):
            if idx >= len(images):
                break
            
            row_val = self._get_combo_field_value(combo, config, actual_row_axis) if actual_row_axis else None
            col_val = self._get_combo_field_value(combo, config, actual_col_axis) if actual_col_axis else None
            
            # Debug: log each combo's extracted values for lora_strength columns
            if actual_col_axis == 'lora_strength' and idx < 5:
                lora_config = combo.get('lora_config', {})
                print(f"[_create_xy_grid] combo[{idx}] lora_config={lora_config}, extracted col_val={col_val}, type={type(col_val)}")
            
            key = (row_val, col_val)
            if key not in grid_map:
                grid_map[key] = []
            grid_map[key].append(idx)
        
        # Debug logging - show types too
        print(f"[_create_xy_grid] grid_map keys={list(grid_map.keys())}")
        
        # Check for collisions - multiple images in same cell
        collisions = {k: v for k, v in grid_map.items() if len(v) > 1}
        if collisions:
            total_lost = sum(len(v) - 1 for v in collisions.values())
            print(f"[_create_xy_grid] COLLISION DETECTED: {len(collisions)} cells have {total_lost} extra images!")
            
            # Find unused varying dimensions that could serve as nest axis
            used_axes = {actual_row_axis, actual_col_axis}
            unused_dims = [d for d in varying.keys() if d not in used_axes and d is not None]
            
            if unused_dims:
                # AUTO-FIX: Delegate to nested grids with unused dimension as nest axis
                print(f"[_create_xy_grid] AUTO-NESTING: Using '{unused_dims[0]}' to resolve collisions")
                print(f"[_create_xy_grid] Available unused dimensions: {unused_dims}")
                
                return self._create_nested_xy_grids(
                    images=images,
                    labels=labels,
                    combinations=combinations,
                    config=config,
                    row_axis=actual_row_axis,
                    col_axis=actual_col_axis,
                    nest_axes=unused_dims,  # Use ALL unused dimensions for nesting
                    varying_dims=varying,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=title,
                    show_positive_prompt=show_positive_prompt,
                    show_negative_prompt=show_negative_prompt,
                    max_grid_pixels=8000,
                )
            else:
                # No unused dimensions to nest by - warn user
                print(f"[_create_xy_grid] WARNING: Collisions but no unused dimensions for nesting!")
                print(f"[_create_xy_grid] Colliding cells: {collisions}")
        
        if actual_col_axis == 'lora_strength':
            print(f"[_create_xy_grid] col_values from varying: {col_values} (types: {[type(v) for v in col_values]})")
            print(f"[_create_xy_grid] grid_map key col types: {set(type(k[1]) for k in grid_map.keys())}")
        
        # Get image dimensions
        img_width, img_height = images[0].size
        
        # Calculate grid dimensions
        num_rows = len(row_values) if row_values[0] is not None else 1
        num_cols = len(col_values) if col_values[0] is not None else len(images)
        
        # Font setup
        title_font = self._get_font(font_name, font_size)
        header_font = self._get_font(font_name, int(font_size * 0.8))
        label_font = self._get_font(font_name, int(font_size * 0.6))
        prompt_font = self._get_font(font_name, int(font_size * 0.5))
        text_rgb = self._parse_color(text_color)
        border_rgb = self._parse_color(border_color)
        
        # Check if using prompt as an axis - need special handling
        is_prompt_row_axis = actual_row_axis in ('prompt_positive', 'prompt_negative')
        is_prompt_col_axis = actual_col_axis in ('prompt_positive', 'prompt_negative')
        
        # Spacing - increased padding for better readability
        title_height = font_size + 40 if title else 0
        
        # For prompt column headers, we need much more height to show wrapped text
        if is_prompt_col_axis:
            col_header_height = int(font_size * 0.6) * 4 + 40  # ~4 lines for prompt
        else:
            col_header_height = int(font_size * 1.0) + 25
        
        # For prompt row labels, we need more width
        if is_prompt_row_axis:
            row_label_width = int(img_width * 0.6)  # 60% of image width for prompt text
        elif actual_row_axis:
            row_label_width = int(font_size * 5)
        else:
            row_label_width = 0
            
        cell_label_height = int(font_size * 0.8) + 20  # More space for labels below images
        
        # Calculate prompt height if needed
        prompt_height = 0
        prompt_text = ""
        if show_positive_prompt:
            # Try prompt_variations first (from prompt config node)
            prompt_variations = config.get("prompt_variations", [])
            if prompt_variations:
                prompt_text = prompt_variations[0].get("positive", "")
            
            # Fallback: check combinations for prompt_positive
            if not prompt_text and combinations:
                for combo in combinations:
                    prompt_text = combo.get("prompt_positive", "")
                    if prompt_text:
                        break
            
            if prompt_text:
                prompt_height = int(font_size * 0.6) * 3 + 30  # ~3 lines + more padding
        
        # Total dimensions
        grid_width = row_label_width + num_cols * (img_width + gap_size) + gap_size
        grid_height = (title_height + col_header_height + 
                       num_rows * (img_height + cell_label_height + gap_size) + 
                       gap_size + prompt_height)
        
        # Create canvas
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        current_y = gap_size
        
        # Draw title
        if title:
            draw.text((grid_width // 2, current_y + font_size // 2), title, 
                      fill=text_rgb, font=title_font, anchor="mm")
            current_y += title_height
        
        # Draw column headers
        if actual_col_axis:
            for col_idx, col_val in enumerate(col_values):
                x = row_label_width + gap_size + col_idx * (img_width + gap_size) + img_width // 2
                
                if is_prompt_col_axis:
                    # For prompt columns, show wrapped text
                    header_text = f"{self._format_axis_label(actual_col_axis)}:"
                    draw.text((x, current_y + 5), header_text,
                              fill=text_rgb, font=header_font, anchor="mt")
                    # Wrap and draw the prompt text below
                    prompt_val = str(col_val) if col_val else ""
                    wrapped = self._wrap_text(prompt_val, prompt_font, img_width - 10)
                    # Limit to ~3 lines
                    lines = wrapped.split('\n')[:3]
                    if len(wrapped.split('\n')) > 3:
                        lines[-1] = lines[-1][:20] + "..."
                    wrapped = '\n'.join(lines)
                    # Draw multiline text line by line (PIL anchor doesn't work with multiline)
                    prompt_y = current_y + int(font_size * 0.9)
                    for line in lines:
                        draw.text((x, prompt_y), line, fill=(80, 80, 80), font=prompt_font, anchor="mt")
                        prompt_y += int(font_size * 0.6)
                else:
                    header_text = f"{self._format_axis_label(actual_col_axis)}: {self._format_value(col_val)}"
                    draw.text((x, current_y + col_header_height // 2), header_text,
                              fill=text_rgb, font=header_font, anchor="mm")
        current_y += col_header_height
        
        # Draw rows
        for row_idx, row_val in enumerate(row_values):
            # Draw row label
            if actual_row_axis and row_val is not None:
                if is_prompt_row_axis:
                    # For prompt rows, draw wrapped text on the left
                    label_x = gap_size + 5
                    label_y = current_y + 10
                    header_text = f"{self._format_axis_label(actual_row_axis)}:"
                    draw.text((label_x, label_y), header_text,
                              fill=text_rgb, font=label_font, anchor="lt")
                    # Wrap and draw the prompt text below
                    prompt_val = str(row_val) if row_val else ""
                    wrapped = self._wrap_text(prompt_val, prompt_font, row_label_width - 20)
                    # Limit lines to fit in row height
                    max_lines = max(3, (img_height + cell_label_height) // int(font_size * 0.6))
                    lines = wrapped.split('\n')[:max_lines]
                    if len(wrapped.split('\n')) > max_lines:
                        lines[-1] = lines[-1][:20] + "..."
                    # Draw multiline text line by line (PIL anchor doesn't work with multiline)
                    prompt_y = label_y + int(font_size * 0.7)
                    for line in lines:
                        draw.text((label_x, prompt_y), line, fill=(80, 80, 80), font=prompt_font)
                        prompt_y += int(font_size * 0.6)
                else:
                    label_y = current_y + (img_height + cell_label_height) // 2
                    # Draw row label as two lines (PIL anchor doesn't work with multiline)
                    axis_label = self._format_axis_label(actual_row_axis)
                    value_label = self._format_value(row_val)
                    draw.text((gap_size + row_label_width // 2, label_y - int(font_size * 0.4)), axis_label,
                              fill=text_rgb, font=label_font, anchor="mm")
                    draw.text((gap_size + row_label_width // 2, label_y + int(font_size * 0.4)), value_label,
                              fill=text_rgb, font=label_font, anchor="mm")
            
            # Draw images in this row
            for col_idx, col_val in enumerate(col_values):
                key = (row_val, col_val)
                x = row_label_width + gap_size + col_idx * (img_width + gap_size)
                y = current_y
                
                if key in grid_map and grid_map[key]:
                    img_idx = grid_map[key][0]  # Take first matching image
                    img = images[img_idx]
                    label = labels[img_idx] if img_idx < len(labels) else ""
                    
                    # Resize if needed
                    if img.size != (img_width, img_height):
                        img = img.resize((img_width, img_height), Image.LANCZOS)
                    
                    # Draw border
                    if border_width > 0:
                        for i in range(border_width):
                            draw.rectangle(
                                [(x - i, y - i), (x + img_width + i, y + img_height + i)],
                                outline=border_rgb, width=1
                            )
                    
                    # Paste image
                    grid_img.paste(img, (x, y))
                    
                    # Draw cell label (shortened)
                    # Extract just the varying parts from full label
                    short_label = self._shorten_label(label, actual_row_axis, actual_col_axis)
                    if short_label:
                        draw.text((x + img_width // 2, y + img_height + 12), short_label,
                                  fill=text_rgb, font=label_font, anchor="mt")
                else:
                    # Empty cell
                    draw.rectangle([(x, y), (x + img_width, y + img_height)],
                                   outline=(200, 200, 200), width=1)
                    draw.text((x + img_width // 2, y + img_height // 2), "N/A",
                              fill=(150, 150, 150), font=label_font, anchor="mm")
            
            current_y += img_height + cell_label_height + gap_size
        
        # Draw prompt text at bottom
        if prompt_text and prompt_height > 0:
            wrapped = self._wrap_text(prompt_text, prompt_font, grid_width - gap_size * 4)
            # Truncate and show as single line (anchor doesn't work with multiline)
            display_text = f"Prompt: {wrapped[:500]}..." if len(wrapped) > 500 else f"Prompt: {wrapped}"
            # Replace newlines with spaces for single-line display
            display_text = display_text.replace('\n', ' ')
            draw.text((grid_width // 2, current_y + 15), display_text,
                      fill=(80, 80, 80), font=prompt_font, anchor="mt")
        
        return grid_img
    
    def _create_row_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """Create a simple horizontal row grid when there's only one dimension."""
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        img_width, img_height = images[0].size
        
        # Layout: title + header row + single row of images
        label_font = self._get_font(font_name, int(font_size * 0.6))
        title_font = self._get_font(font_name, font_size)
        text_rgb = self._parse_color(text_color)
        border_rgb = self._parse_color(border_color)
        
        title_height = font_size + 30 if title else 0
        label_height = int(font_size * 0.8) + 10
        
        num_cols = len(images)
        grid_width = num_cols * (img_width + gap_size) + gap_size
        grid_height = title_height + img_height + label_height + gap_size * 2
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        current_y = gap_size
        
        # Title
        if title:
            draw.text((grid_width // 2, current_y + font_size // 2), title,
                      fill=text_rgb, font=title_font, anchor="mm")
            current_y += title_height
        
        # Images in row
        for idx, (img, label) in enumerate(zip(images, labels)):
            x = gap_size + idx * (img_width + gap_size)
            
            # Border
            if border_width > 0:
                for i in range(border_width):
                    draw.rectangle(
                        [(x - i, current_y - i), (x + img_width + i, current_y + img_height + i)],
                        outline=border_rgb, width=1
                    )
            
            # Image
            grid_img.paste(img, (x, current_y))
            
            # Label
            short_label = label.split('|')[-1].strip() if '|' in label else label
            if len(short_label) > 30:
                short_label = short_label[:27] + "..."
            draw.text((x + img_width // 2, current_y + img_height + 5), short_label,
                      fill=text_rgb, font=label_font, anchor="mt")
        
        return grid_img
    
    def _create_hierarchical_grid(
        self,
        images: List[Image.Image],
        combinations: List[Dict],
        config: Dict[str, Any],
        row_hierarchy: List[str],
        col_hierarchy: List[str],
        format_config: Dict[str, Any],
        title: str = "",
        external_varying_dims: Dict[str, Any] = None,
        subtitle_config: Dict[str, bool] = None,
    ) -> Image.Image:
        """
        Create a hierarchical pivot-table grid with merged headers.
        
        Uses RaggedGridRenderer for proper tree-based layout that handles:
        - Models with different LoRA configurations
        - Sparse combinations (not full Cartesian product)
        - Proper header merging based on actual data
        
        Falls back to Cartesian layout if ragged renderer unavailable.
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        print(f"[GridCompare] _create_hierarchical_grid: {len(images)} images, {len(combinations)} combos")
        print(f"[GridCompare] row_hierarchy={row_hierarchy}, col_hierarchy={col_hierarchy}")
        
        # Get varying dimensions
        if external_varying_dims:
            varying_dims = {}
            for field, info in external_varying_dims.items():
                if isinstance(info, dict) and 'values' in info:
                    varying_dims[field] = info['values']
                elif isinstance(info, list):
                    varying_dims[field] = info
                else:
                    varying_dims[field] = [info]
        else:
            varying_dims = self._detect_varying_dimensions(combinations, config)
        
        print(f"[GridCompare] varying_dims: {varying_dims}")
        
        # Try to use ragged grid renderer for tree-based layout
        if HAS_RAGGED_RENDERER:
            try:
                print(f"[GridCompare] Using RaggedHierarchyGrid for tree-based layout")
                
                # Create renderer with format config
                renderer = RaggedHierarchyGrid(
                    images=images,
                    combinations=combinations,
                    config=config,
                    row_hierarchy=row_hierarchy,
                    col_hierarchy=col_hierarchy,
                    format_config=format_config,
                    title=title,
                    subtitle_config=subtitle_config,
                )
                
                # Render the grid
                grid_image = renderer.render()
                
                if grid_image:
                    print(f"[GridCompare] RaggedHierarchyGrid produced {grid_image.size[0]}x{grid_image.size[1]} grid")
                    return grid_image
                else:
                    print(f"[GridCompare] RaggedHierarchyGrid returned None, falling back to Cartesian layout")
                    
            except Exception as e:
                print(f"[GridCompare] RaggedHierarchyGrid failed: {e}, falling back to Cartesian layout")
                import traceback
                traceback.print_exc()
        else:
            print(f"[GridCompare] RaggedHierarchyGrid not available, using Cartesian layout")
        
        # =========================================================================
        # FALLBACK: Original Cartesian product layout
        # =========================================================================
        
        # Extract styling from format_config for fallback
        header_colors = format_config.get('header_colors', ['#E8E8E8', '#D4D4D4', '#C0C0C0'])
        header_font_size = format_config.get('header_font_size', 32)
        header_font_name = format_config.get('header_font_name', 'default')
        header_text_color = format_config.get('header_text_color', '#1A1A1A')
        header_padding = format_config.get('header_padding', 12)
        gap_size = format_config.get('gap_size', 4)
        border_color = format_config.get('border_color', '#000000')
        border_width = format_config.get('border_width', 2)
        grid_background = format_config.get('grid_background', '#F0F0F0')
        title_font_size = format_config.get('title_font_size', 48)
        title_background = format_config.get('title_background', '#1A1A1A')
        title_text_color = format_config.get('title_text_color', '#FFFFFF')
        show_grid_title = format_config.get('show_grid_title', True)
        prompt_wrap_width = format_config.get('prompt_wrap_width', 80)
        
        # Get fonts
        title_font = self._get_font(header_font_name, title_font_size)
        header_font = self._get_font(header_font_name, header_font_size)
        small_header_font = self._get_font(header_font_name, max(12, header_font_size - 6))
        
        # Build row and column value lists
        row_values_list = []  # List of unique row value tuples
        col_values_list = []  # List of unique column value tuples
        
        for combo in combinations:
            row_vals = tuple(utils_get_combo_field_value(combo, config, f) for f in row_hierarchy) if row_hierarchy else ()
            col_vals = tuple(utils_get_combo_field_value(combo, config, f) for f in col_hierarchy) if col_hierarchy else ()
            
            if row_vals not in row_values_list:
                row_values_list.append(row_vals)
            if col_vals not in col_values_list:
                col_values_list.append(col_vals)
        
        print(f"[GridCompare] [FALLBACK] row_values_list: {row_values_list}")
        print(f"[GridCompare] [FALLBACK] col_values_list: {col_values_list}")
        
        # Build lookup map: (row_vals, col_vals) → image_index
        cell_to_image = {}
        for idx, combo in enumerate(combinations):
            row_vals = tuple(utils_get_combo_field_value(combo, config, f) for f in row_hierarchy) if row_hierarchy else ()
            col_vals = tuple(utils_get_combo_field_value(combo, config, f) for f in col_hierarchy) if col_hierarchy else ()
            cell_to_image[(row_vals, col_vals)] = idx
        
        print(f"[GridCompare] cell_to_image has {len(cell_to_image)} entries")
        
        # Calculate dimensions
        img_width, img_height = images[0].size
        
        num_rows = max(1, len(row_values_list))
        num_cols = max(1, len(col_values_list))
        
        # Subtitle font and height calculation
        # Check if any subtitle fields are enabled
        show_subtitles = subtitle_config and any(
            v for k, v in subtitle_config.items() if k != 'show_field_names' and v
        )
        subtitle_font_size = int(header_font_size * 0.6)
        subtitle_font = self._get_font(header_font_name, subtitle_font_size)
        subtitle_height = (subtitle_font_size + 8) if show_subtitles else 0  # Space below each image
        
        # Calculate dynamic row header width based on content
        # For prompts, we need more space with wrapping
        base_header_width = 150
        row_header_widths = []
        for level, field in enumerate(row_hierarchy):
            if field in ['prompt_positive', 'prompt_negative']:
                # Calculate width based on wrapped text
                max_text_width = prompt_wrap_width * 8  # Rough char width estimate
                row_header_widths.append(min(400, max(200, max_text_width)))
            elif field == 'lora_name' or field == 'lora_group_label':
                row_header_widths.append(180)  # Slightly wider for LoRA names
            else:
                row_header_widths.append(base_header_width)
        
        row_header_width = sum(row_header_widths) if row_header_widths else 0
        
        # Calculate column header height - check if we have prompts that need wrapping
        col_has_prompt = any(f in ['prompt_positive', 'prompt_negative'] for f in col_hierarchy)
        col_header_row_height = header_font_size + header_padding * 2
        if col_has_prompt:
            # Allow extra height for wrapped prompts (estimate 3 lines)
            col_header_row_height = (header_font_size * 3) + header_padding * 2
        col_header_height = col_header_row_height * len(col_hierarchy) if col_hierarchy else 0
        
        # Title height
        title_height = (title_font_size + 30) if (title and show_grid_title) else 0
        
        # Grid dimensions (include subtitle height in cell calculation)
        content_width = num_cols * (img_width + gap_size)
        content_height = num_rows * (img_height + subtitle_height + gap_size)
        
        grid_width = row_header_width + content_width + gap_size
        grid_height = title_height + col_header_height + content_height + gap_size
        
        print(f"[GridCompare] Grid: {grid_width}x{grid_height}, {num_cols} cols x {num_rows} rows")
        print(f"[GridCompare] Subtitles: show_subtitles={show_subtitles}, subtitle_height={subtitle_height}")
        
        # Create canvas
        grid_bg = self._parse_color(grid_background)
        grid_img = Image.new('RGB', (grid_width, grid_height), color=grid_bg)
        draw = ImageDraw.Draw(grid_img)
        
        # Draw title
        y_offset = gap_size
        if title and show_grid_title:
            title_bg = self._parse_color(title_background)
            title_text = self._parse_color(title_text_color)
            draw.rectangle([(0, 0), (grid_width, title_height)], fill=title_bg)
            draw.text((grid_width // 2, title_height // 2), title,
                      fill=title_text, font=title_font, anchor="mm")
            y_offset = title_height
        
        # Draw column headers (one header row per level in col_hierarchy)
        header_text = self._parse_color(header_text_color)
        for level, field in enumerate(col_hierarchy):
            level_y = y_offset + level * col_header_row_height
            color_idx = level % len(header_colors)
            header_bg = self._parse_color(header_colors[color_idx])
            
            for col_idx, col_vals in enumerate(col_values_list):
                x = row_header_width + col_idx * (img_width + gap_size)
                
                # Draw header cell background
                draw.rectangle(
                    [(x, level_y), (x + img_width, level_y + col_header_row_height)],
                    fill=header_bg
                )
                
                # Draw header text
                val = col_vals[level] if level < len(col_vals) else ""
                
                # Format the text based on field type
                if field in ['prompt_positive', 'prompt_negative']:
                    # Wrap prompt text
                    lines = format_prompt_for_header(str(val) if val else "", prompt_wrap_width)
                    text = '\n'.join(lines) if lines else ""
                    # Use smaller font for multi-line prompts
                    use_font = small_header_font if len(lines) > 1 else header_font
                    draw.text(
                        (x + img_width // 2, level_y + col_header_row_height // 2),
                        text, fill=header_text, font=use_font, anchor="mm"
                    )
                elif field.endswith('_strength') and field != 'lora_strength':
                    # Per-LoRA strength dimension
                    lora_name = field[:-9]  # Remove '_strength'
                    text = f"{lora_name}: {self._format_value(val)}"
                    draw.text(
                        (x + img_width // 2, level_y + col_header_row_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
                elif field == 'lora_strength':
                    # Format strength tuple or single value
                    if isinstance(val, tuple):
                        text = "(" + ",".join(f"{v:.1f}".rstrip('0').rstrip('.') for v in val) + ")"
                    else:
                        text = f"{val:.1f}".rstrip('0').rstrip('.') if isinstance(val, (int, float)) else str(val)
                    draw.text(
                        (x + img_width // 2, level_y + col_header_row_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
                else:
                    text = self._format_value(val)
                    if len(text) > 30:
                        text = text[:27] + "..."
                    draw.text(
                        (x + img_width // 2, level_y + col_header_row_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
        
        # Calculate image area start
        img_area_y = y_offset + col_header_height
        
        # Draw row headers and images
        for row_idx, row_vals in enumerate(row_values_list):
            # Account for subtitle height in row spacing
            y = img_area_y + row_idx * (img_height + subtitle_height + gap_size)
            
            # Draw row headers (one per level in row_hierarchy)
            # Row headers span the image height but not subtitle area
            level_x = 0
            for level, field in enumerate(row_hierarchy):
                header_w = row_header_widths[level] if level < len(row_header_widths) else base_header_width
                color_idx = level % len(header_colors)
                header_bg = self._parse_color(header_colors[color_idx])
                
                draw.rectangle(
                    [(level_x, y), (level_x + header_w, y + img_height)],
                    fill=header_bg
                )
                
                # Get value for this row level
                val = row_vals[level] if level < len(row_vals) else ""
                
                # Format text based on field type
                if field in ['prompt_positive', 'prompt_negative']:
                    # Wrap prompt text for row headers
                    lines = format_prompt_for_header(str(val) if val else "", prompt_wrap_width)
                    text = '\n'.join(lines) if lines else ""
                    use_font = small_header_font
                    draw.text(
                        (level_x + header_w // 2, y + img_height // 2),
                        text, fill=header_text, font=use_font, anchor="mm"
                    )
                elif field == 'lora_name' or field == 'lora_group_label':
                    # LoRA name or group label - show full name
                    text = str(val) if val else ""
                    if len(text) > 25:
                        text = text[:22] + "..."
                    draw.text(
                        (level_x + header_w // 2, y + img_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
                elif field.endswith('_strength') and field != 'lora_strength':
                    # Per-LoRA strength dimension
                    lora_name = field[:-9]
                    text = f"{lora_name}: {self._format_value(val)}"
                    draw.text(
                        (level_x + header_w // 2, y + img_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
                elif field == 'lora_strength':
                    # Format strength tuple or single value
                    if isinstance(val, tuple):
                        text = "(" + ",".join(f"{v:.1f}".rstrip('0').rstrip('.') for v in val) + ")"
                    else:
                        text = f"{val:.1f}".rstrip('0').rstrip('.') if isinstance(val, (int, float)) else str(val)
                    draw.text(
                        (level_x + header_w // 2, y + img_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
                else:
                    text = self._format_value(val)
                    if len(text) > 20:
                        text = text[:17] + "..."
                    draw.text(
                        (level_x + header_w // 2, y + img_height // 2),
                        text, fill=header_text, font=header_font, anchor="mm"
                    )
                
                level_x += header_w
            
            # Draw images for this row
            for col_idx, col_vals in enumerate(col_values_list):
                x = row_header_width + col_idx * (img_width + gap_size)
                
                # Look up image for this cell
                img_idx = cell_to_image.get((row_vals, col_vals))
                
                if img_idx is not None and img_idx < len(images):
                    img = images[img_idx]
                    combo = combinations[img_idx] if img_idx < len(combinations) else {}
                    
                    # Resize if needed
                    if img.size != (img_width, img_height):
                        img = img.resize((img_width, img_height), Image.LANCZOS)
                    
                    # Draw border
                    if border_width > 0:
                        border_rgb = self._parse_color(border_color)
                        draw.rectangle(
                            [(x - border_width, y - border_width), 
                             (x + img_width + border_width, y + img_height + border_width)],
                            outline=border_rgb, width=border_width
                        )
                    
                    # Paste image
                    grid_img.paste(img, (x, y))
                    
                    # Draw subtitle below image
                    if show_subtitles and subtitle_height > 0:
                        # Generate subtitle using _generate_cell_label
                        # Exclude fields shown in row/col hierarchy
                        exclude_fields = list(row_hierarchy) + list(col_hierarchy)
                        subtitle = self._generate_cell_label(
                            combo, config, varying_dims,
                            exclude_axes=exclude_fields,
                            subtitle_filter=subtitle_config,
                            show_field_names=subtitle_config.get('show_field_names', False) if subtitle_config else False
                        )
                        if subtitle:
                            # Truncate if too long
                            max_subtitle_len = img_width // (subtitle_font_size // 2)
                            if len(subtitle) > max_subtitle_len:
                                subtitle = subtitle[:max_subtitle_len - 3] + "..."
                            # Draw centered below image
                            draw.text(
                                (x + img_width // 2, y + img_height + 4),
                                subtitle, fill=header_text, font=subtitle_font, anchor="mt"
                            )
                else:
                    # No image for this cell - draw placeholder
                    draw.rectangle([(x, y), (x + img_width, y + img_height)], 
                                   fill=self._parse_color('#CCCCCC'))
                    draw.text((x + img_width // 2, y + img_height // 2), "?",
                              fill=header_text, font=header_font, anchor="mm")
        
        return grid_img
    
    def _build_hierarchy_tree(
        self,
        combinations: List[Dict],
        config: Dict[str, Any],
        hierarchy: List[str],
        varying_dims: Dict[str, List[Any]],
    ) -> Dict:
        """
        Build a nested tree structure representing the hierarchy.
        
        Returns a dict like:
        {
            'value1': {
                'value1a': {'_indices': [0, 1]},
                'value1b': {'_indices': [2, 3]},
            },
            'value2': {...}
        }
        """
        if not hierarchy:
            # Leaf level - just return indices
            return {'_indices': list(range(len(combinations)))}
        
        tree = {}
        field = hierarchy[0]
        remaining = hierarchy[1:]
        
        # Get unique values for this field
        values = varying_dims.get(field, [])
        if not values:
            # Field not varying, treat as single value
            values = ['default']
        
        for val in values:
            # Find combinations matching this value
            matching_indices = []
            for idx, combo in enumerate(combinations):
                combo_val = self._get_combo_field_value(combo, config, field)
                if combo_val == val or (combo_val is None and val == 'default'):
                    matching_indices.append(idx)
            
            if matching_indices:
                if remaining:
                    # Recurse with filtered combinations
                    filtered_combos = [combinations[i] for i in matching_indices]
                    sub_tree = self._build_hierarchy_tree(
                        filtered_combos, config, remaining, varying_dims
                    )
                    # Remap indices back to original
                    sub_tree = self._remap_tree_indices(sub_tree, matching_indices)
                    tree[val] = sub_tree
                else:
                    tree[val] = {'_indices': matching_indices}
        
        return tree
    
    def _remap_tree_indices(self, tree: Dict, index_map: List[int]) -> Dict:
        """Remap tree indices from filtered to original."""
        if '_indices' in tree:
            return {'_indices': [index_map[i] for i in tree['_indices']]}
        
        remapped = {}
        for key, subtree in tree.items():
            remapped[key] = self._remap_tree_indices(subtree, index_map)
        return remapped
    
    def _count_hierarchy_leaves(self, tree: Dict) -> int:
        """Count total leaf nodes in hierarchy tree."""
        if '_indices' in tree:
            return len(tree['_indices'])
        
        count = 0
        for key, subtree in tree.items():
            count += self._count_hierarchy_leaves(subtree)
        return count if count > 0 else 1
    
    def _draw_hierarchical_headers(
        self,
        draw: ImageDraw.Draw,
        tree: Dict,
        hierarchy: List[str],
        header_colors: List[str],
        header_font_name: str,
        header_font_size: int,
        header_text_color: str,
        header_heights: List[int],
        x_start: int,
        y_start: int,
        cell_width: int,
        is_column: bool,
        scale_font: bool,
        depth: int = 0,
    ) -> int:
        """
        Draw hierarchical headers recursively.
        Returns the total width/height used.
        """
        if '_indices' in tree:
            # Leaf level - no more headers to draw
            return len(tree['_indices']) * cell_width
        
        if not hierarchy:
            return 0
        
        current_x = x_start
        header_height = header_heights[depth] if depth < len(header_heights) else header_heights[-1]
        
        # Get color for this depth
        color_idx = depth % len(header_colors)
        bg_color = self._parse_color(header_colors[color_idx])
        text_color = self._parse_color(header_text_color)
        
        # Scale font by depth if enabled
        font_size = header_font_size
        if scale_font and depth > 0:
            font_size = max(12, header_font_size - depth * 4)
        font = self._get_font(header_font_name, font_size)
        
        for val, subtree in tree.items():
            # Calculate span for this header
            span = self._count_hierarchy_leaves(subtree)
            header_width = span * cell_width - (cell_width - 1)  # Remove last gap
            
            if is_column:
                # Draw column header
                rect_x1 = current_x
                rect_y1 = y_start
                rect_x2 = current_x + header_width
                rect_y2 = y_start + header_height
                
                draw.rectangle([(rect_x1, rect_y1), (rect_x2, rect_y2)], fill=bg_color)
                
                # Draw text centered
                text = self._format_value(val)
                draw.text(((rect_x1 + rect_x2) // 2, (rect_y1 + rect_y2) // 2), 
                          text, fill=text_color, font=font, anchor="mm")
            
            # Recurse for child levels
            if len(hierarchy) > 1:
                self._draw_hierarchical_headers(
                    draw=draw,
                    tree=subtree,
                    hierarchy=hierarchy[1:],
                    header_colors=header_colors,
                    header_font_name=header_font_name,
                    header_font_size=header_font_size,
                    header_text_color=header_text_color,
                    header_heights=header_heights,
                    x_start=current_x,
                    y_start=y_start + header_height if is_column else y_start,
                    cell_width=cell_width,
                    is_column=is_column,
                    scale_font=scale_font,
                    depth=depth + 1,
                )
            
            current_x += span * cell_width
        
        return current_x - x_start
    
    def _draw_rows_with_headers(
        self,
        draw: ImageDraw.Draw,
        grid_img: Image.Image,
        images: List[Image.Image],
        combinations: List[Dict],
        config: Dict[str, Any],
        row_tree: Dict,
        col_tree: Dict,
        row_hierarchy: List[str],
        col_hierarchy: List[str],
        header_colors: List[str],
        header_font_name: str,
        header_font_size: int,
        header_text_color: str,
        row_header_widths: List[int],
        x_start: int,
        y_start: int,
        img_width: int,
        img_height: int,
        gap_size: int,
        border_color: str,
        border_width: int,
        scale_font: bool,
        varying_dims: Dict[str, List[Any]],
        depth: int = 0,
    ) -> int:
        """
        Draw row headers and images recursively.
        Returns total height used.
        """
        if '_indices' in row_tree:
            # Leaf level - draw images
            indices = row_tree['_indices']
            current_y = y_start
            
            for row_idx, img_idx in enumerate(indices):
                if img_idx >= len(images):
                    continue
                
                # Draw images across all columns
                col_x = x_start + sum(row_header_widths)
                self._draw_image_row(
                    draw=draw,
                    grid_img=grid_img,
                    images=images,
                    col_tree=col_tree,
                    img_idx=img_idx,
                    x_start=col_x,
                    y=current_y,
                    img_width=img_width,
                    img_height=img_height,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                )
                current_y += img_height + gap_size
            
            return len(indices) * (img_height + gap_size)
        
        current_y = y_start
        header_width = row_header_widths[depth] if depth < len(row_header_widths) else row_header_widths[-1]
        
        # Get color for this depth
        color_idx = depth % len(header_colors)
        bg_color = self._parse_color(header_colors[color_idx])
        text_color = self._parse_color(header_text_color)
        
        # Scale font
        font_size = header_font_size
        if scale_font and depth > 0:
            font_size = max(12, header_font_size - depth * 4)
        font = self._get_font(header_font_name, font_size)
        
        for val, subtree in row_tree.items():
            # Calculate span
            span = self._count_hierarchy_leaves(subtree)
            header_height = span * (img_height + gap_size) - gap_size
            
            # Draw row header
            rect_x1 = x_start + sum(row_header_widths[:depth])
            rect_y1 = current_y
            rect_x2 = rect_x1 + header_width
            rect_y2 = current_y + header_height
            
            draw.rectangle([(rect_x1, rect_y1), (rect_x2, rect_y2)], fill=bg_color)
            
            # Draw text centered vertically, rotated if needed
            text = self._format_value(val)
            # For now, draw horizontal text
            draw.text(((rect_x1 + rect_x2) // 2, (rect_y1 + rect_y2) // 2),
                      text, fill=text_color, font=font, anchor="mm")
            
            # Recurse
            child_height = self._draw_rows_with_headers(
                draw=draw,
                grid_img=grid_img,
                images=images,
                combinations=combinations,
                config=config,
                row_tree=subtree,
                col_tree=col_tree,
                row_hierarchy=row_hierarchy[1:] if len(row_hierarchy) > 1 else [],
                col_hierarchy=col_hierarchy,
                header_colors=header_colors,
                header_font_name=header_font_name,
                header_font_size=header_font_size,
                header_text_color=header_text_color,
                row_header_widths=row_header_widths,
                x_start=x_start,
                y_start=current_y,
                img_width=img_width,
                img_height=img_height,
                gap_size=gap_size,
                border_color=border_color,
                border_width=border_width,
                scale_font=scale_font,
                varying_dims=varying_dims,
                depth=depth + 1,
            )
            
            current_y += child_height
        
        return current_y - y_start
    
    def _draw_image_row(
        self,
        draw: ImageDraw.Draw,
        grid_img: Image.Image,
        images: List[Image.Image],
        col_tree: Dict,
        img_idx: int,
        x_start: int,
        y: int,
        img_width: int,
        img_height: int,
        gap_size: int,
        border_color: str,
        border_width: int,
    ):
        """Draw a single row of images following column hierarchy.
        
        img_idx is the base index for this row. We need to place images
        at positions determined by the column tree structure.
        """
        border_rgb = self._parse_color(border_color)
        
        # Traverse column tree to get column indices
        col_positions = self._get_column_positions(col_tree)
        
        current_x = x_start
        for col_idx, (col_offset, _) in enumerate(col_positions):
            actual_img_idx = img_idx + col_offset
            
            if actual_img_idx < len(images):
                img = images[actual_img_idx]
                
                # Resize if needed
                if img.size != (img_width, img_height):
                    img = img.resize((img_width, img_height), Image.LANCZOS)
                
                # Draw border
                if border_width > 0:
                    for i in range(border_width):
                        draw.rectangle(
                            [(current_x - i, y - i), (current_x + img_width + i, y + img_height + i)],
                            outline=border_rgb, width=1
                        )
                
                # Paste image
                grid_img.paste(img, (current_x, y))
            
            current_x += img_width + gap_size
    
    def _get_column_positions(self, col_tree: Dict, offset: int = 0) -> List[Tuple[int, Any]]:
        """
        Get flat list of (offset, value) for all column leaf positions.
        offset is relative to the start of this subtree.
        """
        if '_indices' in col_tree:
            # Leaf level - return positions
            return [(i, None) for i in col_tree['_indices']]
        
        positions = []
        for val, subtree in col_tree.items():
            sub_positions = self._get_column_positions(subtree)
            positions.extend(sub_positions)
        return positions

    def _create_nested_xy_grids(
        self,
        images: List[Image.Image],
        labels: List[str],
        combinations: List[Dict],
        config: Dict[str, Any],
        row_axis: str,
        col_axis: str,
        nest_axes: List[str],
        varying_dims: Dict[str, List[Any]],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
        max_grid_pixels: int = 8000,
    ) -> Image.Image:
        """
        Create nested grids when there are 3+ varying dimensions.
        Creates one XY grid for each value of the nest_axis, then combines them.
        
        Args:
            nest_axes: List of field names to use for nesting (up to 8 levels)
            max_grid_pixels: Maximum dimension before auto-splitting into separate grids
            
        Layout: Multiple XY grids stacked vertically or horizontally, one per nest_axis value.
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Use first nest axis - remaining axes will be handled recursively
        nest_axis = nest_axes[0] if nest_axes else "auto"
        remaining_nest_axes = nest_axes[1:] if len(nest_axes) > 1 else []
        
        # Determine the nest axis (third dimension)
        priority = ['scheduler', 'sampler_name', 'height', 'lumina_shift', 'qwen_shift', 
                    'wan_shift', 'hunyuan_shift', 'flux_guidance', 'width', 'cfg', 'steps', 
                    'model', 'seed', 'lora_name', 'lora_strength', 'vae', 'clip']
        
        # Auto-detect row and col axes if needed
        actual_row_axis = row_axis
        actual_col_axis = col_axis
        actual_nest_axis = nest_axis
        
        used_axes = set()
        
        if row_axis == "auto":
            for p in priority:
                if p in varying_dims:
                    actual_row_axis = p
                    used_axes.add(p)
                    break
        else:
            used_axes.add(row_axis)
        
        if col_axis == "auto":
            for p in priority:
                if p in varying_dims and p not in used_axes:
                    actual_col_axis = p
                    used_axes.add(p)
                    break
        else:
            used_axes.add(col_axis)
        
        # Auto-detect nest axis if "auto" or "none" but we have 3+ dimensions
        if nest_axis in ("auto", "none") and len(varying_dims) > 2:
            for p in priority:
                if p in varying_dims and p not in used_axes:
                    actual_nest_axis = p
                    break
        elif nest_axis not in ("auto", "none"):
            actual_nest_axis = nest_axis
        
        # If no nest axis found but we have 3+ dims, use the third varying dimension
        if actual_nest_axis in ("auto", "none") and len(varying_dims) > 2:
            for dim in varying_dims:
                if dim not in used_axes:
                    actual_nest_axis = dim
                    break
        
        # If we still don't have a valid nest axis, fall back to regular XY grid
        if actual_nest_axis in ("auto", "none") or actual_nest_axis not in varying_dims:
            return self._create_xy_grid(
                images=images, labels=labels, combinations=combinations, config=config,
                row_axis=actual_row_axis, col_axis=actual_col_axis,
                gap_size=gap_size, border_color=border_color, border_width=border_width,
                text_color=text_color, font_size=font_size, font_name=font_name,
                title=title, show_positive_prompt=show_positive_prompt,
                show_negative_prompt=show_negative_prompt, varying_dims=varying_dims
            )
        
        # Get nest axis values
        nest_values = varying_dims.get(actual_nest_axis, [])
        if not nest_values:
            return self._create_xy_grid(
                images=images, labels=labels, combinations=combinations, config=config,
                row_axis=actual_row_axis, col_axis=actual_col_axis,
                gap_size=gap_size, border_color=border_color, border_width=border_width,
                text_color=text_color, font_size=font_size, font_name=font_name,
                title=title, show_positive_prompt=show_positive_prompt,
                show_negative_prompt=show_negative_prompt, varying_dims=varying_dims
            )
        
        # Group images by nest axis value
        nested_groups = {}  # nest_value -> [(idx, image, label, combo)]
        for idx, (img, combo) in enumerate(zip(images, combinations)):
            label = labels[idx] if idx < len(labels) else f"Image {idx}"
            nest_val = self._get_combo_field_value(combo, config, actual_nest_axis)
            
            if nest_val not in nested_groups:
                nested_groups[nest_val] = []
            nested_groups[nest_val].append((idx, img, label, combo))
        
        # Create XY grid for each nest value
        sub_grids = []
        for nest_val in nest_values:
            if nest_val not in nested_groups:
                continue
            
            group_items = nested_groups[nest_val]
            group_images = [item[1] for item in group_items]
            group_labels = [item[2] for item in group_items]
            group_combos = [item[3] for item in group_items]
            
            # Create sub-title showing nest axis value
            nest_label = f"{self._format_axis_label(actual_nest_axis)}: {self._format_value(nest_val)}"
            sub_title = f"{title} [{nest_label}]" if title else nest_label
            
            # Compute varying dims for the sub-group
            sub_varying = self._detect_varying_dimensions(group_combos, config)
            
            # Check if we have more nest axes OR if sub-group still has >2 varying dimensions
            # This enables RECURSIVE nesting to handle all dimensions
            sub_unused_dims = [d for d in sub_varying.keys() 
                               if d not in {actual_row_axis, actual_col_axis, actual_nest_axis}]
            
            if remaining_nest_axes or (len(sub_varying) > 2 and sub_unused_dims):
                # RECURSIVE: Continue nesting with remaining axes
                effective_nest_axes = remaining_nest_axes if remaining_nest_axes else sub_unused_dims
                print(f"[_create_nested_xy_grids] Recursive nesting for '{nest_val}' with axes: {effective_nest_axes}")
                
                sub_grid = self._create_nested_xy_grids(
                    images=group_images,
                    labels=group_labels,
                    combinations=group_combos,
                    config=config,
                    row_axis=actual_row_axis,
                    col_axis=actual_col_axis,
                    nest_axes=effective_nest_axes,
                    varying_dims=sub_varying,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=sub_title,
                    show_positive_prompt=False,
                    show_negative_prompt=False,
                    max_grid_pixels=max_grid_pixels,
                )
            else:
                # BASE CASE: No more nesting needed, create XY grid
                sub_grid = self._create_xy_grid(
                    images=group_images,
                    labels=group_labels,
                    combinations=group_combos,
                    config=config,
                    row_axis=actual_row_axis,
                    col_axis=actual_col_axis,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=sub_title,
                    show_positive_prompt=False,  # Only show prompt once at the end
                    show_negative_prompt=False,
                    varying_dims=sub_varying,
                )
            sub_grids.append((nest_val, sub_grid))
        
        if not sub_grids:
            return Image.new('RGB', (100, 100), color='white')
        
        # Combine sub-grids vertically with separator and nest axis label
        # Calculate combined dimensions
        max_width = max(sg[1].width for sg in sub_grids)
        total_height = sum(sg[1].height for sg in sub_grids) + (len(sub_grids) - 1) * gap_size * 2
        
        # Create combined canvas
        combined = Image.new('RGB', (max_width, total_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(combined)
        border_rgb = self._parse_color(border_color)
        
        current_y = 0
        for i, (nest_val, sub_grid) in enumerate(sub_grids):
            # Center sub-grid horizontally
            x_offset = (max_width - sub_grid.width) // 2
            combined.paste(sub_grid, (x_offset, current_y))
            current_y += sub_grid.height
            
            # Add separator between grids
            if i < len(sub_grids) - 1:
                sep_y = current_y + gap_size
                draw.line([(gap_size * 2, sep_y), (max_width - gap_size * 2, sep_y)], 
                          fill=border_rgb, width=2)
                current_y += gap_size * 2
        
        # Draw prompt at bottom if requested
        if show_positive_prompt:
            prompt_variations = config.get("prompt_variations", [])
            if prompt_variations:
                prompt_text = prompt_variations[0].get("positive", "")
                if prompt_text:
                    prompt_font = self._get_font(font_name, int(font_size * 0.5))
                    wrapped = self._wrap_text(prompt_text, prompt_font, max_width - gap_size * 4)
                    display_text = f"Prompt: {wrapped[:500]}..." if len(wrapped) > 500 else f"Prompt: {wrapped}"
                    display_text = display_text.replace('\n', ' ')
                    draw.text((max_width // 2, current_y - gap_size // 2), display_text,
                              fill=(80, 80, 80), font=prompt_font, anchor="mt")
        
        return combined

    def _create_complete_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        combinations: List[Dict],
        config: Dict[str, Any],
        varying_dims: Dict[str, List[Any]],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
    ) -> Image.Image:
        """
        Create a complete grid showing ALL images with full labels.
        This is used when we have 3+ varying dimensions and need to show every combination.
        
        Layout: Grid where each cell shows one image with its full variation label.
        Dimensions: Calculates optimal rows/cols to fit all images.
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get image dimensions
        img_width, img_height = images[0].size
        
        # Calculate optimal grid layout (try to make it roughly square)
        num_images = len(images)
        # Calculate cols based on sqrt, but cap at a reasonable number
        num_cols = min(int(num_images ** 0.5) + 1, 8)  # Max 8 columns
        num_rows = (num_images + num_cols - 1) // num_cols
        
        # Font setup
        title_font = self._get_font(font_name, font_size)
        header_font = self._get_font(font_name, int(font_size * 0.7))
        label_font = self._get_font(font_name, int(font_size * 0.5))
        prompt_font = self._get_font(font_name, int(font_size * 0.45))
        text_rgb = self._parse_color(text_color)
        border_rgb = self._parse_color(border_color)
        
        # Spacing - increased label height for multi-line labels
        title_height = font_size + 40 if title else 0
        cell_label_height = int(font_size * 1.2) + 25  # More space for labels
        
        # Calculate prompt height
        prompt_height = 0
        prompt_text = ""
        if show_positive_prompt:
            prompt_variations = config.get("prompt_variations", [])
            if prompt_variations:
                prompt_text = prompt_variations[0].get("positive", "")
            # Fallback to combinations
            if not prompt_text and combinations:
                for combo in combinations:
                    prompt_text = combo.get("prompt_positive", "")
                    if prompt_text:
                        break
            if prompt_text:
                prompt_height = int(font_size * 0.6) * 2 + 30
        
        # Grid dimensions
        grid_width = num_cols * (img_width + gap_size) + gap_size
        grid_height = (title_height + 
                       num_rows * (img_height + cell_label_height + gap_size) + 
                       gap_size + prompt_height)
        
        # Create canvas
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        current_y = gap_size
        
        # Draw title
        if title:
            draw.text((grid_width // 2, current_y + font_size // 2), title, 
                      fill=text_rgb, font=title_font, anchor="mm")
            current_y += title_height
        
        # Draw images in grid
        for idx, (img, label) in enumerate(zip(images, labels)):
            row = idx // num_cols
            col = idx % num_cols
            
            x = gap_size + col * (img_width + gap_size)
            y = current_y + row * (img_height + cell_label_height + gap_size)
            
            # Resize if needed
            if img.size != (img_width, img_height):
                img = img.resize((img_width, img_height), Image.LANCZOS)
            
            # Draw border
            if border_width > 0:
                for i in range(border_width):
                    draw.rectangle(
                        [(x - i, y - i), (x + img_width + i, y + img_height + i)],
                        outline=border_rgb, width=1
                    )
            
            # Paste image
            grid_img.paste(img, (x, y))
            
            # Draw label below image - show key varying values
            if label:
                # Truncate long labels
                display_label = label[:60] + "..." if len(label) > 60 else label
                display_label = display_label.replace('\n', ' ')
                draw.text((x + img_width // 2, y + img_height + 12), display_label,
                          fill=text_rgb, font=label_font, anchor="mt")
        
        # Draw prompt text at bottom
        if prompt_text and prompt_height > 0:
            final_y = current_y + num_rows * (img_height + cell_label_height + gap_size)
            wrapped = self._wrap_text(prompt_text, prompt_font, grid_width - gap_size * 4)
            display_text = f"Prompt: {wrapped[:500]}..." if len(wrapped) > 500 else f"Prompt: {wrapped}"
            display_text = display_text.replace('\n', ' ')
            draw.text((grid_width // 2, final_y + 15), display_text,
                      fill=(80, 80, 80), font=prompt_font, anchor="mt")
        
        return grid_img

    def _split_grids_by_dimension(
        self,
        images: List[Image.Image],
        labels: List[str],
        config: Dict[str, Any],
        split_by: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
    ) -> List[Dict]:
        """
        Split images into multiple grids based on a dimension.
        Each unique value of split_by dimension gets its own grid.
        
        Returns a list of {"image": PIL.Image, "label": str} dicts.
        """
        if not images:
            return []
        
        # Get combinations from config
        combinations = config.get("combinations", [])
        
        # Detect varying dimensions
        varying_dims = self._detect_varying_dimensions(combinations)
        
        # Determine which dimension to split by
        if split_by == "auto":
            # Auto-select: choose the dimension with fewest unique values
            if not varying_dims:
                # Nothing to split by
                return []
            # Sort by number of unique values and pick the one with most variation
            # (to create meaningful sub-grids)
            sorted_dims = sorted(varying_dims.items(), key=lambda x: len(x[1]), reverse=True)
            split_by = sorted_dims[0][0] if sorted_dims else None
        
        if not split_by or split_by not in varying_dims:
            return []
        
        split_values = varying_dims[split_by]
        
        # Group images by split dimension value
        split_groups = {}
        for idx, combo in enumerate(combinations):
            if idx >= len(images):
                break
            
            # Get the value for this split dimension
            split_val = combo.get(split_by)
            if split_val is None:
                # Try fallback mappings
                if split_by == "sampler_name":
                    split_val = combo.get("sampler")
                elif split_by == "scheduler":
                    split_val = combo.get("sched")
            
            # Handle list values (like lora_strengths)
            if isinstance(split_val, (list, tuple)):
                split_val = str(split_val)
            
            split_val_key = str(split_val) if split_val is not None else "unknown"
            
            if split_val_key not in split_groups:
                split_groups[split_val_key] = {
                    "images": [],
                    "labels": [],
                    "combinations": [],
                    "value": split_val
                }
            
            split_groups[split_val_key]["images"].append(images[idx])
            split_groups[split_val_key]["labels"].append(labels[idx] if idx < len(labels) else "")
            split_groups[split_val_key]["combinations"].append(combo)
        
        # Create a sub-grid for each group
        result_grids = []
        for split_val_key, group in split_groups.items():
            sub_title = f"{title} [{self._format_axis_label(split_by)}: {self._format_value(group['value'])}]" if title else f"{self._format_axis_label(split_by)}: {self._format_value(group['value'])}"
            
            # Create a grid for this subset - use complete grid approach to show ALL images
            sub_grid = self._create_complete_grid(
                images=group["images"],
                labels=group["labels"],
                combinations=group["combinations"],
                config=config,
                varying_dims={k: v for k, v in varying_dims.items() if k != split_by},
                gap_size=gap_size,
                border_color=border_color,
                border_width=border_width,
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                title=sub_title,
                show_positive_prompt=show_positive_prompt,
                show_negative_prompt=show_negative_prompt,
            )
            
            result_grids.append({
                "image": sub_grid,
                "label": f"{self._format_axis_label(split_by)}_{self._format_value(group['value'])}"
            })
        
        return result_grids

    def _format_axis_label(self, axis: str) -> str:
        """Format axis name for display."""
        labels = {
            'sampler_name': 'Sampler',
            'scheduler': 'Scheduler',
            'steps': 'Steps',
            'cfg': 'CFG',
            'width': 'W',
            'height': 'H',
            'lumina_shift': 'Shift',
            'qwen_shift': 'Q-Shift',
            'wan_shift': 'W-Shift',
            'wan22_shift': 'W22-Shift',
            'hunyuan_shift': 'HY-Shift',
            'flux_guidance': 'Flux-G',
            'model': 'Model',
            'seed': 'Seed',
            'lora_name': 'LoRA',
            'lora_strength': 'LoRA Str',
            'lora_names': 'LoRAs',
            'lora_strengths': 'LoRA Strs',
            'vae': 'VAE',
            'clip': 'CLIP',
            'denoise': 'Denoise',
            'prompt_positive': 'Pos Prompt',
            'prompt_negative': 'Neg Prompt',
        }
        return labels.get(axis, axis)
    
    def _format_value(self, value: Any, max_length: int = 50) -> str:
        """Format a value for display, with optional truncation for long strings."""
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}".rstrip('0').rstrip('.')
        if isinstance(value, tuple):
            # Format tuples compactly for LoRA strengths like (0,1,0)
            formatted = '(' + ','.join(
                f"{v:.1f}".rstrip('0').rstrip('.') if isinstance(v, float) else str(v)
                for v in value
            ) + ')'
            return formatted
        if isinstance(value, str):
            # Remove .safetensors extension
            if value.endswith('.safetensors'):
                value = value[:-12]
            # Truncate long strings (like prompts)
            if len(value) > max_length:
                return value[:max_length-3] + "..."
        return str(value)
    
    def _shorten_label(self, label: str, row_axis: str, col_axis: str) -> str:
        """Remove row/col axis info from label since it's already shown in headers."""
        if not label:
            return ""
        
        # Parse label parts (format: "model | S:euler | Sch:normal | h:1024 | lsh:3")
        parts = [p.strip() for p in label.split('|')]
        
        # Map axis names to label prefixes
        axis_prefixes = {
            'sampler_name': 'S:',
            'scheduler': 'Sch:',
            'height': 'h:',
            'width': 'w:',
            'lumina_shift': 'lsh:',
            'cfg': 'cfg:',
            'steps': 'st:',
        }
        
        # Remove parts that match row or col axis
        filtered = []
        row_prefix = axis_prefixes.get(row_axis, '')
        col_prefix = axis_prefixes.get(col_axis, '')
        
        for part in parts:
            if row_prefix and part.startswith(row_prefix):
                continue
            if col_prefix and part.startswith(col_prefix):
                continue
            # Also skip model name (first part usually)
            if '[Diffusion]' in part or '.safetensors' in part:
                continue
            filtered.append(part)
        
        result = ' | '.join(filtered)
        if len(result) > 40:
            result = result[:37] + "..."
        return result

    def _detect_varying_parameters(self, config: Dict[str, Any]) -> Tuple[int, int]:
        """
        Analyze the config to determine grid dimensions based on AND/OR logic.
        Rows = number of OR groups (one row per OR-separated LoRA)
        Cols = number of strength variations
        """
        if "combinations" not in config or not config["combinations"]:
            return 1, 1
        
        combinations = config["combinations"]
        num_combinations = len(combinations)
        
        # Get LoRA combiners to determine grid rows
        lora_combiners = config.get('lora_combiners', [])
        if not lora_combiners:
            # No combiners info, use square-ish layout
            cols = max(1, int(num_combinations ** 0.5))
            rows = (num_combinations + cols - 1) // cols
            return rows, cols
        
        # Count OR operators to determine number of rows
        # OR separates LoRA groups, so row count = number of OR groups
        or_count = sum(1 for op in lora_combiners if op == 'OR')
        rows = or_count + 1  # OR count + 1 = number of groups/rows
        
        # Columns = combinations per row
        cols = num_combinations // max(1, rows) if rows > 0 else num_combinations
        
        return rows, cols

    def _organize_images_by_lora(self, config: Dict[str, Any], pil_images: List[Image.Image], labels: List[str]) -> Dict[str, Any]:
        """
        Organize images into a structure grouped by LoRA and strength.
        Parses labels to extract LoRA names and strength values (labels format: "LoRA_Name(strength)")
        Returns a dict with rows of images, where each row represents one LoRA with multiple strengths.
        """
        if not labels or not pil_images:
            return {
                "rows": [],
                "column_headers": [],
                "num_rows": 0,
                "num_cols": 0,
            }
        
        # Parse labels to extract LoRA names and strengths
        # Label format: "LoRA_Name(strength)" e.g., "Skin 1(0.00)"
        lora_groups = {}  # lora_name -> list of (strength, image, label, image_index)
        strength_values = set()
        
        for idx, label in enumerate(labels):
            if idx >= len(pil_images):
                break
            
            # Parse label to extract LoRA name and strength
            # Format: "LoRA_Name(strength)"
            if '(' in label and ')' in label:
                try:
                    # Split on the last opening parenthesis to handle LoRA names with numbers
                    last_paren = label.rfind('(')
                    lora_name = label[:last_paren].strip()
                    strength_str = label[last_paren+1:-1].strip()  # Remove '(' and ')'
                    strength = float(strength_str)
                    
                    if lora_name not in lora_groups:
                        lora_groups[lora_name] = []
                    
                    lora_groups[lora_name].append({
                        "strength": strength,
                        "image": pil_images[idx],
                        "label": label,
                        "image_index": idx,
                    })
                    
                    strength_values.add(strength)
                except (ValueError, IndexError) as e:
                    continue
            else:
                continue
        
        if not lora_groups or not strength_values:
            return {
                "rows": [],
                "column_headers": [],
                "num_rows": 0,
                "num_cols": 0,
            }
        
        # Sort strength values for column headers
        sorted_strengths = sorted(list(strength_values))
        
        # Organize into rows, maintaining order of first appearance
        rows = []
        lora_order = []  # Track order in which LoRAs first appeared
        
        for idx, label in enumerate(labels):
            if idx >= len(pil_images):
                break
            
            if '(' in label and ')' in label:
                try:
                    last_paren = label.rfind('(')
                    lora_name = label[:last_paren].strip()
                    
                    if lora_name not in lora_order:
                        lora_order.append(lora_name)
                except:
                    continue
        
        # Create rows in the order LoRAs first appeared
        for lora_name in lora_order:
            if lora_name in lora_groups:
                # Sort this LoRA's strengths
                lora_data = sorted(lora_groups[lora_name], key=lambda x: x["strength"])
                rows.append({
                    "lora_name": lora_name,
                    "images": lora_data,
                })
        
        return {
            "rows": rows,
            "column_headers": sorted_strengths,
            "num_rows": len(rows),
            "num_cols": len(sorted_strengths),
        }

    def _get_unique_values(self, config: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Extract unique values for each dimension from config."""
        # Extract from variations lists to maintain order
        models = []
        for m in config.get("model_variations", []):
            label = m.get("label", "")
            if not label:
                label = m["name"].replace("[Diffusion]", "").strip()
                if label.endswith(".safetensors"): label = label[:-12]
            models.append({"name": m["name"], "label": label})

        vaes = []
        for v in config.get("vae_variations", []):
            if isinstance(v, dict):
                name = v["name"]
                label = v.get("label", "")
                if not label:
                    label = name
                    if label.endswith(".safetensors"): label = label[:-12]
                vaes.append({"name": name, "label": label})
            else:
                # Fallback
                label = v
                if label.endswith(".safetensors"): label = label[:-12]
                vaes.append({"name": v, "label": label})
        
        # Extract CLIPs - handle both single (QWEN) and pair (FLUX) formats
        clips = []
        for c in config.get("clip_variations", []):
            label = c.get("label", "")
            if c.get("type") == "pair":
                name = f"{c['a']}/{c['b']}"
            else:
                name = c.get("model", "Unknown")
            
            if not label:
                label = name
                
            clips.append({"name": name, "label": label, "data": c})
            
        # Extract LoRA Groups and Strengths from combinations
        # We need to scan combinations to find all unique LoRA groups and their max strength counts
        lora_groups = []
        seen_groups = set()
        max_strengths = 0
        
        for combo in config.get("combinations", []):
            # Create a signature for the LoRA group
            names = tuple(combo.get("lora_names", []))
            if names not in seen_groups:
                seen_groups.add(names)
                # Create a display label for the group
                if not names:
                    label = "No LoRA"
                else:
                    # Use display names if available
                    display_names = combo.get("lora_display_names", names)
                    label = " + ".join(display_names)
                
                lora_groups.append({"names": names, "label": label})
            
            # Track max number of strengths (columns)
            strengths = combo.get("lora_strengths", ())
            max_strengths = max(max_strengths, len(strengths) if strengths else 1)

        return {
            "models": models,
            "vaes": vaes,
            "clips": clips,
            "lora_groups": lora_groups,
            "max_strengths": max_strengths
        }

    def _organize_nested_data(self, images: List[Image.Image], config: Dict[str, Any], unique_vals: Dict) -> Dict:
        """
        Organize images into a nested dictionary structure:
        data[clip_idx][group_idx][model_idx][vae_idx][strength_idx] = image
        """
        data = {}
        
        # Map unique values to indices for fast lookup
        model_to_idx = {m["name"]: i for i, m in enumerate(unique_vals["models"])}
        vae_to_idx = {v["name"]: i for i, v in enumerate(unique_vals["vaes"])}
        
        # CLIP mapping is trickier due to dict structure
        # We'll rely on the order in unique_vals["clips"] matching config["clip_variations"]
        # But we need to match the combo's clip_variation to our unique list
        
        combinations = config.get("combinations", [])
        
        for img_idx, combo in enumerate(combinations):
            if img_idx >= len(images):
                break
                
            image = images[img_idx]
            
            # Get indices
            model_name = combo.get("model")
            if model_name not in model_to_idx:
                continue # Should not happen if config is consistent
            m_idx = model_to_idx[model_name]
            
            vae_name = combo.get("vae")
            if vae_name not in vae_to_idx:
                continue
            v_idx = vae_to_idx[vae_name]
            
            # Find CLIP index
            # We compare the combo's clip_variation dict with our extracted clips
            c_idx = -1
            combo_clip = combo.get("clip_variation", {})
            for i, c in enumerate(unique_vals["clips"]):
                # Compare relevant fields
                if c["data"].get("type") == combo_clip.get("type"):
                    if c["data"].get("type") == "pair":
                        if c["data"].get("a") == combo_clip.get("a") and c["data"].get("b") == combo_clip.get("b"):
                            c_idx = i
                            break
                    else:
                        if c["data"].get("model") == combo_clip.get("model"):
                            c_idx = i
                            break
            if c_idx == -1: continue
            
            # Find LoRA Group index
            lora_names = tuple(combo.get("lora_names", []))
            g_idx = -1
            for i, g in enumerate(unique_vals["lora_groups"]):
                if g["names"] == lora_names:
                    g_idx = i
                    break
            if g_idx == -1: continue
            
            if c_idx not in data: data[c_idx] = {}
            if g_idx not in data[c_idx]: data[c_idx][g_idx] = {}
            if m_idx not in data[c_idx][g_idx]: data[c_idx][g_idx][m_idx] = {}
            if v_idx not in data[c_idx][g_idx][m_idx]: data[c_idx][g_idx][m_idx][v_idx] = []
            
            # Store image and its specific strength label
            strengths = combo.get("lora_strengths", ())
            # Generate a short label for the strength column (e.g. "0.1, 1.0")
            if not strengths:
                str_label = "-"
            else:
                str_label = ", ".join([f"{s:.2f}" for s in strengths])
                
            data[c_idx][g_idx][m_idx][v_idx].append({
                "image": image,
                "label": str_label,
                "full_strengths": strengths
            })
            
        return data

    def create_grid(
        self,
        images: torch.Tensor,
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        output_prefix: str = "compare",
        save_individuals: bool = False,
        save_metadata: bool = True,
        subtitle_fields: str = "",
        subtitle_show_field_names: bool = True,
        max_images_per_grid: int = 100,
        split_by_field: str = "auto",
        html_grid_output: bool = True,
        html_image_format: str = "PNG",
        html_image_quality: int = 100,
        # Optional inputs
        grid_layout: Dict[str, Any] = None,
        format_config: Dict[str, Any] = None,
        video_config: Dict[str, Any] = None,
        prompt=None,
        extra_pnginfo=None,
        **kwargs  # Ignore any extra parameters for backwards compatibility
    ) -> Tuple[torch.Tensor, str, str, str]:
        """
        Create a hierarchical comparison grid from images.
        
        Uses row_hierarchy and col_hierarchy from grid_layout to determine structure.
        Uses format_config for visual styling (colors, fonts, borders).
        Both inputs are optional with sensible defaults.
        """
        # Import default format config
        from .grid_format_config import get_default_format_config
        
        # Use provided format_config or fall back to defaults
        if format_config is None:
            format_config = get_default_format_config()
            print(f"[GridCompare] Using default 'Technical Grid' format")
        else:
            print(f"[GridCompare] Using custom format config")
        
        # Extract styling from format_config
        gap_size = format_config.get('gap_size', 4)
        border_color = format_config.get('border_color', '#000000')
        border_width = format_config.get('border_width', 2)
        text_color = format_config.get('cell_text_color', '#1A1A1A')
        font_size = format_config.get('cell_font_size', 18)
        font_name = format_config.get('cell_font_name', 'default')
        header_colors = format_config.get('header_colors', ['#E8E8E8', '#D4D4D4', '#C0C0C0'])
        header_font_size = format_config.get('header_font_size', 32)
        header_text_color = format_config.get('header_text_color', '#1A1A1A')
        header_padding = format_config.get('header_padding', 12)
        
        # Extract hierarchies from grid_layout or detect automatically
        if grid_layout:
            row_hierarchy = grid_layout.get('row_hierarchy', [])
            col_hierarchy = grid_layout.get('col_hierarchy', [])
            print(f"[GridCompare] Using GRID_LAYOUT: rows={row_hierarchy}, cols={col_hierarchy}")
            if grid_layout.get('warnings'):
                for warning in grid_layout['warnings']:
                    print(f"[GridCompare] Layout warning: {warning}")
        else:
            # Fall back to auto-detection with simple XY layout
            print(f"[GridCompare] No GRID_LAYOUT provided, using auto-detection")
            row_hierarchy = []
            col_hierarchy = []
        
        # Extract video options from video_config or use defaults (images only)
        video_output_mode = "images_only"
        video_format = "mp4"
        video_codec = "libx264"
        video_quality = 23
        
        if video_config:
            video_output_mode = video_config.get("video_output_mode", "both")
            video_format = video_config.get("video_format", "mp4")
            video_codec = video_config.get("video_codec", "libx264")
            video_quality = video_config.get("video_quality", 23)
        
        # Parse subtitle_fields string OR use defaults
        # New format: comma-separated field names like "model,vae,sampler,cfg"
        if subtitle_fields and subtitle_fields.strip():
            fields = [f.strip().lower() for f in subtitle_fields.split(",")]
            subtitle_config = {
                'model': 'model' in fields,
                'vae': 'vae' in fields,
                'clip': 'clip' in fields,
                'lora': 'lora' in fields,
                'lora_strength': 'lora_strength' in fields,
                'sampler': 'sampler' in fields,
                'scheduler': 'scheduler' in fields,
                'cfg': 'cfg' in fields,
                'steps': 'steps' in fields,
                'seed': 'seed' in fields,
                'dimensions': 'dimensions' in fields,
                'prompt': 'prompt' in fields,
                'negative_prompt': 'negative_prompt' in fields,
                'show_field_names': subtitle_show_field_names,
            }
        else:
            # Default: show nothing (user can specify fields via subtitle_fields parameter)
            subtitle_config = {
                'model': False,
                'vae': False,
                'clip': False,
                'lora': False,
                'lora_strength': False,
                'sampler': False,
                'scheduler': False,
                'cfg': False,
                'steps': False,
                'seed': False,
                'dimensions': False,
                'prompt': False,
                'negative_prompt': False,
                'show_field_names': subtitle_show_field_names,
            }
        
        # Extract show_positive_prompt and show_negative_prompt from subtitle_config
        # These control whether prompts are displayed in grid headers
        show_positive_prompt = subtitle_config.get('prompt', False)
        show_negative_prompt = subtitle_config.get('negative_prompt', False)
        
        # Get combinations for label generation
        combinations = config.get("combinations", [])
        print(f"[GridCompare] DEBUG: config keys = {list(config.keys()) if config else 'None'}")
        print(f"[GridCompare] DEBUG: combinations from config = {len(combinations)}")
        
        # CRITICAL: Expand combinations with LoRA modes before processing
        # This ensures combinations have proper lora_config, lora_name, lora_strength fields
        chain_lora_configs = config.get('chain_lora_configs', {})
        if chain_lora_configs:
            first_combo = combinations[0] if combinations else {}
            has_lora_data = bool(first_combo.get('lora_config', {}).get('loras', []))
            
            if not has_lora_data:
                print(f"[GridCompare] Expanding {len(combinations)} combinations with chain_lora_configs")
                combinations = expand_combinations_with_lora_modes(combinations, config)
                print(f"[GridCompare] Expanded to {len(combinations)} combinations")
        
        # Detect varying dimensions from expanded combinations
        varying_dims = detect_varying_dimensions(combinations, config)
        print(f"[GridCompare] Detected varying dimensions: {list(varying_dims.keys())}")
        
        # Generate labels from config - respects subtitle_config filter
        label_list = []
        for combo in combinations:
            label = self._generate_cell_label(
                combo, config, varying_dims,
                subtitle_filter=subtitle_config,
                show_field_names=subtitle_config.get('show_field_names', False)
            )
            label_list.append(label)
        
        # Convert ALL images to PIL (needed for video grid)
        all_pil_images = self._tensor_to_pil_list(images)
        
        # Check if images were padded (different original sizes stored in config)
        # If so, crop each image back to its original size
        has_different_sizes = any(
            combo.get("output_width") and combo.get("output_height") 
            for combo in combinations
        )
        
        if has_different_sizes and len(combinations) == len(all_pil_images):
            cropped_images = []
            for i, (pil_img, combo) in enumerate(zip(all_pil_images, combinations)):
                orig_w = combo.get("output_width")
                orig_h = combo.get("output_height")
                if orig_w and orig_h and (orig_w != pil_img.width or orig_h != pil_img.height):
                    # Image was padded - crop to original size (centered)
                    pad_w = pil_img.width
                    pad_h = pil_img.height
                    x_offset = (pad_w - orig_w) // 2
                    y_offset = (pad_h - orig_h) // 2
                    cropped = pil_img.crop((x_offset, y_offset, x_offset + orig_w, y_offset + orig_h))
                    cropped_images.append(cropped)
                else:
                    cropped_images.append(pil_img)
            all_pil_images = cropped_images
        
        # For image grid, extract only first frame per combination if we have multi-frame outputs
        has_frame_counts = any(combo.get("output_frame_count", 1) > 1 for combo in combinations)
        
        if has_frame_counts:
            # Extract first frame from each combination for image grid
            pil_images = []
            img_idx = 0
            for combo in combinations:
                frame_count = combo.get("output_frame_count", 1)
                if img_idx < len(all_pil_images):
                    pil_images.append(all_pil_images[img_idx])  # First frame only
                img_idx += frame_count  # Skip remaining frames
        else:
            pil_images = all_pil_images

        # =========================================================================
        # HIERARCHICAL GRID PATH
        # If row_hierarchy or col_hierarchy are provided from GridPresetFormula,
        # use the new hierarchical grid method directly
        # =========================================================================
        if row_hierarchy or col_hierarchy:
            print(f"[GridCompare] Using HIERARCHICAL grid with rows={row_hierarchy}, cols={col_hierarchy}")
            print(f"[GridCompare] DEBUG: combinations count = {len(combinations)}")
            print(f"[GridCompare] DEBUG: pil_images count = {len(pil_images)}")
            print(f"[GridCompare] DEBUG: grid_layout keys = {list(grid_layout.keys()) if grid_layout else 'None'}")
            if grid_layout:
                print(f"[GridCompare] DEBUG: grid_layout varying_dims = {grid_layout.get('varying_dims', {})}")
            
            # If combinations is empty but we have images, create synthetic combinations
            # This happens when the sampler doesn't store combinations in config
            if not combinations and pil_images:
                print(f"[GridCompare] WARNING: No combinations in config, creating synthetic from grid_layout")
                # Use varying_dims from grid_layout to reconstruct combinations
                if grid_layout and 'varying_dims' in grid_layout:
                    varying_dims_info = grid_layout.get('varying_dims', {})
                    combinations = self._reconstruct_combinations_from_layout(
                        num_images=len(pil_images),
                        row_hierarchy=row_hierarchy,
                        col_hierarchy=col_hierarchy,
                        varying_dims=varying_dims_info,
                    )
                    print(f"[GridCompare] Reconstructed {len(combinations)} combinations")
            
            # Prepare varying_dims info for the hierarchical grid
            varying_dims_info = {}
            if grid_layout and 'varying_dims' in grid_layout:
                varying_dims_info = grid_layout.get('varying_dims', {})
            else:
                # Detect from combinations
                for field in (row_hierarchy + col_hierarchy):
                    values = set()
                    for combo in combinations:
                        val = self._get_combo_field_value(combo, config, field)
                        if val is not None:
                            values.add(val)
                    varying_dims_info[field] = {'values': list(values), 'count': len(values)}
            
            # Create hierarchical grid
            grid_image = self._create_hierarchical_grid(
                images=pil_images,
                combinations=combinations,
                config=config,
                row_hierarchy=row_hierarchy,
                col_hierarchy=col_hierarchy,
                format_config=format_config,
                title=grid_title,
                external_varying_dims=varying_dims_info if varying_dims_info else None,
                subtitle_config=subtitle_config,
            )
            
            # Save the grid
            from datetime import datetime
            output_dir = folder_paths.get_output_directory()
            save_dir = os.path.join(output_dir, save_location) if save_location else output_dir
            os.makedirs(save_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = sanitize_filename(grid_title)
            grid_filename = f"{output_prefix}_{safe_title}_{timestamp}.png"
            grid_path = os.path.join(save_dir, grid_filename)
            
            # Save with metadata
            metadata = PngInfo()
            if prompt and save_metadata:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo and save_metadata:
                for k, v in extra_pnginfo.items():
                    metadata.add_text(k, json.dumps(v) if not isinstance(v, str) else v)
            metadata.add_text("grid_title", grid_title)
            metadata.add_text("row_hierarchy", json.dumps(row_hierarchy))
            metadata.add_text("col_hierarchy", json.dumps(col_hierarchy))
            
            grid_image.save(grid_path, pnginfo=metadata)
            print(f"[GridCompare] Saved hierarchical grid: {grid_path}")
            
            # Save individual images if requested
            if save_individuals and pil_images:
                indiv_dir = os.path.join(save_dir, "individuals")
                os.makedirs(indiv_dir, exist_ok=True)
                for i, (img, label) in enumerate(zip(pil_images, label_list)):
                    safe_label = sanitize_filename(label[:50]) if label else f"image_{i:03d}"
                    indiv_path = os.path.join(indiv_dir, f"{output_prefix}_{i:03d}_{safe_label}.png")
                    indiv_meta = PngInfo()
                    if prompt and save_metadata:
                        indiv_meta.add_text("prompt", json.dumps(prompt))
                    indiv_meta.add_text("label", label)
                    img.save(indiv_path, pnginfo=indiv_meta)
            
            # Generate HTML grid if enabled
            html_path = ""
            if html_grid_output:
                try:
                    from .html_grid_generator import generate_html_grid, save_html_grid
                    
                    html_content = generate_html_grid(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        title=grid_title,
                        use_base64=True,
                        image_format=html_image_format,
                        image_quality=html_image_quality,
                        grid_image=grid_image,
                    )
                    
                    html_filename = f"{output_prefix}_{safe_title}_{timestamp}_gallery.html"
                    html_path = os.path.join(save_dir, html_filename)
                    
                    save_html_grid(html_content, html_path)
                    print(f"[GridCompare] HTML grid saved to: {html_path}")
                except Exception as e:
                    print(f"[GridCompare] Error generating HTML grid: {e}")
                    import traceback
                    traceback.print_exc()
            
            # Convert to tensor and return
            grid_tensor = self._pil_to_tensor(grid_image)
            return (grid_tensor, grid_path, "", html_path)
        
        # =========================================================================
        # LEGACY GRID PATH
        # Fall back to the existing logic for backwards compatibility
        # when no hierarchies are provided
        # =========================================================================
        
        # Set default values for legacy variables that may not be defined
        max_images_per_grid = 100
        grid_split_by = "none"
        preset_mode = "auto"
        nest_axes = []
        row_axis = "auto"
        col_axis = "auto"
        save_prompt_grids_separately = False
        max_grid_pixels = 16000

        # Check if pagination is needed (exceeds max_images_per_grid)
        num_images = len(pil_images)
        
        # Determine split field (from layout analysis or grid_split_by setting)
        split_field = None
        if grid_split_by and grid_split_by != "none":
            split_field = grid_split_by
        elif num_images > max_images_per_grid and preset_mode == "smart":
            # Use backup_split_field from layout analysis if available
            if hasattr(layout, 'backup_split_field') and layout.backup_split_field:
                split_field = layout.backup_split_field
            elif nest_axes:
                split_field = nest_axes[0]  # Split by first nest level
            elif varying_dims:
                # Use first varying dim as fallback
                split_field = list(varying_dims.keys())[0] if varying_dims else None
        
        if num_images > max_images_per_grid:
            print(f"[GridCompare] {num_images} images exceed max_images_per_grid ({max_images_per_grid})")
            if split_field:
                print(f"[GridCompare] Will split by '{split_field}'")
            else:
                print(f"[GridCompare] Consider enabling 'save_prompt_grids_separately' or setting 'grid_split_by'")
        
        # --- GRID SPLITTING: Split into multiple grids if needed ---
        if split_field and num_images > max_images_per_grid:
            # Split images into groups by split_field value
            groups = self._split_by_field(pil_images, label_list, combinations, config, split_field)
            
            if len(groups) > 1:
                print(f"[GridCompare] Splitting into {len(groups)} grids by '{split_field}'")
                
                # Create a grid for each group
                all_grid_images = []
                all_save_paths = []
                
                for group_idx, group in enumerate(groups):
                    group_images = group['images']
                    group_labels = group['labels']
                    group_combos = group['combinations']
                    group_title_suffix = group['group_title']
                    
                    # CASCADE SPLIT: If group still exceeds limit, split again by next nest axis
                    if len(group_images) > max_images_per_grid:
                        # Find next split field from nest_axes (skip the one we already split by)
                        remaining_nest_axes = [ax for ax in nest_axes if ax != split_field and ax != 'none']
                        group_varying = self._detect_varying_dimensions(group_combos, config)
                        available_split_dims = [d for d in group_varying.keys() if d != split_field]
                        
                        next_split = remaining_nest_axes[0] if remaining_nest_axes else (available_split_dims[0] if available_split_dims else None)
                        
                        if next_split:
                            print(f"[GridCompare] CASCADE: Group '{group_title_suffix}' has {len(group_images)} images, splitting further by '{next_split}'")
                            sub_groups = self._split_by_field(group_images, group_labels, group_combos, config, next_split)
                            
                            # Recursively process sub-groups
                            for sub_group in sub_groups:
                                sub_title = f"{group_title_suffix} / {sub_group['group_title']}"
                                sub_group['group_title'] = sub_title
                                groups.append(sub_group)  # Add to groups list for processing
                            continue  # Skip this group, process sub-groups instead
                        else:
                            print(f"[GridCompare] Warning: Group '{group_title_suffix}' has {len(group_images)} images but no more split dimensions available")
                    
                    # Create title with group suffix
                    group_grid_title = f"{grid_title} - {group_title_suffix}" if group_title_suffix else grid_title
                    
                    # Detect varying dims for this group
                    group_varying = self._detect_varying_dimensions(group_combos, config)
                    
                    # Generate labels for this group
                    group_label_list = []
                    for combo in group_combos:
                        label = self._generate_cell_label(
                            combo, config, group_varying,
                            subtitle_filter=subtitle_config,
                            show_field_names=subtitle_config.get('show_field_names', False)
                        )
                        group_label_list.append(label)
                    
                    # Create the grid for this group
                    has_sampling_variations = any(
                        dim in group_varying for dim in ['sampler_name', 'scheduler', 'height', 'width', 
                                                         'lumina_shift', 'qwen_shift', 'wan_shift', 
                                                         'hunyuan_shift', 'flux_guidance', 'cfg', 'steps',
                                                         'seed', 'lora_name', 'lora_strength', 'vae', 'clip']
                    )
                    
                    if has_sampling_variations:
                        num_varying = len(group_varying)
                        has_user_nest = len(nest_axes) > 0
                        
                        if has_user_nest or num_varying > 2:
                            group_grid_image = self._create_nested_xy_grids(
                                images=group_images,
                                labels=group_label_list,
                                combinations=group_combos,
                                config=config,
                                row_axis=row_axis,
                                col_axis=col_axis,
                                nest_axes=nest_axes,
                                varying_dims=group_varying,
                                gap_size=gap_size,
                                border_color=border_color,
                                border_width=border_width,
                                text_color=text_color,
                                font_size=font_size,
                                font_name=font_name,
                                title=group_grid_title,
                                show_positive_prompt=show_positive_prompt,
                                show_negative_prompt=show_negative_prompt,
                                max_grid_pixels=max_grid_pixels,
                            )
                        else:
                            group_grid_image = self._create_xy_grid(
                                images=group_images,
                                labels=group_label_list,
                                combinations=group_combos,
                                config=config,
                                row_axis=row_axis,
                                col_axis=col_axis,
                                varying_dims=group_varying,
                                gap_size=gap_size,
                                border_color=border_color,
                                border_width=border_width,
                                text_color=text_color,
                                font_size=font_size,
                                font_name=font_name,
                                title=group_grid_title,
                                show_positive_prompt=show_positive_prompt,
                                show_negative_prompt=show_negative_prompt,
                            )
                    else:
                        # Simple row grid for this group
                        group_grid_image = self._create_row_grid(
                            images=group_images,
                            labels=group_label_list,
                            gap_size=gap_size,
                            border_color=border_color,
                            border_width=border_width,
                            text_color=text_color,
                            font_size=font_size,
                            font_name=font_name,
                            title=group_grid_title,
                        )
                    
                    all_grid_images.append(group_grid_image)
                    
                    # Save this grid
                    from datetime import datetime
                    output_dir = folder_paths.get_output_directory()
                    save_dir = os.path.join(output_dir, save_location) if save_location else output_dir
                    os.makedirs(save_dir, exist_ok=True)
                    
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_title = sanitize_filename(group_grid_title)
                    grid_filename = f"{output_prefix}_{safe_title}_{group_idx + 1:02d}_{timestamp}.png"
                    grid_path = os.path.join(save_dir, grid_filename)
                    
                    # Save with metadata
                    metadata = PngInfo()
                    if prompt and save_metadata:
                        metadata.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo and save_metadata:
                        for k, v in extra_pnginfo.items():
                            metadata.add_text(k, json.dumps(v) if not isinstance(v, str) else v)
                    metadata.add_text("grid_title", group_grid_title)
                    metadata.add_text("grid_group", str(group_idx + 1))
                    metadata.add_text("split_field", split_field)
                    metadata.add_text("split_value", str(group['split_value']))
                    
                    group_grid_image.save(grid_path, pnginfo=metadata)
                    print(f"[GridCompare] Saved grid {group_idx + 1}/{len(groups)}: {grid_path}")
                    all_save_paths.append(grid_path)
                
                # Stack all grid images as output
                grid_tensors = []
                for grid_img in all_grid_images:
                    tensor = self._pil_to_tensor(grid_img)
                    grid_tensors.append(tensor)
                
                stacked_tensor = torch.cat(grid_tensors, dim=0)
                
                # Generate HTML grid if enabled (includes all images)
                html_path = ""
                if html_grid_output:
                    try:
                        from .html_grid_generator import generate_html_grid, save_html_grid
                        
                        html_content = generate_html_grid(
                            images=pil_images,
                            labels=label_list,
                            combinations=combinations,
                            config=config,
                            title=grid_title,
                            use_base64=True,
                            image_format=html_image_format,
                            image_quality=html_image_quality,
                            grid_image=all_grid_images[0] if all_grid_images else None,
                        )
                        
                        html_save_dir = os.path.join(output_dir, save_location) if save_location else output_dir
                        html_filename = f"{output_prefix}_{sanitize_filename(grid_title)}_{timestamp}_gallery.html"
                        html_path = os.path.join(html_save_dir, html_filename)
                        
                        save_html_grid(html_content, html_path)
                        print(f"[GridCompare] HTML grid saved to: {html_path}")
                    except Exception as e:
                        print(f"[GridCompare] Error generating HTML grid: {e}")
                        import traceback
                        traceback.print_exc()
                
                return (stacked_tensor, ", ".join(all_save_paths), "", html_path)

        # Handle "Save each prompt as separate grid" option
        prompt_variations = config.get("prompt_variations", [])
        
        if save_prompt_grids_separately and len(prompt_variations) > 1 and len(combinations) == len(pil_images):
            result = self._create_separate_prompt_grids(
                pil_images=pil_images,
                label_list=label_list,
                config=config,
                save_location=save_location,
                grid_title=grid_title,
                gap_size=gap_size,
                border_color=border_color,
                border_width=border_width,
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                show_positive_prompt=show_positive_prompt,
                show_negative_prompt=show_negative_prompt,
                save_individuals=save_individuals,
                save_metadata=save_metadata,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            
            # Generate HTML grid even for separate prompt grids if enabled
            html_path = ""
            if html_grid_output:
                try:
                    from .html_grid_generator import generate_html_grid, save_html_grid
                    
                    # Convert the stacked tensor back to PIL for HTML generation
                    stacked_tensor = result[0]
                    grid_pil_images = self._tensor_to_pil_list(stacked_tensor)
                    grid_for_thumbnail = grid_pil_images[0] if grid_pil_images else None
                    
                    html_content = generate_html_grid(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        title=grid_title,
                        use_base64=True,
                        image_format=html_image_format,
                        image_quality=html_image_quality,
                        grid_image=grid_for_thumbnail,
                    )
                    
                    output_dir = folder_paths.get_output_directory()
                    html_save_dir = os.path.join(output_dir, save_location) if save_location else output_dir
                    os.makedirs(html_save_dir, exist_ok=True)
                    
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_title = sanitize_filename(grid_title)
                    html_filename = f"{safe_title}_{timestamp}.html"
                    html_path = os.path.join(html_save_dir, html_filename)
                    
                    save_html_grid(html_content, html_path)
                    print(f"[GridCompare] HTML grid saved to: {html_path}")
                    
                    # Notify tracker
                    try:
                        from .compare_tracker import set_html_grid_available
                        import base64 as b64
                        html_abs = os.path.abspath(html_path)
                        encoded_path = b64.urlsafe_b64encode(html_abs.encode('utf-8')).decode('ascii')
                        view_url = f"/model-compare/view/{encoded_path}"
                        set_html_grid_available(html_path, view_url)
                    except Exception as e:
                        print(f"[GridCompare] Could not notify tracker: {e}")
                except Exception as e:
                    print(f"[GridCompare] Error generating HTML grid: {e}")
                    import traceback
                    traceback.print_exc()
            
            return (result[0], result[1], result[2], html_path)

        # Check if sampling failed (e.g., "No successful samples" returned)
        if len(pil_images) > 0 and len(label_list) == 1 and label_list[0].lower().startswith("no "):
            # Create a simple fallback grid showing error message
            grid_image = self._create_error_grid(
                images=pil_images,
                error_message=label_list[0],
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                title=grid_title,
            )
        else:
            if len(pil_images) != len(label_list):
                # Pad labels if needed
                while len(label_list) < len(pil_images):
                    label_list.append(f"Image {len(label_list)}")

            # varying_dims already detected at start of method
            
            # Check if we have sampling variations (multi-value fields from config chain)
            has_sampling_variations = any(
                dim in varying_dims for dim in ['sampler_name', 'scheduler', 'height', 'width', 
                                                  'lumina_shift', 'qwen_shift', 'wan_shift', 
                                                  'hunyuan_shift', 'flux_guidance', 'cfg', 'steps',
                                                  'seed', 'lora_name', 'lora_strength', 'vae', 'clip']
            )
            
            if has_sampling_variations:
                # Check if we have 3+ varying dimensions and need nested grids
                num_varying = len(varying_dims)
                
                # Determine if user specified nesting or we need auto-nesting for 3+ dimensions
                has_user_nest = len(nest_axes) > 0
                
                # Debug logging for grid path decision
                print(f"[GridCompare] Grid path decision: num_varying={num_varying}, has_user_nest={has_user_nest}, num_images={len(pil_images)}, num_combos={len(combinations)}")
                print(f"[GridCompare] varying_dims={list(varying_dims.keys())}, nest_axes={nest_axes}")
                
                if has_user_nest or num_varying > 2:
                    # Create nested grids - one XY grid per combination of nest axis values
                    grid_image = self._create_nested_xy_grids(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        row_axis=row_axis,
                        col_axis=col_axis,
                        nest_axes=nest_axes,
                        varying_dims=varying_dims,
                        gap_size=gap_size,
                        border_color=border_color,
                        border_width=border_width,
                        text_color=text_color,
                        font_size=font_size,
                        font_name=font_name,
                        title=grid_title,
                        show_positive_prompt=show_positive_prompt,
                        show_negative_prompt=show_negative_prompt,
                        max_grid_pixels=max_grid_pixels,
                    )
                else:
                    # Use smart XY grid with user-specified or auto-detected axes
                    print(f"[GridCompare] Calling _create_xy_grid with row_axis={row_axis}, col_axis={col_axis}")
                    print(f"[GridCompare] varying_dims keys: {list(varying_dims.keys())}")
                    print(f"[GridCompare] num combinations: {len(combinations)}, num images: {len(pil_images)}")
                    # Debug: print first combo structure
                    if combinations:
                        print(f"[GridCompare] First combo keys: {list(combinations[0].keys())}")
                        print(f"[GridCompare] First combo lora_config: {combinations[0].get('lora_config')}")
                        print(f"[GridCompare] First combo prompt_positive: {combinations[0].get('prompt_positive', '')[:50]}...")
                    grid_image = self._create_xy_grid(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        row_axis=row_axis,
                        col_axis=col_axis,
                        varying_dims=varying_dims,
                        gap_size=gap_size,
                        border_color=border_color,
                        border_width=border_width,
                        text_color=text_color,
                        font_size=font_size,
                        font_name=font_name,
                        title=grid_title,
                        show_positive_prompt=show_positive_prompt,
                        show_negative_prompt=show_negative_prompt,
                    )
            else:
                # Organize images by LoRA and strength (legacy mode)
                organized_data = self._organize_images_by_lora(config, pil_images, label_list)
                
                # Check if we should use the Nested Grid System
                # Use nested grid if we have multiple models, VAEs, or CLIPs AND not in grouped mode
                is_grouped = config.get("is_grouped", False)
                is_nested = (
                    len(config.get("model_variations", [])) > 1 or
                    len(config.get("vae_variations", [])) > 1 or
                    len(config.get("clip_variations", [])) > 1
                ) and not is_grouped
                
                if is_grouped:
                    # Grouped mode: simple side-by-side comparison
                    # Each model group (Model + VAE + CLIP) is one column
                    grid_image = self._create_grouped_grid(
                        images=pil_images,
                        labels=label_list,
                        config=config,
                        gap_size=gap_size,
                        border_color=border_color,
                        border_width=border_width,
                        text_color=text_color,
                        font_size=font_size,
                        font_name=font_name,
                        title=grid_title,
                        show_positive_prompt=show_positive_prompt,
                        show_negative_prompt=show_negative_prompt,
                    )
                elif is_nested:
                    grid_image = self._create_nested_grid(
                        images=pil_images,
                        config=config,
                        gap_size=gap_size,
                        border_color=border_color,
                        border_width=border_width,
                        text_color=text_color,
                        font_size=font_size,
                        font_name=font_name,
                        title=grid_title,
                    )
                elif organized_data["num_rows"] == 0 or organized_data["num_cols"] == 0:
                    # Fallback to simple grid if label parsing failed
                    grid_image = self._create_xy_grid(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        row_axis="auto",
                        col_axis="auto",
                        varying_dims=varying_dims,
                        gap_size=gap_size,
                        border_color=border_color,
                        border_width=border_width,
                        text_color=text_color,
                        font_size=font_size,
                        font_name=font_name,
                        title=grid_title,
                        show_positive_prompt=show_positive_prompt,
                        show_negative_prompt=show_negative_prompt,
                    )
                else:
                    grid_image = self._create_organized_grid(
                        organized_data=organized_data,
                        gap_size=gap_size,
                        border_color=border_color,
                        border_width=border_width,
                        text_color=text_color,
                        font_size=font_size,
                        font_name=font_name,
                        title=grid_title,
                    )

        # Add prompt text to the main grid if prompts are enabled and we're NOT in grouped mode
        # (grouped mode already handles prompts internally)
        is_grouped = config.get("is_grouped", False)
        if not is_grouped and (show_positive_prompt or show_negative_prompt):
            # Get prompt info from the first prompt variation
            prompt_info = None
            if prompt_variations:
                prompt_info = prompt_variations[0]
            elif combinations:
                # Fallback: try to get prompt from combinations
                for combo in combinations:
                    if combo.get("prompt_positive") or combo.get("prompt_negative"):
                        prompt_info = {
                            "positive": combo.get("prompt_positive", ""),
                            "negative": combo.get("prompt_negative", "")
                        }
                        break
            
            if prompt_info:
                grid_image = self._add_prompt_text_to_grid(
                    grid_image=grid_image,
                    prompt_info=prompt_info,
                    show_positive=show_positive_prompt,
                    show_negative=show_negative_prompt,
                    text_color=text_color,
                    font_name=font_name,
                    font_size=font_size,
                )
        
        # Handle grid splitting if requested
        all_grid_images = [grid_image]
        grid_labels = [grid_title]
        
        if grid_split_by != "none":
            split_grids = self._split_grids_by_dimension(
                images=pil_images,
                labels=label_list,
                config=config,
                split_by=grid_split_by,
                gap_size=gap_size,
                border_color=border_color,
                border_width=border_width,
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                title=grid_title,
                show_positive_prompt=show_positive_prompt,
                show_negative_prompt=show_negative_prompt,
            )
            if split_grids:
                all_grid_images = [g["image"] for g in split_grids]
                grid_labels = [g["label"] for g in split_grids]

        # Save images with enhanced individual naming
        save_path = self._save_images_enhanced(
            grid_images=all_grid_images,
            grid_labels=grid_labels,
            individual_images=pil_images if save_individuals else [],
            individual_labels=label_list if save_individuals else [],
            combinations=combinations if save_individuals else [],
            save_location=save_location,
            output_prefix=output_prefix,
            save_metadata=save_metadata,
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
        )

        print(f"[GridCompare] Grid saved to: {save_path}")

        # Handle video output if needed
        video_path = ""
        if video_output_mode in ["video_only", "both"]:
            video_path = self._create_video_grid(
                all_pil_images=all_pil_images,
                labels=label_list,
                config=config,
                save_location=save_location,
                grid_title=grid_title,
                video_format=video_format,
                video_codec=video_codec,
                video_quality=video_quality,
                gap_size=gap_size,
                font_size=font_size,
                text_color=text_color,
                border_color=border_color,
                border_width=border_width,
                font_name=font_name,
                show_positive_prompt=show_positive_prompt,
            )

        # Handle HTML grid output if enabled
        html_path = ""
        if html_grid_output:
            try:
                from .html_grid_generator import generate_html_grid, save_html_grid
                
                # Generate HTML content
                # Pass the composed grid image for use as gallery thumbnail
                grid_for_thumbnail = all_grid_images[0] if all_grid_images else None
                html_content = generate_html_grid(
                    images=pil_images,
                    labels=label_list,
                    combinations=combinations,
                    config=config,
                    title=grid_title,
                    use_base64=True,
                    image_format=html_image_format,
                    image_quality=html_image_quality,
                    grid_image=grid_for_thumbnail,
                )
                
                # Determine save path
                output_dir = folder_paths.get_output_directory()
                if save_location:
                    html_save_dir = os.path.join(output_dir, save_location)
                else:
                    html_save_dir = output_dir
                os.makedirs(html_save_dir, exist_ok=True)
                
                # Generate filename with timestamp
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_title = sanitize_filename(grid_title)
                html_filename = f"{safe_title}_{timestamp}.html"
                html_path = os.path.join(html_save_dir, html_filename)
                
                # Save HTML
                save_html_grid(html_content, html_path)
                print(f"[GridCompare] HTML grid saved to: {html_path}")
                
                # Notify tracker that HTML grid is available
                try:
                    from .compare_tracker import set_html_grid_available
                    import urllib.parse
                    import base64
                    
                    # Use our custom /model-compare/view/ endpoint which works for any path
                    # Encode the full path in base64 for safe URL transmission
                    html_abs = os.path.abspath(html_path)
                    encoded_path = base64.urlsafe_b64encode(html_abs.encode('utf-8')).decode('ascii')
                    view_url = f"/model-compare/view/{encoded_path}"
                    
                    set_html_grid_available(html_path, view_url)
                    print(f"[GridCompare] HTML view URL: {view_url}")
                except Exception as e:
                    print(f"[GridCompare] Could not notify tracker: {e}")
                
            except Exception as e:
                print(f"[GridCompare] Error generating HTML grid: {e}")
                import traceback
                traceback.print_exc()

        # Convert PIL back to tensor for output (all grids stacked)
        if len(all_grid_images) > 1:
            # Find max dimensions across all grids
            max_width = max(g.width for g in all_grid_images)
            max_height = max(g.height for g in all_grid_images)
            
            # Pad all grids to the same size (white background)
            padded_grids = []
            for g in all_grid_images:
                if g.width != max_width or g.height != max_height:
                    # Create new image with max dimensions
                    padded = Image.new('RGB', (max_width, max_height), (255, 255, 255))
                    # Paste original centered
                    x_offset = (max_width - g.width) // 2
                    y_offset = (max_height - g.height) // 2
                    padded.paste(g, (x_offset, y_offset))
                    padded_grids.append(padded)
                else:
                    padded_grids.append(g)
            
            output_tensors = [self._pil_to_tensor(g) for g in padded_grids]
            output_tensor = torch.cat(output_tensors, dim=0)
        else:
            output_tensor = self._pil_to_tensor(all_grid_images[0])

        return (output_tensor, save_path, video_path, html_path)

    @staticmethod
    def _tensor_to_pil_list(images: torch.Tensor) -> List[Image.Image]:
        """Convert image tensor to list of PIL images."""
        images_list = []
        
        # Handle different tensor formats
        # Expected shapes:
        # - 4D: [batch, height, width, channels]
        # - 5D video: [batch, frames, height, width, channels]
        
        # If 5D and frames=1, squeeze it down to 4D
        if images.ndim == 5:
            if images.shape[1] == 1:  # Single frame video
                images = images.squeeze(1)  # Remove frame dimension
            else:
                # Multiple frames - take first frame of each batch
                images = images[:, 0, :, :, :]
        
        for i in range(images.shape[0]):
            img = images[i]
            
            # Handle different tensor formats
            if img.dtype == torch.float32 or img.dtype == torch.float16 or img.dtype == torch.bfloat16:
                # Assume range [0, 1]
                img_np = (img.cpu().numpy() * 255).astype(np.uint8)
            else:
                # Direct conversion for uint8 or other types
                img_np = img.cpu().numpy().astype(np.uint8)

            # Handle different shapes
            if img_np.ndim == 3 and img_np.shape[-1] == 4:
                # RGBA
                pil_img = Image.fromarray(img_np, mode='RGBA')
            elif img_np.ndim == 3 and img_np.shape[-1] == 3:
                # RGB
                pil_img = Image.fromarray(img_np, mode='RGB')
            elif img_np.ndim == 2:
                # Grayscale
                pil_img = Image.fromarray(img_np, mode='L')
            else:
                # Try to squeeze and retry
                img_np_squeezed = img_np.squeeze()
                if img_np_squeezed.ndim == 2:
                    pil_img = Image.fromarray(img_np_squeezed, mode='L')
                else:
                    raise ValueError(f"Cannot convert image with shape {img_np.shape} to PIL")

            images_list.append(pil_img)

        return images_list

    @staticmethod
    def _pil_to_tensor(pil_image: Image.Image) -> torch.Tensor:
        """Convert PIL image to tensor."""
        img_np = np.array(pil_image).astype(np.float32) / 255.0
        if img_np.ndim == 2:
            img_np = np.stack([img_np] * 3, axis=-1)
        img_tensor = torch.from_numpy(img_np)[None, :]
        return img_tensor

    @staticmethod
    def _parse_color(color_str: str) -> Tuple[int, int, int]:
        """Parse hex color string to RGB tuple."""
        color_str = color_str.lstrip('#')
        if len(color_str) == 6:
            return tuple(int(color_str[i:i+2], 16) for i in (0, 2, 4))
        else:
            return (0, 0, 0)  # Default to black

    @staticmethod
    def _get_font(font_name: str, font_size: int):
        """Load font from system. Returns None if default should be used."""
        if font_name == "default":
            return None  # Use PIL default font
        
        try:
            # Windows system fonts
            if os.name == 'nt':
                font_path = f"C:\\Windows\\Fonts\\{font_name}"
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, font_size)
            
            # Linux system fonts
            linux_paths = [
                f"/usr/share/fonts/truetype/dejavu/{font_name}",
                f"/usr/share/fonts/truetype/{font_name}",
                f"/usr/share/fonts/{font_name}",
            ]
            for font_path in linux_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, font_size)
            
            # Try direct path
            if os.path.exists(font_name):
                return ImageFont.truetype(font_name, font_size)
            
            # If no font found, use default
            return None
        except Exception as e:
            print(f"[GridCompare] Font loading failed: {e}, using default")
            return None

    def _create_error_grid(
        self,
        images: List[Image.Image],
        error_message: str,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """Create a simple grid showing error message when sampling fails."""
        if not images:
            return Image.new('RGB', (400, 100), color='white')
        
        # Use first image as reference size
        img_width, img_height = images[0].size
        
        # Create simple layout
        gap = 10
        header_height = font_size + 20
        
        grid_width = img_width + gap * 2
        grid_height = header_height + img_height + gap * 2
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        font = self._get_font(font_name, font_size)
        text_rgb = self._parse_color(text_color)
        
        # Draw error message
        msg_x = grid_width // 2
        msg_y = header_height // 2
        draw.text((msg_x, msg_y), error_message, fill=text_rgb, font=font, anchor="mm")
        
        # Draw placeholder image
        if images:
            grid_img.paste(images[0], (gap, header_height + gap))
        
        return grid_img

    def _create_separate_prompt_grids(
        self,
        pil_images: List[Image.Image],
        label_list: List[str],
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        show_positive_prompt: bool,
        show_negative_prompt: bool,
        save_individuals: bool,
        save_metadata: bool,
        prompt,
        extra_pnginfo,
    ) -> Tuple[torch.Tensor, str]:
        """
        Create separate grid images for each prompt variation.
        
        Returns the first grid as tensor and comma-separated paths for all grids.
        """
        prompt_variations = config.get("prompt_variations", [])
        combinations = config.get("combinations", [])
        num_model_groups = config.get("num_model_groups", 1)
        
        # Group images by prompt_index
        # Images are organized: [prompt1_model1, prompt1_model2, ..., prompt2_model1, prompt2_model2, ...]
        images_by_prompt: Dict[int, List[Tuple[Image.Image, str]]] = {}
        
        for i, (img, label) in enumerate(zip(pil_images, label_list)):
            if i < len(combinations):
                prompt_idx = combinations[i].get("prompt_index", 1)
            else:
                # Fallback: calculate from position
                prompt_idx = (i // num_model_groups) + 1
            
            if prompt_idx not in images_by_prompt:
                images_by_prompt[prompt_idx] = []
            images_by_prompt[prompt_idx].append((img, label))
        
        all_paths = []
        all_grid_tensors = []
        
        for prompt_idx in sorted(images_by_prompt.keys()):
            img_label_pairs = images_by_prompt[prompt_idx]
            prompt_images = [pair[0] for pair in img_label_pairs]
            prompt_labels = [pair[1] for pair in img_label_pairs]
            
            # Get the prompt text for this variation
            prompt_info = None
            for pv in prompt_variations:
                if pv.get("index") == prompt_idx:
                    prompt_info = pv
                    break
            
            # Create a modified config for this single prompt
            single_prompt_config = config.copy()
            single_prompt_config["prompt_variations"] = [prompt_info] if prompt_info else []
            single_prompt_config["num_model_groups"] = num_model_groups
            
            # Build title with prompt info
            prompt_title = f"{grid_title} - Prompt {prompt_idx}" if grid_title else f"Prompt {prompt_idx}"
            
            # Create the grid for this prompt using grouped layout
            is_grouped = config.get("is_grouped", False)
            
            if is_grouped:
                grid_image = self._create_grouped_grid(
                    images=prompt_images,
                    labels=prompt_labels,
                    config=single_prompt_config,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=prompt_title,
                    show_positive_prompt=show_positive_prompt,
                    show_negative_prompt=show_negative_prompt,
                )
            else:
                # Use simple grid for non-grouped mode
                grid_image = self._create_simple_grid(
                    images=prompt_images,
                    labels=prompt_labels,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=prompt_title,
                )
                
                # Add prompt text to bottom only for non-grouped mode (grouped mode already includes it)
                if show_positive_prompt or show_negative_prompt:
                    grid_image = self._add_prompt_text_to_grid(
                        grid_image=grid_image,
                        prompt_info=prompt_info,
                        show_positive=show_positive_prompt,
                        show_negative=show_negative_prompt,
                        text_color=text_color,
                        font_name=font_name,
                        font_size=font_size,
                    )
            
            # Save this grid
            save_title = f"{grid_title}_prompt{prompt_idx}" if grid_title else f"grid_prompt{prompt_idx}"
            save_path = self._save_images(
                grid_image=grid_image,
                individual_images=prompt_images if save_individuals else [],
                save_location=save_location,
                title=save_title,
                save_metadata=save_metadata,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            all_paths.append(save_path)
            all_grid_tensors.append(self._pil_to_tensor(grid_image))
            print(f"[GridCompare] Prompt {prompt_idx} grid saved to: {save_path}")
        
        # Return all grid tensors stacked and all paths
        combined_paths = ", ".join(all_paths)
        
        # Stack all grid tensors into a batch
        # Grids may have different sizes due to prompt text, so pad to largest dimensions
        if all_grid_tensors:
            if len(all_grid_tensors) == 1:
                stacked_grids = all_grid_tensors[0]
            else:
                # Find max dimensions across all grids
                max_h = max(t.shape[1] for t in all_grid_tensors)
                max_w = max(t.shape[2] for t in all_grid_tensors)
                
                # Pad each tensor to max dimensions (bottom-right padding with white)
                padded_tensors = []
                for tensor in all_grid_tensors:
                    h, w = tensor.shape[1], tensor.shape[2]
                    if h < max_h or w < max_w:
                        # Create white padded tensor
                        padded = torch.ones((1, max_h, max_w, 3), dtype=tensor.dtype, device=tensor.device)
                        padded[:, :h, :w, :] = tensor
                        padded_tensors.append(padded)
                    else:
                        padded_tensors.append(tensor)
                
                stacked_grids = torch.cat(padded_tensors, dim=0)
        else:
            stacked_grids = torch.zeros((1, 64, 64, 3))
        
        # Generate HTML grid for all separate prompt grids if html_grid_output was enabled
        # We need to get this from the caller - check if it was passed via kwargs or config
        html_path = ""
        
        return (stacked_grids, combined_paths, "", html_path)

    def _add_prompt_text_to_grid(
        self,
        grid_image: Image.Image,
        prompt_info: Dict[str, Any],
        show_positive: bool,
        show_negative: bool,
        text_color: str,
        font_name: str,
        font_size: int,
    ) -> Image.Image:
        """Add prompt text to bottom of grid image, centered and wrapped."""
        if not prompt_info:
            return grid_image
        
        prompt_font = self._get_font(font_name, int(font_size * 0.5))
        text_rgb = self._parse_color(text_color)
        
        # Calculate available width for text (with padding on both sides)
        text_padding = 20
        available_width = grid_image.width - text_padding * 2
        
        # Build wrapped text lines
        lines = []
        if show_positive and prompt_info.get("positive"):
            pos_text = prompt_info["positive"]
            lines.append(("header", "Positive Prompt:"))
            wrapped = self._wrap_text(pos_text, prompt_font, available_width)
            for line in wrapped.split('\n'):
                lines.append(("positive", line))
            lines.append(("spacer", ""))  # Add spacing between positive and negative
        
        if show_negative and prompt_info.get("negative"):
            neg_text = prompt_info["negative"]
            lines.append(("header_neg", "Negative Prompt:"))
            wrapped = self._wrap_text(neg_text, prompt_font, available_width)
            for line in wrapped.split('\n'):
                lines.append(("negative", line))
        
        if not lines:
            return grid_image
        
        # Calculate text height needed
        line_height = int(font_size * 0.6)
        spacer_height = int(font_size * 0.3)
        total_text_height = 0
        for line_type, _ in lines:
            if line_type == "spacer":
                total_text_height += spacer_height
            else:
                total_text_height += line_height
        text_height = total_text_height + text_padding * 2
        
        # Create new image with extra space at bottom
        new_width = grid_image.width
        new_height = grid_image.height + text_height
        new_image = Image.new('RGB', (new_width, new_height), color=(255, 255, 255))
        new_image.paste(grid_image, (0, 0))
        
        # Draw prompt text - centered
        draw = ImageDraw.Draw(new_image)
        y = grid_image.height + text_padding
        center_x = new_width // 2
        
        for line_type, line_text in lines:
            if line_type == "spacer":
                y += spacer_height
                continue
            elif line_type == "header":
                color = (80, 80, 80)  # Gray for headers
            elif line_type == "header_neg":
                color = (150, 50, 50)  # Dark red for negative header
            elif line_type == "negative":
                color = (150, 50, 50)  # Dark red for negative
            else:
                color = text_rgb
            
            # Draw centered text
            draw.text((center_x, y), line_text, fill=color, font=prompt_font, anchor="mt")
            y += line_height
        
        return new_image

    def _create_grouped_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        config: Dict[str, Any],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
    ) -> Image.Image:
        """
        Create a grid for grouped comparisons (Model+VAE+CLIP are grouped together).
        
        Layout:
        - Title at top
        - For each prompt variation:
            - Model labels row (one per column)
            - Images row (one per model group)
            - Prompt text row (spanning all columns) if enabled
        
        Columns = Model Groups (Model 1 vs Model 2 vs ...)
        Sections = Prompt variations (each gets its own row of images + optional prompt label)
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get image dimensions from first image
        img_width, img_height = images[0].size
        
        # Determine grid layout
        num_model_groups = config.get("num_model_groups", 1)
        prompt_variations = config.get("prompt_variations", [])
        num_prompts = len(prompt_variations) if prompt_variations else 1
        
        # Columns = model groups
        num_cols = num_model_groups
        
        # Images are organized: [prompt1_model1, prompt1_model2, ..., prompt2_model1, prompt2_model2, ...]
        # Each prompt variation gets num_cols images
        
        # Get fonts
        title_font = self._get_font(font_name, font_size)
        label_font = self._get_font(font_name, int(font_size * 0.7))
        prompt_font = self._get_font(font_name, int(font_size * 0.5))
        text_rgb = self._parse_color(text_color)
        border_rgb = self._parse_color(border_color)
        
        # Calculate dimensions
        model_label_height = int(font_size * 1.2)
        title_height = font_size + 30 if title else 0
        
        # Calculate cell dimensions first (needed for prompt width calculation)
        cell_width = img_width + gap_size
        
        # Calculate prompt text height (if enabled) - measure actual text height needed
        prompt_text_height = 0
        if show_positive_prompt or show_negative_prompt:
            # We need to calculate actual height based on wrapped text
            # Get prompt text from first prompt variation to measure
            prompt_variations = config.get("prompt_variations", [])
            max_prompt_height = 0
            
            # Calculate available width for text wrapping (same as used in drawing)
            grid_width_temp = cell_width * num_cols + gap_size
            prompt_width = grid_width_temp - gap_size * 2
            
            for pv in prompt_variations:
                pv_height = 0
                if show_positive_prompt and pv.get("positive"):
                    # Header line
                    pv_height += int(font_size * 0.6)
                    # Wrapped text lines
                    wrapped = self._wrap_text(pv.get("positive", ""), prompt_font, prompt_width)
                    pv_height += int(font_size * 0.6) * len(wrapped.split('\n'))
                
                if show_negative_prompt and pv.get("negative"):
                    # Spacer
                    pv_height += int(font_size * 0.3)
                    # Header line
                    pv_height += int(font_size * 0.6)
                    # Wrapped text lines
                    wrapped = self._wrap_text(pv.get("negative", ""), prompt_font, prompt_width)
                    pv_height += int(font_size * 0.6) * len(wrapped.split('\n'))
                
                max_prompt_height = max(max_prompt_height, pv_height)
            
            prompt_text_height = max_prompt_height + gap_size * 2  # Add padding
        
        # Calculate grid dimensions (cell_width already defined above)
        section_height = model_label_height + img_height + gap_size + prompt_text_height
        
        grid_width = cell_width * num_cols + gap_size
        grid_height = title_height + section_height * num_prompts + gap_size
        
        # Create grid image
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        # Draw title
        current_y = 0
        if title:
            title_x = grid_width // 2
            title_y = title_height // 2
            draw.text((title_x, title_y), title, fill=text_rgb, font=title_font, anchor="mm")
            current_y = title_height
        
        # Draw each prompt section
        for prompt_idx in range(num_prompts):
            section_y = current_y + prompt_idx * section_height
            
            # Get prompt text for this section
            prompt_positive = ""
            prompt_negative = ""
            if prompt_variations and prompt_idx < len(prompt_variations):
                prompt_data = prompt_variations[prompt_idx]
                prompt_positive = prompt_data.get("positive", "")
                prompt_negative = prompt_data.get("negative", "")
            
            # Draw model labels and images for this prompt section
            for col in range(num_cols):
                img_idx = prompt_idx * num_cols + col
                if img_idx >= len(images):
                    continue
                
                x = gap_size + col * cell_width
                
                # Get label for this image (model name)
                label = labels[img_idx] if img_idx < len(labels) else f"Model {col + 1}"
                
                # Draw model label
                label_y = section_y + model_label_height // 2
                # Truncate label if too long
                max_label_width = img_width - 10
                display_label = label
                if label_font:
                    try:
                        while label_font.getbbox(display_label)[2] > max_label_width and len(display_label) > 10:
                            display_label = display_label[:-4] + "..."
                    except:
                        pass
                draw.text((x + img_width // 2, label_y), display_label, fill=text_rgb, font=label_font, anchor="mm")
                
                # Draw image
                img_y = section_y + model_label_height
                img = images[img_idx]
                
                # Resize if needed
                if img.size != (img_width, img_height):
                    img = img.resize((img_width, img_height), Image.LANCZOS)
                
                # Draw border
                if border_width > 0:
                    for i in range(border_width):
                        draw.rectangle(
                            [(x - i, img_y - i), (x + img_width + i, img_y + img_height + i)],
                            outline=border_rgb,
                            width=1,
                        )
                
                grid_img.paste(img, (x, img_y))
            
            # Draw prompt text spanning all columns (if enabled)
            if show_positive_prompt or show_negative_prompt:
                prompt_y = section_y + model_label_height + img_height + gap_size // 2
                prompt_x = gap_size
                prompt_width = grid_width - gap_size * 2
                
                if show_positive_prompt and prompt_positive:
                    # Draw header
                    draw.text((grid_width // 2, prompt_y), "Positive Prompt:", fill=(80, 80, 80), font=prompt_font, anchor="mt")
                    prompt_y += int(font_size * 0.6)
                    # Wrap and draw positive prompt
                    wrapped_pos = self._wrap_text(prompt_positive, prompt_font, prompt_width)
                    for line in wrapped_pos.split('\n'):
                        draw.text((grid_width // 2, prompt_y), line, fill=text_rgb, font=prompt_font, anchor="mt")
                        prompt_y += int(font_size * 0.6)
                
                if show_negative_prompt and prompt_negative:
                    prompt_y += int(font_size * 0.3)  # Add spacer
                    # Draw header
                    draw.text((grid_width // 2, prompt_y), "Negative Prompt:", fill=(150, 50, 50), font=prompt_font, anchor="mt")
                    prompt_y += int(font_size * 0.6)
                    # Wrap and draw negative prompt
                    wrapped_neg = self._wrap_text(prompt_negative, prompt_font, prompt_width)
                    for line in wrapped_neg.split('\n'):
                        draw.text((grid_width // 2, prompt_y), line, fill=(150, 50, 50), font=prompt_font, anchor="mt")
                        prompt_y += int(font_size * 0.6)
        
        return grid_img

    def _wrap_text(self, text: str, font, max_width: int) -> str:
        """Wrap text to fit within max_width."""
        if not font:
            return text
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                bbox = font.getbbox(test_line)
                width = bbox[2] - bbox[0]
            except:
                width = len(test_line) * 10
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines) if lines else text

    def _create_simple_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """Create a simple grid when label parsing fails - just rows of images."""
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get image dimensions from first image
        img_width, img_height = images[0].size
        
        # Create a single column grid
        label_height = font_size + 20
        title_height = label_height + gap_size if title else 0
        
        grid_width = img_width + gap_size * 2
        grid_height = title_height + len(images) * (img_height + label_height + gap_size) + gap_size
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        font = self._get_font(font_name, font_size)
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)
        
        current_y = gap_size
        
        # Draw title if provided
        if title:
            title_x = grid_width // 2
            draw.text((title_x, current_y), title, fill=text_rgb, font=font, anchor="mm")
            current_y += title_height
        
        # Draw each image with its label
        for idx, (img, label) in enumerate(zip(images, labels)):
            x = gap_size
            y = current_y
            
            # Draw label
            draw.text((x, y), label, fill=text_rgb, font=font)
            y += label_height
            
            # Draw border if specified
            if border_width > 0:
                for i in range(border_width):
                    draw.rectangle(
                        [(x - i, y - i), (x + img_width + i, y + img_height + i)],
                        outline=border_rgb,
                        width=1,
                    )
            
            # Paste image
            grid_img.paste(img, (x, y))
            current_y = y + img_height + gap_size
        
        return grid_img

    def _create_nested_grid(
        self,
        images: List[Image.Image],
        config: Dict[str, Any],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """
        Create a hierarchical nested grid:
        Cols: Model -> VAE -> Strength
        Rows: CLIP -> LoRA Group
        """
        unique_vals = self._get_unique_values(config)
        data = self._organize_nested_data(images, config, unique_vals)
        
        # --- Calculate Dimensions ---
        
        # 1. Determine cell size (from first image)
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        img_width, img_height = images[0].size
        
        # 2. Determine number of columns per VAE (max variations)
        max_cols_per_vae = 1
        for c_idx in data:
            for g_idx in data[c_idx]:
                for m_idx in data[c_idx][g_idx]:
                    for v_idx in data[c_idx][g_idx][m_idx]:
                        max_cols_per_vae = max(max_cols_per_vae, len(data[c_idx][g_idx][m_idx][v_idx]))
        
        num_models = len(unique_vals["models"])
        num_vaes = len(unique_vals["vaes"])
        
        # Total Grid Columns = Models * VAEs * Max_Strengths
        total_data_cols = num_models * num_vaes * max_cols_per_vae
        
        # 3. Determine Label Widths (Rows)
        label_font = self._get_font(font_name, int(font_size * 0.8))
        
        # CLIP Label Width
        max_clip_width = 0
        for c in unique_vals["clips"]:
            w = len(c["label"]) * 10 # Estimate
            if label_font:
                try: w = label_font.getbbox(c["label"])[2]
                except: pass
            max_clip_width = max(max_clip_width, w)
        clip_label_width = max_clip_width + 40
        
        # LoRA Group Label Width
        max_group_width = 0
        for g in unique_vals["lora_groups"]:
            # Check if we should show this label
            # "The Lora name label on the left should only show the lora's that have variations or have the OR operator"
            # Variations: max_cols_per_vae > 1 (approximation, strictly it's per group)
            # OR operator: len(unique_vals["lora_groups"]) > 1
            show_label = (max_cols_per_vae > 1) or (len(unique_vals["lora_groups"]) > 1)
            if not show_label: continue

            # Wrap text logic estimation
            label_text = g["label"]
            # Simple estimation: assume we wrap at ~20 chars? 
            # Let's just measure the longest word or fixed width
            w = 200 # Minimum width
            if label_font:
                try: w = max(w, label_font.getbbox(label_text)[2])
                except: pass
            # Cap width to avoid huge labels
            w = min(w, 400) 
            max_group_width = max(max_group_width, w)
            
        group_label_width = max_group_width + 40 if max_group_width > 0 else 0
        
        total_label_width = clip_label_width + group_label_width
        
        # 4. Calculate Header Heights
        # "The model header column for each base model should be slightly larger font and bold"
        model_font_size = int(font_size * 1.2)
        model_header_font = self._get_font(font_name, model_font_size)
        header_font = self._get_font(font_name, font_size)
        sub_header_font = self._get_font(font_name, int(font_size * 0.9))
        small_header_font = self._get_font(font_name, int(font_size * 0.7))
        
        model_header_height = model_font_size + 30
        vae_header_height = int(font_size * 0.9) + 20
        
        # "The labels for lora strength should ONLY show for the Lora that has a variation set"
        show_strength_header = max_cols_per_vae > 1
        strength_header_height = (int(font_size * 0.7) + 20) if show_strength_header else 0
        
        total_header_height = model_header_height + vae_header_height + strength_header_height
        
        title_height = (font_size + 30) if title else 0
        
        # 5. Calculate Total Size
        # Rows = CLIPs * LoRA_Groups
        num_rows = len(unique_vals["clips"]) * len(unique_vals["lora_groups"])
        
        # Add extra space for CLIP separators
        clip_separator_height = gap_size * 2
        
        grid_width = total_label_width + total_data_cols * (img_width + gap_size) + gap_size
        grid_height = title_height + total_header_height + num_rows * (img_height + gap_size) + (len(unique_vals["clips"]) - 1) * clip_separator_height + gap_size
        
        # --- Render ---
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)
        
        current_y = gap_size
        
        # Draw Main Title
        if title:
            draw.text((grid_width // 2, current_y), title, fill=text_rgb, font=header_font, anchor="mt")
            current_y += title_height
            
        # --- Draw Headers ---
        
        # Model Headers
        model_width = num_vaes * max_cols_per_vae * (img_width + gap_size)
        for m_i, model_info in enumerate(unique_vals["models"]):
            x_start = total_label_width + gap_size + m_i * model_width
            # Center text in the model block
            center_x = x_start + model_width // 2
            
            # Use custom label
            display_name = model_info["label"]
            
            # Draw Bold (simulate by drawing with offset)
            draw.text((center_x, current_y), display_name, fill=text_rgb, font=model_header_font, anchor="mt")
            draw.text((center_x+1, current_y), display_name, fill=text_rgb, font=model_header_font, anchor="mt")
            
            # Draw separator line (Thick border for models)
            if border_width > 0:
                # Draw line at start of model block (except first one maybe?)
                # "the divide between the first 3 images and 2nd 3 images should have a clear separator"
                line_x = x_start - (gap_size // 2)
                if m_i > 0:
                    draw.line([(line_x, current_y), (line_x, grid_height)], fill=border_rgb, width=border_width * 2)
                
        current_y += model_header_height
        
        # VAE Headers
        vae_width = max_cols_per_vae * (img_width + gap_size)
        for m_i in range(num_models):
            for v_i, vae_info in enumerate(unique_vals["vaes"]):
                # Calculate absolute index
                abs_v_i = m_i * num_vaes + v_i
                x_start = total_label_width + gap_size + abs_v_i * vae_width
                center_x = x_start + vae_width // 2
                
                display_name = vae_info["label"]
                
                draw.text((center_x, current_y), display_name, fill=text_rgb, font=sub_header_font, anchor="mt")
                
                # Draw separator line (Normal width for VAEs)
                if border_width > 0:
                    line_x = x_start - (gap_size // 2)
                    # Don't draw over the model separator
                    if v_i > 0: 
                        draw.line([(line_x, current_y), (line_x, grid_height)], fill=border_rgb, width=1)

        current_y += vae_header_height
        
        # Strength Headers
        if show_strength_header:
            for m_i in range(num_models):
                for v_i in range(num_vaes):
                    for s_i in range(max_cols_per_vae):
                        # Find a label for this column index
                        label = f"Var {s_i+1}"
                        # Try to find a real label from data
                        found = False
                        for c_idx in data:
                            for g_idx in data[c_idx]:
                                if m_i in data[c_idx][g_idx] and v_idx in data[c_idx][g_idx][m_idx]:
                                    items = data[c_idx][g_idx][m_idx][v_idx]
                                    if s_i < len(items):
                                        label = items[s_i]["label"]
                                        found = True
                                        break
                            if found: break
                        
                        abs_col_i = (m_i * num_vaes * max_cols_per_vae) + (v_i * max_cols_per_vae) + s_i
                        x_start = total_label_width + gap_size + abs_col_i * (img_width + gap_size)
                        center_x = x_start + img_width // 2
                        
                        draw.text((center_x, current_y), label, fill=text_rgb, font=small_header_font, anchor="mt")

            current_y += strength_header_height
        
        # --- Draw Rows and Images ---
        
        def draw_multiline_text(draw, text, box, font, fill, anchor="lm"):
            """Helper to draw multiline text centered vertically in box"""
            x, y, w, h = box
            lines = []
            words = text.split()
            current_line = []
            
            # Simple word wrap
            for word in words:
                test_line = ' '.join(current_line + [word])
                if font.getbbox(test_line)[2] <= w:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word) # Word too long, force split
                        current_line = []
            if current_line:
                lines.append(' '.join(current_line))
            
            # Calculate total height
            line_height = font.getbbox("Ay")[3] + 4
            total_text_height = len(lines) * line_height
            
            start_y = y + (h - total_text_height) // 2
            
            for i, line in enumerate(lines):
                draw.text((x, start_y + i * line_height), line, fill=fill, font=font)

        for c_i, clip_info in enumerate(unique_vals["clips"]):
            # Draw CLIP Label Area
            clip_y_start = current_y
            clip_height = len(unique_vals["lora_groups"]) * (img_height + gap_size)
            
            # Draw CLIP Label (Vertical centered in its block)
            # "clearer definition between the clip rows"
            # Draw a background or distinct separator
            if c_i > 0:
                # Draw separator above this CLIP block
                sep_y = clip_y_start - (clip_separator_height // 2)
                draw.line([(0, sep_y), (grid_width, sep_y)], fill=border_rgb, width=border_width * 2)
            
            draw.text((gap_size, clip_y_start + clip_height // 2), clip_info["label"], fill=text_rgb, font=label_font, anchor="lm")
            
            # Separator between CLIP label and LoRA labels
            if border_width > 0:
                 draw.line([(clip_label_width, clip_y_start), (clip_label_width, clip_y_start + clip_height)], fill=border_rgb, width=border_width)
            
            for g_i, group_info in enumerate(unique_vals["lora_groups"]):
                row_y = current_y
                
                # Draw LoRA Group Label
                # Only if we decided to show it
                if group_label_width > 0:
                    # "multiline might be tidier"
                    label_box = (gap_size + clip_label_width + 10, row_y, group_label_width - 20, img_height)
                    draw_multiline_text(draw, group_info["label"], label_box, label_font, text_rgb)
                
                # Draw Images
                for m_i in range(num_models):
                    for v_i in range(num_vaes):
                        # Retrieve images for this cell
                        cell_images = []
                        if c_i in data and g_i in data[c_i]:
                            if m_i in data[c_i][g_i] and v_i in data[c_i][g_i][m_i]:
                                cell_images = data[c_i][g_i][m_i][v_i]
                        
                        for s_i in range(max_cols_per_vae):
                            abs_col_i = (m_i * num_vaes * max_cols_per_vae) + (v_i * max_cols_per_vae) + s_i
                            x = total_label_width + gap_size + abs_col_i * (img_width + gap_size)
                            
                            if s_i < len(cell_images):
                                # Draw Image
                                img = cell_images[s_i]["image"]
                                grid_img.paste(img, (x, row_y))
                                
                                # Border
                                if border_width > 0:
                                    for b in range(border_width):
                                        draw.rectangle(
                                            [(x - b, row_y - b), (x + img_width + b, row_y + img_height + b)],
                                            outline=border_rgb,
                                            width=1,
                                        )
                            else:
                                # Empty cell placeholder?
                                pass
                
                current_y += img_height + gap_size
            
            # Add gap after CLIP block
            current_y += clip_separator_height
                
        return grid_img

    def _create_organized_grid(
        self,
        organized_data: Dict[str, Any],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """
        Create a grid image organized by LoRA and strength.
        Rows represent different LoRAs, columns represent different strengths.
        Strength values shown as column headers above, LoRA names as row labels on left.
        """
        rows = organized_data.get("rows", [])
        column_headers = organized_data.get("column_headers", [])
        
        if not rows or not column_headers:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get first image to determine cell dimensions
        first_image = rows[0]["images"][0]["image"] if rows[0]["images"] else None
        if not first_image:
            return Image.new('RGB', (100, 100), color='white')
        
        img_width, img_height = first_image.size
        
        # Calculate layout dimensions
        label_height = font_size + 20
        label_font = self._get_font(font_name, int(font_size * 0.8))
        
        # Calculate label_width based on longest LoRA name
        max_label_width = 100  # Minimum width
        for row in rows:
            lora_name = row["lora_name"]
            # Estimate text width
            if label_font:
                try:
                    # Get bounding box of text
                    bbox = label_font.getbbox(lora_name)
                    text_width = bbox[2] - bbox[0]
                except:
                    text_width = len(lora_name) * 10
            else:
                # Default font estimate: ~10 pixels per character
                text_width = len(lora_name) * 10
            max_label_width = max(max_label_width, text_width + 40)  # Add padding
        
        label_width = max_label_width
        header_height = label_height + gap_size  # Height for strength headers
        title_height = label_height + gap_size if title else 0
        
        num_rows = len(rows)
        num_cols = len(column_headers)
        
        grid_width = label_width + gap_size + num_cols * (img_width + gap_size) + gap_size
        grid_height = title_height + header_height + num_rows * (img_height + gap_size) + gap_size
        
        # Create grid image
        grid_color = self._parse_color("#FFFFFF")
        grid_img = Image.new('RGB', (grid_width, grid_height), color=grid_color)
        draw = ImageDraw.Draw(grid_img)
        font = self._get_font(font_name, font_size)
        header_font = self._get_font(font_name, int(font_size * 0.9))
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)
        
        # Draw title
        current_y = gap_size
        if title:
            title_x = label_width + (num_cols * (img_width + gap_size)) // 2
            draw.text((title_x, current_y), title, fill=text_rgb, font=font, anchor="mm")
            current_y += title_height
        
        # Draw column headers (strength values)
        header_y = current_y
        for col_idx, strength in enumerate(column_headers):
            x = label_width + gap_size + col_idx * (img_width + gap_size) + img_width // 2
            header_text = f"LoRA Strength\n{strength:.2f}"
            draw.text((x, header_y), header_text, fill=text_rgb, font=header_font, anchor="mm")
        
        current_y += header_height
        
        # Draw rows with LoRA labels and images
        for row_idx, row_data in enumerate(rows):
            lora_name = row_data["lora_name"]
            images_data = row_data["images"]
            
            # Draw LoRA name on left
            lora_y = current_y + img_height // 2
            draw.text((gap_size + label_width // 2, lora_y), lora_name, fill=text_rgb, font=label_font, anchor="mm")
            
            # Draw images for this row
            for col_idx, img_data in enumerate(images_data):
                pil_img = img_data["image"]
                
                x = label_width + gap_size + col_idx * (img_width + gap_size)
                y = current_y
                
                # Draw border
                if border_width > 0:
                    for i in range(border_width):
                        draw.rectangle(
                            [(x - i, y - i), (x + img_width + i, y + img_height + i)],
                            outline=border_rgb,
                            width=1,
                        )
                
                # Paste image
                grid_img.paste(pil_img, (x, y))
            
            current_y += img_height + gap_size
        
        return grid_img

    def _split_grids_by_dimension(
        self,
        images: List[Image.Image],
        labels: List[str],
        config: Dict[str, Any],
        split_by: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str,
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Split images into multiple grids based on a grouping dimension.
        
        Args:
            split_by: One of "model", "sampler", "scheduler", "chain", "prompt_positive", "prompt_negative", "auto"
        
        Returns:
            List of {"image": PIL.Image, "label": str} for each split grid
        """
        combinations = config.get("combinations", [])
        
        if not combinations or not images:
            return []
        
        # Determine grouping key based on split_by
        def get_group_key(combo: Dict, idx: int) -> str:
            if split_by == "model":
                model = combo.get("model", "")
                # Clean up model name
                if model.endswith(".safetensors"):
                    model = model[:-12]
                return model
            elif split_by == "sampler":
                override = combo.get("_sampling_override", {})
                return override.get("sampler_name", combo.get("sampler_name", "default"))
            elif split_by == "scheduler":
                override = combo.get("_sampling_override", {})
                return override.get("scheduler", combo.get("scheduler", "default"))
            elif split_by == "chain":
                return str(combo.get("chain_index", 0))
            elif split_by == "prompt_positive":
                # Group by positive prompt - use prompt_index or truncated prompt
                prompt = combo.get("prompt_positive", "")
                prompt_idx = combo.get("prompt_index", 0)
                # Use prompt index if available, else truncate prompt for key
                if prompt_idx:
                    return f"Prompt {prompt_idx}"
                return prompt[:50] if prompt else "default"
            elif split_by == "prompt_negative":
                # Group by negative prompt
                prompt = combo.get("prompt_negative", "")
                return prompt[:50] if prompt else "(no negative)"
            elif split_by == "auto":
                # Auto-detect: use first dimension with > 1 unique values
                # Priority: model > sampler > scheduler > chain
                override = combo.get("_sampling_override", {})
                # Use underscore instead of pipe to be filename-safe
                return f"{combo.get('model', '')}_{override.get('sampler_name', '')}_{override.get('scheduler', '')}"
            else:
                return "default"
        
        # Group images by key
        groups: Dict[str, List[Tuple[int, Image.Image, str, Dict]]] = {}
        for idx, (combo, img) in enumerate(zip(combinations, images)):
            if idx >= len(labels):
                label = f"Image {idx}"
            else:
                label = labels[idx]
            
            key = get_group_key(combo, idx)
            if key not in groups:
                groups[key] = []
            groups[key].append((idx, img, label, combo))
        
        # If only one group, don't split
        if len(groups) <= 1:
            return []
        
        # Create a grid for each group
        result = []
        for group_key, group_items in groups.items():
            group_images = [item[1] for item in group_items]
            group_labels = [item[2] for item in group_items]
            group_combos = [item[3] for item in group_items]
            
            # Create title for this sub-grid
            sub_title = f"{title} - {split_by.title()}: {group_key}"
            
            # Use XY grid for proper layout within each split group
            sub_grid = self._create_xy_grid(
                images=group_images,
                labels=group_labels,
                combinations=group_combos,
                config=config,
                row_axis="auto",
                col_axis="auto",
                gap_size=gap_size,
                border_color=border_color,
                border_width=border_width,
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                title=sub_title,
                show_positive_prompt=False,  # We'll add prompt text manually for prompt splits
                show_negative_prompt=False,
            )
            
            # If splitting by prompt, add the actual prompt text below the grid
            if split_by in ("prompt_positive", "prompt_negative") and group_combos:
                # Get the actual prompt text from the first combo in this group
                prompt_text = ""
                if split_by == "prompt_positive":
                    prompt_text = group_combos[0].get("prompt_positive", "")
                else:
                    prompt_text = group_combos[0].get("prompt_negative", "")
                
                if prompt_text:
                    # Add the prompt text to the grid image
                    prompt_info = {"positive": prompt_text} if split_by == "prompt_positive" else {"negative": prompt_text}
                    sub_grid = self._add_prompt_text_to_grid(
                        grid_image=sub_grid,
                        prompt_info=prompt_info,
                        show_positive=(split_by == "prompt_positive"),
                        show_negative=(split_by == "prompt_negative"),
                        text_color=text_color,
                        font_name=font_name,
                        font_size=font_size,
                    )
            elif show_positive_prompt or show_negative_prompt:
                # For non-prompt splits, show prompts if requested
                if group_combos:
                    prompt_info = {
                        "positive": group_combos[0].get("prompt_positive", ""),
                        "negative": group_combos[0].get("prompt_negative", "")
                    }
                    if prompt_info["positive"] or prompt_info["negative"]:
                        sub_grid = self._add_prompt_text_to_grid(
                            grid_image=sub_grid,
                            prompt_info=prompt_info,
                            show_positive=show_positive_prompt,
                            show_negative=show_negative_prompt,
                            text_color=text_color,
                            font_name=font_name,
                            font_size=font_size,
                        )
            
            result.append({
                "image": sub_grid,
                "label": sanitize_filename(f"{title}_{split_by}_{group_key}"),
            })
        
        return result

    def _save_images_enhanced(
        self,
        grid_images: List[Image.Image],
        grid_labels: List[str],
        individual_images: List[Image.Image],
        individual_labels: List[str],
        combinations: List[Dict[str, Any]],
        save_location: str,
        output_prefix: str,
        save_metadata: bool = False,
        prompt=None,
        extra_pnginfo=None,
    ) -> str:
        """
        Save grids and individual images with enhanced structured naming.
        
        Individual images are saved as:
        {output_prefix}_{idx}_{model}_{sampler}_{sched}_{cfg}_{steps}.png
        
        Also saves a metadata JSON file for easy programmatic access.
        """
        # Create metadata if requested
        metadata = None
        if save_metadata and not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for key in extra_pnginfo:
                    metadata.add_text(key, json.dumps(extra_pnginfo[key]))
        
        # Create save directory
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Save all grid images
        saved_paths = []
        for grid_img, grid_label in zip(grid_images, grid_labels):
            # Sanitize the label for use in filename
            safe_label = sanitize_filename(grid_label)
            # Find next available counter
            counter = 0
            while True:
                grid_path = os.path.join(save_dir, f"{safe_label}_{counter}.png")
                if not os.path.exists(grid_path):
                    break
                counter += 1
            
            grid_img.save(grid_path, pnginfo=metadata, compress_level=4)
            saved_paths.append(grid_path)
            print(f"[GridCompare] Saved grid: {grid_path}")
        
        # Save individual images with structured naming
        if individual_images:
            # Create subfolder for individuals
            individuals_dir = os.path.join(save_dir, "individuals")
            os.makedirs(individuals_dir, exist_ok=True)
            
            # Metadata list for JSON
            images_metadata = []
            
            for idx, img in enumerate(individual_images):
                # Build structured filename from combination data
                combo = combinations[idx] if idx < len(combinations) else {}
                label = individual_labels[idx] if idx < len(individual_labels) else f"img_{idx}"
                
                # Extract components for filename
                model = combo.get("model", "unknown")
                if model.endswith(".safetensors"):
                    model = model[:-12]
                # Sanitize model name for filename
                model = "".join(c if c.isalnum() or c in "._-" else "_" for c in model)[:30]
                
                # Get sampling override values if present
                override = combo.get("_sampling_override", {})
                sampler = override.get("sampler_name", combo.get("sampler_name", "default"))[:15]
                scheduler = override.get("scheduler", combo.get("scheduler", "normal"))[:15]
                cfg = override.get("cfg", combo.get("cfg", 7.0))
                steps = override.get("steps", combo.get("steps", 20))
                
                # Build structured filename
                structured_name = f"{output_prefix}_{idx:04d}_{model}_{sampler}_{scheduler}_cfg{cfg}_steps{steps}"
                
                # Find unique filename
                img_counter = 0
                while True:
                    if img_counter == 0:
                        img_path = os.path.join(individuals_dir, f"{structured_name}.png")
                    else:
                        img_path = os.path.join(individuals_dir, f"{structured_name}_{img_counter}.png")
                    if not os.path.exists(img_path):
                        break
                    img_counter += 1
                
                # Save image
                img.save(img_path, pnginfo=metadata, compress_level=4)
                
                # Collect metadata
                images_metadata.append({
                    "index": idx,
                    "filename": os.path.basename(img_path),
                    "path": img_path,
                    "label": label,
                    "model": combo.get("model", ""),
                    "sampler": sampler,
                    "scheduler": scheduler,
                    "cfg": cfg,
                    "steps": steps,
                    "width": img.width,
                    "height": img.height,
                    "variation_label": combo.get("_variation_label", ""),
                    "lora_names": combo.get("lora_names", []),
                    "lora_strengths": combo.get("lora_strengths", []),
                })
            
            # Save metadata JSON
            json_path = os.path.join(individuals_dir, f"{output_prefix}_metadata.json")
            try:
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump({
                        "prefix": output_prefix,
                        "total_images": len(individual_images),
                        "images": images_metadata,
                    }, f, indent=2, ensure_ascii=False)
                print(f"[GridCompare] Saved metadata: {json_path}")
            except Exception as e:
                print(f"[GridCompare] Failed to save metadata JSON: {e}")
        
        return saved_paths[0] if saved_paths else save_dir

    @staticmethod
    def _save_images(
        grid_image: Image.Image,
        individual_images: List[Image.Image],
        save_location: str,
        title: str,
        save_metadata: bool = False,
        prompt=None,
        extra_pnginfo=None,
    ) -> str:
        """Save grid and optionally individual images.
        
        Saves files like ComfyUI standard nodes:
        - Grid: output/{save_location}/{title}_0.png, {title}_1.png, etc.
        - Individuals: output/{save_location}/{title}_image_{idx}_{counter}.png
        """
        
        # Create metadata if requested
        metadata = None
        if save_metadata and not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for key in extra_pnginfo:
                    metadata.add_text(key, json.dumps(extra_pnginfo[key]))
        
        # Create save directory
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Find next available counter for grid file (following ComfyUI pattern)
        counter = 0
        while True:
            grid_path = os.path.join(save_dir, f"{title}_{counter}.png")
            if not os.path.exists(grid_path):
                break
            counter += 1
        
        # Save grid image with metadata
        grid_image.save(grid_path, pnginfo=metadata, compress_level=4)
        print(f"[GridCompare] Saved grid: {grid_path}")
        
        # Save individual images if requested
        if individual_images:
            for idx, img in enumerate(individual_images):
                img_counter = 0
                while True:
                    img_path = os.path.join(save_dir, f"{title}_image_{idx}_{img_counter}.png")
                    if not os.path.exists(img_path):
                        break
                    img_counter += 1
                
                img.save(img_path, pnginfo=metadata, compress_level=4)
            
        return save_dir

    def _create_video_grid(
        self,
        all_pil_images: List[Image.Image],
        labels: List[str],
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        video_format: str,
        video_codec: str,
        video_quality: int,
        gap_size: int,
        font_size: int,
        text_color: str = "#000000",
        border_color: str = "#000000",
        border_width: int = 2,
        font_name: str = "default",
        show_positive_prompt: bool = False,
    ) -> str:
        """
        Create a video grid from multi-frame outputs.
        
        For video models, each model variation may output multiple frames.
        This method arranges them into a video grid where each cell shows
        the animated output of that model.
        
        Args:
            all_pil_images: List of all PIL images (all frames from all combinations)
        
        Returns:
            Path to the saved video file, or empty string if failed.
        """
        try:
            from .video_utils import create_video_grid, is_video_output, get_ffmpeg_path
        except ImportError:
            print("[GridCompare] video_utils not available, skipping video grid")
            return ""
        
        if get_ffmpeg_path() is None:
            print("[GridCompare] FFmpeg not found, skipping video grid")
            return ""
        
        combinations = config.get("combinations", [])
        model_variations = config.get("model_variations", [])
        
        if not combinations:
            return ""
        
        # Collect video frames per combination using output_frame_count
        video_frames_list = []
        video_labels = []
        fps_list = []
        
        img_idx = 0
        for combo_idx, combo in enumerate(combinations):
            frame_count = combo.get("output_frame_count", 1)
            combo_frames = []
            
            for _ in range(frame_count):
                if img_idx < len(all_pil_images):
                    combo_frames.append(all_pil_images[img_idx])
                    img_idx += 1
            
            if combo_frames:
                video_frames_list.append(combo_frames)
                
                # Get label
                if combo_idx < len(labels):
                    video_labels.append(labels[combo_idx])
                else:
                    video_labels.append(f"Model {combo_idx + 1}")
                
                # Get FPS from model variation
                model_idx = combo.get("model_index", 0)
                if model_idx < len(model_variations):
                    fps = model_variations[model_idx].get("fps", 24)
                else:
                    fps = 24
                fps_list.append(fps)
        
        if not video_frames_list:
            return ""
        
        # Check if we actually have video (multiple frames)
        has_video = any(len(frames) > 1 for frames in video_frames_list)
        if not has_video:
            return ""
        
        # Determine grid layout
        num_videos = len(video_frames_list)
        grid_cols = min(num_videos, config.get("num_model_groups", 2))
        
        # Get cell size from first frame
        if video_frames_list and video_frames_list[0]:
            first_frame = video_frames_list[0][0]
            cell_size = (first_frame.width, first_frame.height)
        else:
            cell_size = (512, 512)
        
        # Create output path
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Find next counter
        counter = 0
        while True:
            video_path = os.path.join(save_dir, f"{grid_title}_video_{counter}.{video_format}")
            if not os.path.exists(video_path):
                break
            counter += 1
        
        # Remove extension for create_video_grid (it adds it)
        video_path_base = video_path.rsplit('.', 1)[0]
        
        # Get positive prompt for display
        positive_prompt = ""
        if show_positive_prompt:
            prompt_variations = config.get("prompt_variations", [])
            if prompt_variations:
                positive_prompt = prompt_variations[0].get("positive", "")
        
        # Create video grid with styling matching image grid
        success = create_video_grid(
            video_frames_list=video_frames_list,
            labels=video_labels,
            output_path=video_path_base,
            fps_list=fps_list,
            grid_cols=grid_cols,
            cell_size=cell_size,
            padding=gap_size,
            label_height=font_size + 20,
            format=video_format,
            codec=video_codec,
            quality=video_quality,
            font_size=font_size,
            # New styling parameters to match image grid
            text_color=text_color,
            border_color=border_color,
            border_width=border_width,
            font_name=font_name,
            grid_title=grid_title,
            positive_prompt=positive_prompt,
        )
        
        if success:
            print(f"[GridCompare] Video grid saved to: {video_path}")
            return video_path
        else:
            print("[GridCompare] Failed to create video grid")
            return ""

    @classmethod
    def IS_CHANGED(cls, images, config, save_location, grid_title, **kwargs):
        """
        Compute a hash to determine if re-execution is needed.
        """
        import hashlib
        
        # Hash key inputs - add defensive checks for None
        combo_count = len(config.get("combinations", [])) if config else 0
        img_shape = str(images.shape) if hasattr(images, 'shape') else "unknown"
        
        hash_input = f"{combo_count}|{img_shape}|{save_location}|{grid_title}"
        
        # Add relevant kwargs
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if isinstance(val, (str, int, float, bool)):
                hash_input += f"|{key}:{val}"
        
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node mappings
NODE_CLASS_MAPPINGS = {
    "GridCompare": GridCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GridCompare": "Ⓜ️ Model Compare - Grid",
}
