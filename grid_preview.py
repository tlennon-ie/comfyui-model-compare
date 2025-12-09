"""
Grid Preview Node

Generates a preview of the grid layout without actually sampling images.
Shows numbered placeholder images with real labels from the configuration,
allowing users to see exactly how their grid will look before running.
"""

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Any, Tuple, Optional
import json
import itertools
import colorsys

# Import shared grid utilities for consistent behavior with GridCompare
from .grid_utils import (
    expand_combinations_with_lora_modes,
    detect_varying_dimensions,
    get_combo_field_value,
    clean_lora_name,
    clean_model_name,
    wrap_text,
    format_prompt_for_header,
    parse_lora_groups,
)


class GridPreview:
    """
    Preview grid layout without running sampling.
    Shows numbered placeholder images with real configuration labels.
    
    This allows users to verify:
    - Which field is assigned to rows vs columns
    - How nesting/grouping will organize the grid
    - The exact labels that will appear
    - Total number of combinations
    """
    
    CATEGORY = "Model Compare/Preview"
    
    @classmethod
    def INPUT_TYPES(cls):
        axis_options = ["auto", "model", "vae", "clip", "lora_name", "lora_strength", 
                       "sampler_name", "scheduler", "cfg", "steps", "seed", 
                       "width", "height", "prompt_positive", "prompt_negative",
                       "lumina_shift", "qwen_shift", "wan_shift", "hunyuan_shift", "flux_guidance"]
        nest_options = ["none"] + axis_options[1:]
        
        return {
            "required": {
                "config": ("MODEL_COMPARE_CONFIG",),
                "placeholder_width": ("INT", {
                    "default": 150,
                    "min": 80,
                    "max": 600,
                    "step": 10,
                    "tooltip": "Width of each placeholder image in pixels"
                }),
                "placeholder_height": ("INT", {
                    "default": 150,
                    "min": 80,
                    "max": 600,
                    "step": 10,
                    "tooltip": "Height of each placeholder image in pixels"
                }),
                "row_axis": (axis_options, {
                    "default": "auto",
                    "tooltip": "Field to use for rows (Y-axis)"
                }),
                "col_axis": (axis_options, {
                    "default": "auto",
                    "tooltip": "Field to use for columns (X-axis)"
                }),
                "nest_axis_1": (nest_options, {
                    "default": "none",
                    "tooltip": "First nesting level (creates separate sub-grids)"
                }),
                "nest_axis_2": (nest_options, {
                    "default": "none",
                    "tooltip": "Second nesting level"
                }),
                "gap_size": ("INT", {
                    "default": 8,
                    "min": 2,
                    "max": 50,
                    "tooltip": "Gap between images in pixels"
                }),
                "max_images_shown": ("INT", {
                    "default": 100,
                    "min": 10,
                    "max": 500,
                    "tooltip": "Maximum placeholder images to render (for performance)"
                }),
            },
            "optional": {
                "grid_layout": ("GRID_LAYOUT", {
                    "tooltip": "Optional layout from Grid Preset Formula node"
                }),
            },
        }
    
    RETURN_TYPES = ("IMAGE", "STRING", "INT", "STRING")
    RETURN_NAMES = ("preview_grid", "layout_info", "total_combinations", "field_summary")
    FUNCTION = "preview"
    OUTPUT_NODE = True
    
    def _expand_lora_variations(self, combinations: List[Dict], config: Dict) -> List[Dict]:
        """
        Expand combinations with LoRA strength variations from chain_lora_configs.
        Uses shared utility from grid_utils for consistent behavior with GridCompare.
        """
        return expand_combinations_with_lora_modes(combinations, config)

    def _expand_combinations_from_config(self, config: Dict) -> List[Dict]:
        """
        Expand combinations from config if combinations array is empty or incomplete.
        This mimics what the sampler does during actual execution.
        """
        combinations = config.get('combinations', [])
        
        # Check if we have pre-existing combinations
        if combinations:
            # Check if they already have LoRA data or if we need to expand
            first_combo = combinations[0] if combinations else {}
            has_lora_data = bool(first_combo.get('lora_config', {}).get('loras', []))
            chain_lora_configs = config.get('chain_lora_configs', {})
            
            if not has_lora_data and chain_lora_configs:
                # Pre-existing combinations without LoRA data - expand with chain_lora_configs
                print(f"[GridPreview] Expanding {len(combinations)} base combinations with chain_lora_configs")
                expanded = expand_combinations_with_lora_modes(combinations, config)
                print(f"[GridPreview] Expanded to {len(expanded)} combinations after LoRA expansion")
                return expanded
            else:
                print(f"[GridPreview] Using {len(combinations)} pre-existing combinations from config")
                # Check lora_strength structure in first few combos
                for i, combo in enumerate(combinations[:3]):
                    lora_cfg = combo.get('lora_config', {})
                    lora_strengths = lora_cfg.get('lora_strengths', [])
                    direct_strength = combo.get('lora_strength')
                    print(f"  Combo {i}: lora_strengths={lora_strengths}, direct lora_strength={direct_strength}")
                return combinations
        
        # Build combinations from config components
        model_variations = config.get('model_variations', [])
        prompt_variations = config.get('prompt_variations', [])
        lora_configs = config.get('lora_config', [])
        sampling_params = config.get('sampling_params', [])
        
        if not model_variations:
            model_variations = [{'name': 'Default Model', 'display_name': 'Default Model'}]
        
        if not prompt_variations:
            prompt_variations = [{'positive': '', 'negative': ''}]
        
        # Expand LoRA strength combinations using shared utility logic
        lora_strength_combos = [{}]  # Start with empty (no LoRA)
        if lora_configs:
            # Use parse_lora_groups from grid_utils for consistent group handling
            groups = parse_lora_groups(lora_configs)
            
            lora_strength_combos = []
            for group in groups:
                strength_combos = group.get_strength_combinations()
                for strength_tuple in strength_combos:
                    lora_names = []
                    lora_strengths = []
                    
                    for lora, strength in zip(group.loras, strength_tuple):
                        name = clean_lora_name(lora)
                        if not lora.get('ignore_in_grid', False):
                            lora_names.append(name)
                            lora_strengths.append(strength)
                    
                    if lora_names:
                        lora_strength_combos.append({
                            'lora_names': lora_names,
                            'lora_strengths': lora_strengths,
                            'display': ' + '.join(f"{n}:{s}" for n, s in zip(lora_names, lora_strengths)),
                            'group_label': group.label,
                        })
        
        # Build all combinations
        expanded = []
        combo_idx = 0
        
        for model_idx, model in enumerate(model_variations):
            model_name = clean_model_name(model.get('display_name', model.get('name', f'Model {model_idx}')))
            
            for prompt_idx, prompt in enumerate(prompt_variations):
                prompt_text = prompt.get('positive', f'Prompt {prompt_idx + 1}')
                
                for lora_combo in lora_strength_combos:
                    combo = {
                        'model_index': model_idx,
                        'model': model_name,
                        'prompt_index': prompt_idx,
                        'prompt_positive': prompt_text,  # Full text, not truncated
                        'prompt_negative': prompt.get('negative', ''),
                        '_combo_idx': combo_idx,
                    }
                    
                    if lora_combo:
                        combo['lora_config'] = {
                            'loras': [
                                {'name': n, 'strength': s} 
                                for n, s in zip(lora_combo['lora_names'], lora_combo['lora_strengths'])
                            ],
                            'lora_names': lora_combo['lora_names'],
                            'lora_strengths': lora_combo['lora_strengths'],
                            'display': lora_combo['display'],
                            'group_label': lora_combo.get('group_label', ''),
                        }
                        # Also set top-level for easier access
                        combo['lora_name'] = lora_combo.get('group_label', ' + '.join(lora_combo['lora_names']))
                        combo['lora_strength'] = lora_combo['lora_strengths'][0] if len(lora_combo['lora_strengths']) == 1 else tuple(lora_combo['lora_strengths'])
                        combo['lora_group_label'] = lora_combo.get('group_label', '')
                    
                    # Add sampling params from first entry if available
                    if sampling_params:
                        sp = sampling_params[0]
                        combo['sampler_name'] = sp.get('sampler_name', ['euler'])[0] if isinstance(sp.get('sampler_name'), list) else sp.get('sampler_name', 'euler')
                        combo['scheduler'] = sp.get('scheduler', ['normal'])[0] if isinstance(sp.get('scheduler'), list) else sp.get('scheduler', 'normal')
                        combo['steps'] = sp.get('steps', [20])[0] if isinstance(sp.get('steps'), list) else sp.get('steps', 20)
                        combo['cfg'] = sp.get('cfg', [1])[0] if isinstance(sp.get('cfg'), list) else sp.get('cfg', 1)
                    
                    expanded.append(combo)
                    combo_idx += 1
        
        return expanded
    
    def _get_combo_field_value(self, combo: Dict, config: Dict, field: str) -> Any:
        """
        Extract field value from a combination.
        Uses shared utility from grid_utils for consistent behavior with GridCompare.
        """
        return get_combo_field_value(combo, config, field)
    
    def _detect_varying_dimensions(self, combinations: List[Dict], config: Dict) -> Dict[str, List[Any]]:
        """
        Detect which fields have multiple unique values.
        Uses shared utility from grid_utils for consistent behavior with GridCompare.
        """
        return detect_varying_dimensions(combinations, config)
    
    def _format_value(self, val: Any, max_len: int = 20) -> str:
        """Format a value for display."""
        if val is None:
            return "N/A"
        if isinstance(val, float):
            return f"{val:.2f}".rstrip('0').rstrip('.')
        if isinstance(val, tuple):
            # Format tuples compactly for LoRA strengths like (0,1,0)
            return '(' + ','.join(str(int(v)) if isinstance(v, (int, float)) and v == int(v) else str(v) for v in val) + ')'
        s = str(val)
        if len(s) > max_len:
            return s[:max_len-3] + "..."
        return s
    
    def _create_placeholder(self, index: int, width: int, height: int,
                            combo: Dict, config: Dict, 
                            row_field: str, col_field: str,
                            nest_fields: List[str] = None) -> Image.Image:
        """Create a placeholder image with number and field values."""
        # Background color based on model index for visual grouping
        model_idx = combo.get('model_index', 0)
        # Light pastel background - different hue per model
        base_hue = (model_idx * 0.15) % 1.0
        r, g, b = colorsys.hsv_to_rgb(base_hue, 0.12, 0.97)
        bg_color = (int(r * 255), int(g * 255), int(b * 255))
        
        img = Image.new('RGB', (width, height), color=bg_color)
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([(0, 0), (width-1, height-1)], outline=(150, 150, 150), width=2)
        
        # Try to get fonts
        try:
            large_font = ImageFont.truetype("arial.ttf", min(32, height // 4))
            medium_font = ImageFont.truetype("arial.ttf", min(12, height // 12))
            small_font = ImageFont.truetype("arial.ttf", min(10, height // 14))
        except:
            large_font = ImageFont.load_default()
            medium_font = ImageFont.load_default()
            small_font = ImageFont.load_default()
        
        # Draw the combination number prominently
        num_text = str(index + 1)
        draw.text((width // 2, height // 4), num_text, fill=(50, 50, 50), 
                  font=large_font, anchor="mm")
        
        # Draw key field values
        info_lines = []
        
        # Model name (shortened)
        model_name = combo.get('model', self._get_combo_field_value(combo, config, 'model'))
        if model_name:
            info_lines.append(f"M: {self._format_value(model_name, 12)}")
        
        # LoRA info
        lora_config = combo.get('lora_config', {})
        if lora_config:
            strengths = lora_config.get('lora_strengths', [])
            if strengths:
                strength_str = ','.join(f"{s}" for s in strengths)
                info_lines.append(f"L: {strength_str}")
        
        # Row/Col indicators for other fields
        if row_field and row_field not in ['none', 'auto', 'model', 'lora_strength']:
            row_val = self._get_combo_field_value(combo, config, row_field)
            if row_val is not None:
                info_lines.append(f"R: {self._format_value(row_val, 10)}")
        
        if col_field and col_field not in ['none', 'auto', 'model', 'lora_strength']:
            col_val = self._get_combo_field_value(combo, config, col_field)
            if col_val is not None:
                info_lines.append(f"C: {self._format_value(col_val, 10)}")
        
        # Prompt index if varying
        prompt_idx = combo.get('prompt_index')
        if prompt_idx is not None:
            info_lines.append(f"P{prompt_idx + 1}")
        
        # Draw info lines
        y_offset = height // 2
        line_height = min(13, height // 10)
        for line in info_lines[:4]:  # Max 4 lines
            draw.text((width // 2, y_offset), line, fill=(70, 70, 70),
                      font=small_font, anchor="mm")
            y_offset += line_height
        
        return img
    
    def _create_nested_preview(
        self,
        combinations: List[Dict],
        config: Dict,
        varying: Dict[str, List],
        row_axis: str,
        col_axis: str,
        nest_axes: List[str],
        placeholder_width: int,
        placeholder_height: int,
        gap_size: int,
    ) -> Image.Image:
        """Create a nested grid preview with proper hierarchy."""
        
        # Get values for each axis
        row_values = varying.get(row_axis, [None]) if row_axis not in ['auto', 'none'] else [None]
        col_values = varying.get(col_axis, [None]) if col_axis not in ['auto', 'none'] else [None]
        
        if not row_values or row_values == [None]:
            row_values = [None]
        if not col_values or col_values == [None]:
            col_values = [None]
        
        # Handle nesting
        active_nest_axes = [n for n in nest_axes if n and n != 'none' and n in varying]
        
        if not active_nest_axes:
            # Simple grid - no nesting
            return self._create_simple_grid(
                combinations, config, varying,
                row_axis, col_axis, row_values, col_values,
                placeholder_width, placeholder_height, gap_size
            )
        
        # Nested grid
        nest_axis = active_nest_axes[0]
        nest_values = varying.get(nest_axis, [None])
        remaining_nest = active_nest_axes[1:] if len(active_nest_axes) > 1 else []
        
        # Create sub-grids for each nest value
        sub_grids = []
        sub_grid_height = 0
        sub_grid_width = 0
        
        for nest_val in nest_values:
            # Filter combinations for this nest value
            filtered = [
                c for c in combinations 
                if self._get_combo_field_value(c, config, nest_axis) == nest_val
            ]
            
            if not filtered:
                continue
            
            if remaining_nest:
                sub_grid = self._create_nested_preview(
                    filtered, config, varying,
                    row_axis, col_axis, remaining_nest,
                    placeholder_width, placeholder_height, gap_size
                )
            else:
                sub_grid = self._create_simple_grid(
                    filtered, config, varying,
                    row_axis, col_axis, row_values, col_values,
                    placeholder_width, placeholder_height, gap_size
                )
            
            sub_grids.append((nest_val, sub_grid))
            sub_grid_height = max(sub_grid_height, sub_grid.height)
            sub_grid_width = max(sub_grid_width, sub_grid.width)
        
        if not sub_grids:
            # Fallback
            return self._create_simple_grid(
                combinations, config, varying,
                row_axis, col_axis, row_values, col_values,
                placeholder_width, placeholder_height, gap_size
            )
        
        # Arrange sub-grids horizontally
        header_height = 30
        nest_gap = gap_size * 2
        
        total_width = len(sub_grids) * (sub_grid_width + nest_gap) + nest_gap
        total_height = header_height + sub_grid_height + nest_gap
        
        # Create canvas
        canvas = Image.new('RGB', (total_width, total_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(canvas)
        
        try:
            header_font = ImageFont.truetype("arial.ttf", 14)
        except:
            header_font = ImageFont.load_default()
        
        # Place sub-grids with headers
        x_offset = nest_gap
        for nest_val, sub_grid in sub_grids:
            # Header
            header_text = f"{nest_axis}: {self._format_value(nest_val, 20)}"
            draw.text((x_offset + sub_grid_width // 2, header_height // 2),
                      header_text, fill=(40, 40, 40), font=header_font, anchor="mm")
            
            # Draw separator line
            draw.line([(x_offset, header_height - 3), (x_offset + sub_grid_width, header_height - 3)],
                      fill=(180, 180, 180), width=2)
            
            # Paste sub-grid
            canvas.paste(sub_grid, (x_offset, header_height + gap_size))
            
            x_offset += sub_grid_width + nest_gap
        
        return canvas
    
    def _create_simple_grid(
        self,
        combinations: List[Dict],
        config: Dict,
        varying: Dict[str, List],
        row_axis: str,
        col_axis: str,
        row_values: List,
        col_values: List,
        placeholder_width: int,
        placeholder_height: int,
        gap_size: int,
    ) -> Image.Image:
        """Create a simple 2D grid."""
        
        # Build grid mapping: (row_val, col_val) -> combo
        grid_map = {}
        for combo in combinations:
            row_val = self._get_combo_field_value(combo, config, row_axis) if row_axis not in ['auto', 'none'] else None
            col_val = self._get_combo_field_value(combo, config, col_axis) if col_axis not in ['auto', 'none'] else None
            
            key = (row_val, col_val)
            if key not in grid_map:
                grid_map[key] = []
            grid_map[key].append(combo)
        
        # Calculate dimensions
        num_rows = len(row_values) if row_values[0] is not None else 1
        num_cols = len(col_values) if col_values[0] is not None else 1
        
        # If no axes specified, arrange in a line
        if num_rows == 1 and num_cols == 1:
            num_cols = min(len(combinations), 8)
            num_rows = (len(combinations) + num_cols - 1) // num_cols
        
        # Label dimensions
        row_label_width = 70 if row_axis not in ['auto', 'none'] and row_values[0] is not None else 0
        col_label_height = 25 if col_axis not in ['auto', 'none'] and col_values[0] is not None else 0
        
        # Grid size
        grid_width = row_label_width + gap_size + num_cols * (placeholder_width + gap_size)
        grid_height = col_label_height + gap_size + num_rows * (placeholder_height + gap_size)
        
        # Create canvas
        canvas = Image.new('RGB', (grid_width, grid_height), color=(250, 250, 250))
        draw = ImageDraw.Draw(canvas)
        
        try:
            label_font = ImageFont.truetype("arial.ttf", 11)
        except:
            label_font = ImageFont.load_default()
        
        # Draw column headers
        if col_axis not in ['auto', 'none'] and col_values[0] is not None:
            for c_idx, col_val in enumerate(col_values):
                x = row_label_width + gap_size + c_idx * (placeholder_width + gap_size) + placeholder_width // 2
                draw.text((x, col_label_height // 2), self._format_value(col_val, 15),
                          fill=(50, 50, 50), font=label_font, anchor="mm")
        
        # Draw row labels and cells
        combo_linear_idx = 0
        for r_idx, row_val in enumerate(row_values if row_values[0] is not None else [None]):
            y = col_label_height + gap_size + r_idx * (placeholder_height + gap_size)
            
            # Row label
            if row_axis not in ['auto', 'none'] and row_val is not None:
                draw.text((row_label_width // 2, y + placeholder_height // 2),
                          self._format_value(row_val, 10), fill=(50, 50, 50),
                          font=label_font, anchor="mm")
            
            for c_idx, col_val in enumerate(col_values if col_values[0] is not None else [None]):
                x = row_label_width + gap_size + c_idx * (placeholder_width + gap_size)
                
                key = (row_val, col_val)
                cell_combos = grid_map.get(key, [])
                
                if cell_combos:
                    combo = cell_combos[0]
                    idx = combo.get('_combo_idx', combo_linear_idx)
                    
                    placeholder = self._create_placeholder(
                        idx, placeholder_width, placeholder_height,
                        combo, config, row_axis, col_axis, []
                    )
                    canvas.paste(placeholder, (x, y))
                    
                    # Show collision indicator (red badge with count)
                    if len(cell_combos) > 1:
                        badge_w, badge_h = 22, 16
                        draw.rectangle(
                            [(x + placeholder_width - badge_w - 2, y + 2), 
                             (x + placeholder_width - 2, y + badge_h + 2)],
                            fill=(255, 180, 180), outline=(200, 100, 100)
                        )
                        draw.text((x + placeholder_width - badge_w // 2 - 2, y + badge_h // 2 + 2),
                                  f"+{len(cell_combos)-1}", fill=(150, 0, 0),
                                  font=label_font, anchor="mm")
                else:
                    # Empty cell
                    draw.rectangle([(x, y), (x + placeholder_width, y + placeholder_height)],
                                   fill=(235, 235, 235), outline=(210, 210, 210))
                
                combo_linear_idx += 1
        
        return canvas
    
    def preview(
        self,
        config: Dict[str, Any],
        placeholder_width: int,
        placeholder_height: int,
        row_axis: str,
        col_axis: str,
        nest_axis_1: str,
        nest_axis_2: str,
        gap_size: int,
        max_images_shown: int,
        grid_layout: Dict[str, Any] = None,
    ) -> Tuple[torch.Tensor, str, int, str]:
        """Generate preview grid with placeholder images."""
        
        # Expand combinations from config (handles empty combinations array)
        combinations = self._expand_combinations_from_config(config)
        
        if not combinations:
            # Return empty result
            empty_img = Image.new('RGB', (400, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(empty_img)
            draw.text((200, 50), "No combinations found in config", fill=(128, 128, 128), anchor="mm")
            tensor = torch.from_numpy(np.array(empty_img).astype(np.float32) / 255.0).unsqueeze(0)
            return (tensor, json.dumps({"error": "No combinations"}), 0, "No combinations to preview")
        
        total_combinations = len(combinations)
        
        # Limit for performance
        if len(combinations) > max_images_shown:
            combinations = combinations[:max_images_shown]
            truncated = True
        else:
            truncated = False
        
        # Use grid_layout if provided (from GridPresetFormula)
        if grid_layout:
            row_axis = grid_layout.get('row_axis', row_axis)
            col_axis = grid_layout.get('col_axis', col_axis)
            nest_axes_from_layout = grid_layout.get('nest_axes', [])
            if nest_axes_from_layout:
                nest_axis_1 = nest_axes_from_layout[0] if len(nest_axes_from_layout) > 0 else nest_axis_1
                nest_axis_2 = nest_axes_from_layout[1] if len(nest_axes_from_layout) > 1 else nest_axis_2
        
        # Detect varying dimensions
        varying = self._detect_varying_dimensions(combinations, config)
        
        # Auto-detect axes with improved rules
        actual_row = row_axis
        actual_col = col_axis
        
        if row_axis == "auto" and col_axis == "auto":
            # Priority for columns: lora_strength (shows progression), then others
            # Priority for rows: model, lora_name (grouping), then others
            
            # LoRA strength should be columns (shows strength progression 0→1)
            if 'lora_strength' in varying:
                actual_col = 'lora_strength'
            
            # Model should be rows (groups similar images together)
            if 'model' in varying:
                actual_row = 'model'
            # If no model variation, try lora_name for rows
            elif 'lora_name' in varying and actual_col != 'lora_name':
                actual_row = 'lora_name'
            
            # If we still need a column axis, use remaining dimensions
            if actual_col == 'auto':
                col_priority = ['sampler_name', 'scheduler', 'cfg', 'steps']
                for p in col_priority:
                    if p in varying and p != actual_row:
                        actual_col = p
                        break
            
            # If we still need a row axis, use remaining dimensions
            if actual_row == 'auto':
                row_priority = ['sampler_name', 'scheduler', 'cfg', 'steps']
                for p in row_priority:
                    if p in varying and p != actual_col:
                        actual_row = p
                        break
            
            # Prompt should be nesting (not row/col) when we have other dimensions
            # Only use prompt for row/col if nothing else available
            if actual_row == 'auto' and 'prompt_positive' in varying:
                actual_row = 'prompt_positive'
            if actual_col == 'auto' and 'prompt_positive' in varying and actual_row != 'prompt_positive':
                actual_col = 'prompt_positive'
        
        # Fill remaining auto axes from priority list
        priority = ['model', 'lora_strength', 'sampler_name', 'scheduler', 'cfg', 'steps', 'prompt_positive']
        
        if actual_row == "auto":
            for p in priority:
                if p in varying and p != actual_col:
                    actual_row = p
                    break
        
        if actual_col == "auto":
            for p in priority:
                if p in varying and p != actual_row:
                    actual_col = p
                    break
        
        # Auto-add nesting for unassigned varying dimensions
        if not nest_axis_1 or nest_axis_1 == 'none':
            # Find unassigned dimensions that could benefit from nesting
            assigned = {actual_row, actual_col}
            unassigned = [d for d in varying.keys() if d not in assigned and d not in ['auto', 'none', None]]
            
            # Prompt is best for nesting (creates separate grids per prompt)
            if 'prompt_positive' in unassigned:
                nest_axis_1 = 'prompt_positive'
            elif unassigned:
                nest_axis_1 = unassigned[0]
        
        # Build nest axes list
        nest_axes = []
        if nest_axis_1 and nest_axis_1 != 'none':
            nest_axes.append(nest_axis_1)
        if nest_axis_2 and nest_axis_2 != 'none':
            nest_axes.append(nest_axis_2)
        
        # Debug output for troubleshooting
        print(f"[GridPreview] Varying dimensions: {list(varying.keys())}")
        print(f"[GridPreview] Dimension counts: {{{', '.join(f'{k}: {len(v)}' for k, v in varying.items())}}}")
        print(f"[GridPreview] Axes: row={actual_row}, col={actual_col}, nest={nest_axes}")
        print(f"[GridPreview] Total combinations: {total_combinations}")
        
        # Create the preview grid
        grid_img = self._create_nested_preview(
            combinations, config, varying,
            actual_row, actual_col, nest_axes,
            placeholder_width, placeholder_height, gap_size
        )
        
        # Build layout info JSON
        layout_info = {
            "row_axis": actual_row if actual_row != "auto" else "(none)",
            "col_axis": actual_col if actual_col != "auto" else "(none)", 
            "nest_axes": nest_axes,
            "varying_dimensions": list(varying.keys()),
            "dimension_values": {k: [str(v) for v in vals[:5]] for k, vals in varying.items()},
            "total_combinations": total_combinations,
            "shown_combinations": len(combinations),
            "truncated": truncated,
        }
        
        # Build field summary (human readable)
        lines = []
        lines.append(f"{'='*50}")
        lines.append(f"GRID PREVIEW: {total_combinations} combinations")
        lines.append(f"{'='*50}")
        lines.append(f"")
        lines.append(f"AXES:")
        lines.append(f"  Rows: {actual_row if actual_row != 'auto' else '(auto)'}")
        if actual_row in varying:
            lines.append(f"    -> {len(varying[actual_row])} values: {', '.join(str(v)[:15] for v in varying[actual_row][:5])}")
        lines.append(f"  Cols: {actual_col if actual_col != 'auto' else '(auto)'}")
        if actual_col in varying:
            lines.append(f"    -> {len(varying[actual_col])} values: {', '.join(str(v)[:15] for v in varying[actual_col][:8])}")
        
        if nest_axes:
            lines.append(f"  Nest: {' -> '.join(nest_axes)}")
            for na in nest_axes:
                if na in varying:
                    lines.append(f"    {na}: {len(varying[na])} values")
        
        lines.append(f"")
        lines.append(f"VARYING DIMENSIONS ({len(varying)}):")
        for field, values in varying.items():
            lines.append(f"  {field}: {len(values)} values")
        
        # Check for unassigned dimensions
        assigned = {actual_row, actual_col} | set(nest_axes)
        unassigned = [d for d in varying.keys() if d not in assigned and d not in ['auto', 'none', None]]
        if unassigned:
            lines.append(f"")
            lines.append(f"⚠️ WARNING: Unassigned dimensions (may cause collisions):")
            for d in unassigned:
                lines.append(f"  - {d} ({len(varying[d])} values)")
        
        if truncated:
            lines.append(f"")
            lines.append(f"📝 NOTE: Showing {len(combinations)} of {total_combinations} (limited)")
        
        field_summary = "\n".join(lines)
        
        # Convert to tensor
        tensor = torch.from_numpy(np.array(grid_img).astype(np.float32) / 255.0).unsqueeze(0)
        
        return (tensor, json.dumps(layout_info, indent=2), total_combinations, field_summary)


# Node registration  
NODE_CLASS_MAPPINGS = {
    "GridPreview": GridPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GridPreview": "Ⓜ️ Model Compare - Grid Preview",
}
