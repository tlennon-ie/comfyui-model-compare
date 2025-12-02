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
import folder_paths
import json
import comfy.cli_args
args = comfy.cli_args.args


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
    Create a comparison grid from sampled images.
    Arranges images based on model combinations and adds labels.
    """

    @classmethod
    def INPUT_TYPES(cls):
        # Get available fonts from system
        fonts = ["default"]
        font_dir = "C:\\Windows\\Fonts" if os.name == 'nt' else "/usr/share/fonts"
        if os.path.exists(font_dir):
            try:
                fonts.extend([f for f in os.listdir(font_dir) if f.endswith('.ttf')])
            except:
                pass

        return {
            "required": {
                "images": ("IMAGE",),
                "config": ("MODEL_COMPARE_CONFIG",),
                "labels": ("STRING",),
                "save_location": ("STRING", {
                    "default": "model-compare/ComfyUI",
                    "multiline": False,
                    "tooltip": "Output folder path for saving grid",
                }),
                "grid_title": ("STRING", {
                    "default": "Model Comparison Grid",
                    "multiline": False,
                    "tooltip": "Name for the saved grid file",
                }),
                "gap_size": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Space between images in pixels",
                }),
                "border_color": ("STRING", {
                    "default": "#000000",
                    "multiline": False,
                    "tooltip": "Hex color for image borders",
                }),
                "border_width": ("INT", {
                    "default": 2,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "tooltip": "Border width in pixels",
                }),
                "text_color": ("STRING", {
                    "default": "#000000",
                    "multiline": False,
                    "tooltip": "Hex color for text labels",
                }),
                "font_size": ("INT", {
                    "default": 40,
                    "min": 8,
                    "max": 200,
                    "step": 2,
                    "tooltip": "Label text size in points",
                }),
                "font_name": (fonts, {
                    "default": "default",
                    "tooltip": "Font for text labels",
                }),
                "show_positive_prompt": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Show positive prompt text below each prompt section",
                }),
                "show_negative_prompt": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Show negative prompt text below each prompt section",
                }),
                "save_prompt_grids_separately": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Save each prompt variation as a separate grid file (useful for many prompts)",
                }),
                "save_individuals": ("BOOLEAN", {
                    "default": True,
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
                # Grid split options for multi-value variations
                "grid_split_by": (["none", "model", "sampler", "scheduler", "chain", "prompt_positive", "prompt_negative", "auto"], {
                    "default": "none",
                    "tooltip": "Split into multiple grids by grouping dimension (useful for many variations)"
                }),
                "output_prefix": ("STRING", {
                    "default": "compare",
                    "multiline": False,
                    "tooltip": "Prefix for individual image filenames (structured naming)"
                }),
                # Smart grid layout controls
                "row_axis": (["auto", "sampler", "scheduler", "height", "width", "lumina_shift", "qwen_shift", "wan_shift", "wan22_shift", "hunyuan_shift", "flux_guidance", "cfg", "steps", "model", "seed", "lora_name", "lora_strength", "vae", "clip", "prompt_positive", "prompt_negative"], {
                    "default": "auto",
                    "tooltip": "Which variation dimension to use for rows (Y-axis)"
                }),
                "col_axis": (["auto", "sampler", "scheduler", "height", "width", "lumina_shift", "qwen_shift", "wan_shift", "wan22_shift", "hunyuan_shift", "flux_guidance", "cfg", "steps", "model", "seed", "lora_name", "lora_strength", "vae", "clip", "prompt_positive", "prompt_negative"], {
                    "default": "auto",
                    "tooltip": "Which variation dimension to use for columns (X-axis)"
                }),
                # Third axis for nested grids
                "nest_axis": (["none", "auto", "sampler", "scheduler", "height", "width", "lumina_shift", "qwen_shift", "wan_shift", "wan22_shift", "hunyuan_shift", "flux_guidance", "cfg", "steps", "model", "seed", "lora_name", "lora_strength", "vae", "clip", "prompt_positive", "prompt_negative"], {
                    "default": "none",
                    "tooltip": "Third dimension for nested grids (creates separate grids per value)"
                }),
                # HTML Grid output options
                "html_grid_output": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Generate an interactive HTML grid with filters, lightbox, and metadata"
                }),
                "html_image_format": (["JPEG", "PNG"], {
                    "default": "JPEG",
                    "tooltip": "Image format for HTML grid (JPEG = smaller file, PNG = lossless)"
                }),
                "html_image_quality": ("INT", {
                    "default": 85,
                    "min": 50,
                    "max": 100,
                    "step": 5,
                    "tooltip": "JPEG quality for HTML grid images (higher = larger file)"
                }),
            },
            "optional": {
                "video_config": ("VIDEO_GRID_CONFIG", {
                    "tooltip": "Optional video configuration from 'Model Compare - Video Grid Config' node"
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
    
    def _detect_varying_dimensions(self, combinations: List[Dict]) -> Dict[str, List[Any]]:
        """
        Analyze combinations to find which dimensions have multiple unique values.
        
        Returns dict of dimension_name -> list of unique values (sorted)
        """
        if not combinations:
            return {}
        
        # Dimensions to check (from sampling override and combo fields)
        check_fields = [
            'sampler_name', 'scheduler', 'steps', 'cfg', 'denoise',
            'width', 'height', 'lumina_shift', 'qwen_shift', 'wan_shift',
            'wan22_shift', 'hunyuan_shift', 'flux_guidance', 'model',
            'seed', 'lora_name', 'lora_strength', 'vae', 'clip',
            'lora_names', 'lora_strengths',  # Also check list versions
            'prompt_positive', 'prompt_negative'  # Prompt variations
        ]
        
        # Collect all values per field
        field_values = {f: set() for f in check_fields}
        
        for combo in combinations:
            # Check _sampling_override first (for expanded variations)
            override = combo.get('_sampling_override', {})
            
            for field in check_fields:
                # First try override, then combo itself
                value = override.get(field, combo.get(field))
                if value is not None:
                    # Normalize to hashable
                    if isinstance(value, (list, tuple)):
                        value = tuple(value)
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
        
        return varying
    
    def _get_combo_value(self, combo: Dict, field: str) -> Any:
        """Get a field value from combo, checking override first."""
        override = combo.get('_sampling_override', {})
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
    ) -> Image.Image:
        """
        Create a smart XY grid with user-specified or auto-detected axes.
        
        Args:
            row_axis: Field to use for rows (y-axis), or "auto" to detect
            col_axis: Field to use for columns (x-axis), or "auto" to detect
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Detect varying dimensions
        varying = self._detect_varying_dimensions(combinations)
        
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
        
        if row_axis == "auto":
            # Pick first available varying dimension for rows
            for p in priority:
                if p in varying and p != actual_col_axis:
                    actual_row_axis = p
                    break
            if actual_row_axis == "auto":
                actual_row_axis = list(varying.keys())[0] if varying else None
        
        if col_axis == "auto":
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
        row_values = varying.get(actual_row_axis, [None])
        col_values = varying.get(actual_col_axis, [None])
        
        # If we only have one axis, make it columns
        if actual_row_axis and not actual_col_axis:
            actual_col_axis = actual_row_axis
            col_values = row_values
            actual_row_axis = None
            row_values = [None]
        
        # Create mapping from (row_val, col_val) -> image index
        grid_map = {}
        for idx, combo in enumerate(combinations):
            if idx >= len(images):
                break
            
            row_val = self._get_combo_value(combo, actual_row_axis) if actual_row_axis else None
            col_val = self._get_combo_value(combo, actual_col_axis) if actual_col_axis else None
            
            key = (row_val, col_val)
            if key not in grid_map:
                grid_map[key] = []
            grid_map[key].append(idx)
        
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
        
        # Spacing - increased padding for better readability
        title_height = font_size + 40 if title else 0
        col_header_height = int(font_size * 1.0) + 25
        row_label_width = int(font_size * 5) if actual_row_axis else 0
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
                header_text = f"{self._format_axis_label(actual_col_axis)}: {self._format_value(col_val)}"
                draw.text((x, current_y + col_header_height // 2), header_text,
                          fill=text_rgb, font=header_font, anchor="mm")
        current_y += col_header_height
        
        # Draw rows
        for row_idx, row_val in enumerate(row_values):
            # Draw row label
            if actual_row_axis and row_val is not None:
                label_y = current_y + (img_height + cell_label_height) // 2
                row_text = f"{self._format_axis_label(actual_row_axis)}\n{self._format_value(row_val)}"
                draw.text((gap_size + row_label_width // 2, label_y), row_text,
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
            display_text = f"Prompt: {wrapped[:250]}..." if len(wrapped) > 250 else f"Prompt: {wrapped}"
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
    
    def _create_nested_xy_grids(
        self,
        images: List[Image.Image],
        labels: List[str],
        combinations: List[Dict],
        config: Dict[str, Any],
        row_axis: str,
        col_axis: str,
        nest_axis: str,
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
        Create nested grids when there are 3+ varying dimensions.
        Creates one XY grid for each value of the nest_axis, then combines them.
        
        Layout: Multiple XY grids stacked vertically or horizontally, one per nest_axis value.
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
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
                show_negative_prompt=show_negative_prompt
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
                show_negative_prompt=show_negative_prompt
            )
        
        # Group images by nest axis value
        nested_groups = {}  # nest_value -> [(idx, image, label, combo)]
        for idx, (img, combo) in enumerate(zip(images, combinations)):
            label = labels[idx] if idx < len(labels) else f"Image {idx}"
            nest_val = self._get_combo_value(combo, actual_nest_axis)
            
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
                    display_text = f"Prompt: {wrapped[:200]}..." if len(wrapped) > 200 else f"Prompt: {wrapped}"
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
            display_text = f"Prompt: {wrapped[:250]}..." if len(wrapped) > 250 else f"Prompt: {wrapped}"
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
    
    def _format_value(self, value: Any) -> str:
        """Format a value for display."""
        if value is None:
            return ""
        if isinstance(value, float):
            return f"{value:.2f}".rstrip('0').rstrip('.')
        if isinstance(value, str) and value.endswith('.safetensors'):
            return value[:-12]
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
        labels: str,
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
        save_prompt_grids_separately: bool = False,
        save_individuals: bool = False,
        save_metadata: bool = False,
        grid_split_by: str = "none",
        output_prefix: str = "compare",
        row_axis: str = "auto",
        col_axis: str = "auto",
        nest_axis: str = "none",
        html_grid_output: bool = False,
        html_image_format: str = "JPEG",
        html_image_quality: int = 85,
        video_config: Dict[str, Any] = None,
        prompt=None,
        extra_pnginfo=None,
        **kwargs  # Ignore any optional x_label, y_label, z_label
    ) -> Tuple[torch.Tensor, str, str, str]:
        """
        Create a comparison grid from images and labels.
        Organizes images by LoRA rows and strength columns with proper axis labels.
        
        For video output, handles multi-frame results and creates video grids.
        Video options come from optional video_config input (from Video Grid Config node).
        """
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
        
        # Parse labels - try newline-separated first, then semicolon for backwards compatibility
        if "\n" in labels:
            label_list = [l.strip() for l in labels.split("\n") if l.strip()]
        else:
            label_list = [l.strip() for l in labels.split(";") if l.strip()]
        
        # Convert ALL images to PIL (needed for video grid)
        all_pil_images = self._tensor_to_pil_list(images)
        
        # Check if images were padded (different original sizes stored in config)
        # If so, crop each image back to its original size
        combinations = config.get("combinations", [])
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

            # Detect what dimensions are varying in this comparison
            varying_dims = self._detect_varying_dimensions(combinations)
            
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
                
                # If split_by is "none" and we have 3+ dimensions, create a complete grid showing ALL images
                if grid_split_by == "none" and num_varying > 2:
                    grid_image = self._create_complete_grid(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
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
                elif num_varying > 2 or (nest_axis != "none" and nest_axis != "auto"):
                    # Create nested grids - one XY grid per value of nest_axis
                    grid_image = self._create_nested_xy_grids(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        row_axis=row_axis,
                        col_axis=col_axis,
                        nest_axis=nest_axis,
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
                    # Use smart XY grid with user-specified or auto-detected axes
                    grid_image = self._create_xy_grid(
                        images=pil_images,
                        labels=label_list,
                        combinations=combinations,
                        config=config,
                        row_axis=row_axis,
                        col_axis=col_axis,
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
            output_tensors = [self._pil_to_tensor(g) for g in all_grid_images]
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
    ) -> List[Dict[str, Any]]:
        """
        Split images into multiple grids based on a grouping dimension.
        
        Args:
            split_by: One of "model", "sampler", "scheduler", "chain", "auto"
        
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
                show_positive_prompt=False,
                show_negative_prompt=False,
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
    def IS_CHANGED(cls, images, config, labels, save_location, grid_title, **kwargs):
        """
        Compute a hash to determine if re-execution is needed.
        """
        import hashlib
        
        # Hash key inputs - add defensive checks for None
        combo_count = len(config.get("combinations", [])) if config else 0
        img_shape = str(images.shape) if hasattr(images, 'shape') else "unknown"
        
        hash_input = f"{combo_count}|{img_shape}|{labels}|{save_location}|{grid_title}"
        
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
