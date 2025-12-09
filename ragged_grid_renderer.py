"""
Ragged Hierarchy Grid Renderer

This module implements a tree-based grid renderer that properly handles
"ragged" hierarchies - where different branches have different children.

Key features:
- Tree traversal instead of Cartesian product
- Only renders dimensions explicitly in row/col hierarchy
- Handles "No LoRA" cases gracefully
- Proper geometry calculation with stacked Y-offsets
- Subtitles as cell content, not grid structure
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Tuple, Optional
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

from .grid_utils import (
    get_combo_field_value,
    clean_lora_name,
    clean_model_name,
    format_prompt_for_header,
    format_strength_value,
)


@dataclass
class TreeNode:
    """A node in the hierarchy tree."""
    value: Any  # The value at this level (e.g., model name, lora name)
    field: str  # The field name (e.g., 'model', 'lora_name')
    children: Dict[Any, 'TreeNode'] = field(default_factory=dict)
    image_indices: List[int] = field(default_factory=list)  # Leaf nodes have images
    
    def leaf_count(self) -> int:
        """Count total images under this node."""
        if self.image_indices:
            return len(self.image_indices)
        return sum(child.leaf_count() for child in self.children.values())
    
    def max_depth(self) -> int:
        """Get maximum depth of this subtree."""
        if not self.children:
            return 1
        return 1 + max(child.max_depth() for child in self.children.values())


@dataclass  
class GridCell:
    """Represents a cell in the final grid."""
    x: int
    y: int
    width: int
    height: int
    image_index: Optional[int] = None  # None = empty cell
    row_values: Tuple = ()  # Values for row headers
    col_values: Tuple = ()  # Values for column headers


@dataclass
class HeaderSpan:
    """Represents a header that may span multiple cells."""
    x: int
    y: int
    width: int
    height: int
    text: str
    field: str
    level: int  # Depth level in hierarchy
    is_column: bool


class RaggedHierarchyGrid:
    """
    Builds and renders a grid with ragged (non-uniform) hierarchies.
    
    This handles cases like:
    - Model A has 2 LoRAs with 3 strength values each
    - Model B has no LoRAs (shows "No LoRA" column)
    - Model C has 1 LoRA with 2 strength values
    """
    
    def __init__(
        self,
        combinations: List[Dict],
        config: Dict,
        images: List[Image.Image],
        row_hierarchy: List[str],
        col_hierarchy: List[str],
        format_config: Dict[str, Any],
        title: str = "",
        subtitle_config: Dict[str, bool] = None,
    ):
        self.combinations = combinations
        self.config = config
        self.images = images
        self.row_hierarchy = row_hierarchy
        self.col_hierarchy = col_hierarchy
        self.format_config = format_config
        self.title = title
        self.subtitle_config = subtitle_config or {}
        
        # Extract styling - OVERRIDE colors to use clean white/neutral backgrounds
        # User requested no yellow/pink/blue backgrounds
        self.header_colors = ['#FFFFFF', '#FFFFFF', '#FFFFFF']  # All white backgrounds
        self.header_font_size = format_config.get('header_font_size', 32)
        self.header_font_name = format_config.get('header_font_name', 'default')
        self.header_text_color = format_config.get('header_text_color', '#1A1A1A')
        self.header_padding = format_config.get('header_padding', 20)  # Increased padding
        self.gap_size = format_config.get('gap_size', 8)  # Increased gap
        self.border_color = format_config.get('border_color', '#CCCCCC')  # Lighter border for headers
        self.border_width = format_config.get('border_width', 1)
        self.grid_background = format_config.get('grid_background', '#FFFFFF')  # White background
        self.title_font_size = format_config.get('title_font_size', 48)
        self.title_background = format_config.get('title_background', '#1A1A1A')
        self.title_text_color = format_config.get('title_text_color', '#FFFFFF')
        self.show_grid_title = format_config.get('show_grid_title', True)
        self.prompt_wrap_width = format_config.get('prompt_wrap_width', 60)  # Narrower wrap for more lines
        
        # Calculate dimensions
        if images:
            self.img_width, self.img_height = images[0].size
        else:
            self.img_width, self.img_height = 512, 512
        
        # Track subtitle height
        self.show_subtitles = subtitle_config and any(
            v for k, v in subtitle_config.items() if k != 'show_field_names' and v
        )
        self.subtitle_font_size = int(self.header_font_size * 0.5)
        self.subtitle_height = (self.subtitle_font_size + 4) if self.show_subtitles else 0
    
    def build_tree(self) -> Tuple[TreeNode, TreeNode]:
        """
        Build row and column trees from actual combination data.
        
        Returns:
            (row_tree, col_tree) - Root nodes of each hierarchy tree
        """
        # Build row tree
        row_root = TreeNode(value=None, field='_root')
        col_root = TreeNode(value=None, field='_root')
        
        for idx, combo in enumerate(self.combinations):
            # Extract row values for this combination
            row_vals = tuple(
                get_combo_field_value(combo, self.config, f) 
                for f in self.row_hierarchy
            ) if self.row_hierarchy else ()
            
            # Extract col values
            col_vals = tuple(
                get_combo_field_value(combo, self.config, f)
                for f in self.col_hierarchy
            ) if self.col_hierarchy else ()
            
            # Insert into row tree
            self._insert_into_tree(row_root, row_vals, self.row_hierarchy, idx)
            
            # Insert into col tree
            self._insert_into_tree(col_root, col_vals, self.col_hierarchy, idx)
        
        return row_root, col_root
    
    def _insert_into_tree(
        self, 
        node: TreeNode, 
        values: Tuple, 
        fields: List[str], 
        image_idx: int
    ):
        """Insert a combination path into the tree."""
        if not values or not fields:
            node.image_indices.append(image_idx)
            return
        
        val = values[0]
        field = fields[0]
        
        # Normalize value for None/empty cases
        if val is None or val == '':
            val = 'No ' + field.replace('_', ' ').title()
        
        if val not in node.children:
            node.children[val] = TreeNode(value=val, field=field)
        
        self._insert_into_tree(
            node.children[val],
            values[1:],
            fields[1:],
            image_idx
        )
    
    def build_cell_map(self) -> Dict[Tuple, int]:
        """
        Build a map from (row_vals, col_vals) -> image_index.
        Only includes cells that actually have images.
        """
        cell_map = {}
        
        for idx, combo in enumerate(self.combinations):
            row_vals = tuple(
                get_combo_field_value(combo, self.config, f)
                for f in self.row_hierarchy
            ) if self.row_hierarchy else ()
            
            col_vals = tuple(
                get_combo_field_value(combo, self.config, f)
                for f in self.col_hierarchy
            ) if self.col_hierarchy else ()
            
            # Normalize None values
            row_vals = tuple(
                v if v is not None and v != '' else f'No {self.row_hierarchy[i].replace("_", " ").title()}'
                for i, v in enumerate(row_vals)
            ) if row_vals else ()
            
            col_vals = tuple(
                v if v is not None and v != '' else f'No {self.col_hierarchy[i].replace("_", " ").title()}'
                for i, v in enumerate(col_vals)
            ) if col_vals else ()
            
            cell_map[(row_vals, col_vals)] = idx
        
        return cell_map
    
    def get_unique_paths(self, root: TreeNode, hierarchy: List[str]) -> List[Tuple]:
        """Get all unique value paths in the tree."""
        if not root.children:
            return [()]
        
        paths = []
        for val, child in root.children.items():
            sub_paths = self.get_unique_paths(child, hierarchy[1:] if hierarchy else [])
            for sp in sub_paths:
                paths.append((val,) + sp)
        
        return paths if paths else [()]
    
    def render(self) -> Image.Image:
        """Render the complete grid."""
        if not self.images:
            return Image.new('RGB', (100, 100), color='white')
        
        print(f"[RaggedGrid] Rendering {len(self.images)} images")
        print(f"[RaggedGrid] Row hierarchy: {self.row_hierarchy}")
        print(f"[RaggedGrid] Col hierarchy: {self.col_hierarchy}")
        
        # Build trees and cell map
        row_tree, col_tree = self.build_tree()
        cell_map = self.build_cell_map()
        
        print(f"[RaggedGrid] Cell map has {len(cell_map)} entries")
        
        # Get unique row and column paths (from actual data, not Cartesian product)
        row_paths = self.get_unique_paths(row_tree, self.row_hierarchy)
        col_paths = self.get_unique_paths(col_tree, self.col_hierarchy)
        
        # Filter to only paths that have images
        valid_row_paths = []
        for rp in row_paths:
            for cp in col_paths:
                if (rp, cp) in cell_map:
                    if rp not in valid_row_paths:
                        valid_row_paths.append(rp)
                    break
        
        valid_col_paths = []
        for cp in col_paths:
            for rp in row_paths:
                if (rp, cp) in cell_map:
                    if cp not in valid_col_paths:
                        valid_col_paths.append(cp)
                    break
        
        print(f"[RaggedGrid] Valid paths: {len(valid_row_paths)} rows x {len(valid_col_paths)} cols")
        
        if not valid_row_paths:
            valid_row_paths = [()]
        if not valid_col_paths:
            valid_col_paths = [()]
        
        num_rows = len(valid_row_paths)
        num_cols = len(valid_col_paths)
        
        # Calculate dimensions using cursor approach
        current_y = 0
        
        # Title
        title_height = 0
        if self.title and self.show_grid_title:
            title_height = self.title_font_size + 30
            current_y = title_height
        
        # Column headers - one row per hierarchy level
        # Give prompts MUCH more height to show full text
        col_header_heights = []
        for field in self.col_hierarchy:
            if field in ['prompt_positive', 'prompt_negative']:
                # Allow 8 lines of wrapped text for prompts
                col_header_heights.append(self.header_font_size * 8 + self.header_padding * 2)
            else:
                col_header_heights.append(self.header_font_size + self.header_padding * 2)
        
        col_header_total_height = sum(col_header_heights) if col_header_heights else 0
        current_y += col_header_total_height
        
        # Row headers - calculate widths with MORE space
        row_header_widths = []
        for field in self.row_hierarchy:
            if field in ['prompt_positive', 'prompt_negative']:
                row_header_widths.append(min(500, max(300, self.prompt_wrap_width * 10)))
            elif field in ['lora_name', 'lora_group_label']:
                row_header_widths.append(250)  # Much wider for LoRA names
            elif field == 'model':
                row_header_widths.append(200)  # Wider for model names
            else:
                row_header_widths.append(180)  # Increased default width
        
        row_header_total_width = sum(row_header_widths) if row_header_widths else 0
        
        # Cell area
        cell_height = self.img_height + self.subtitle_height + self.gap_size
        cell_width = self.img_width + self.gap_size
        
        content_height = num_rows * cell_height
        content_width = num_cols * cell_width
        
        grid_width = row_header_total_width + content_width + self.gap_size * 2
        grid_height = title_height + col_header_total_height + content_height + self.gap_size * 2
        
        print(f"[RaggedGrid] Grid size: {grid_width}x{grid_height}")
        
        # Create canvas
        grid_bg = self._parse_color(self.grid_background)
        grid_img = Image.new('RGB', (grid_width, grid_height), color=grid_bg)
        draw = ImageDraw.Draw(grid_img)
        
        # Get fonts
        title_font = self._get_font(self.header_font_name, self.title_font_size)
        header_font = self._get_font(self.header_font_name, self.header_font_size)
        small_font = self._get_font(self.header_font_name, max(12, self.header_font_size - 6))
        subtitle_font = self._get_font(self.header_font_name, self.subtitle_font_size)
        
        header_text_rgb = self._parse_color(self.header_text_color)
        
        # Draw title
        current_y = 0
        if self.title and self.show_grid_title:
            title_bg = self._parse_color(self.title_background)
            title_text = self._parse_color(self.title_text_color)
            draw.rectangle([(0, 0), (grid_width, title_height)], fill=title_bg)
            draw.text(
                (grid_width // 2, title_height // 2),
                self.title, fill=title_text, font=title_font, anchor="mm"
            )
            current_y = title_height
        
        # Draw column headers with clean white backgrounds
        for level, (field, header_h) in enumerate(zip(self.col_hierarchy, col_header_heights)):
            header_bg = self._parse_color('#FFFFFF')  # Always white
            
            for col_idx, col_path in enumerate(valid_col_paths):
                x = row_header_total_width + col_idx * cell_width + self.gap_size
                
                # Draw background
                draw.rectangle(
                    [(x, current_y), (x + self.img_width, current_y + header_h)],
                    fill=header_bg
                )
                
                # Draw bottom border for separation
                draw.line(
                    [(x, current_y + header_h - 1), (x + self.img_width, current_y + header_h - 1)],
                    fill=self._parse_color('#CCCCCC'), width=1
                )
                
                # Get value for this level
                val = col_path[level] if level < len(col_path) else ""
                
                # Add field label for column headers
                field_label = field.replace('_', ' ').title()
                text = self._format_header_value(val, field)
                
                # For prompts, show label on first line
                if field in ['prompt_positive', 'prompt_negative']:
                    display_text = f"{field_label}:\n{text}"
                else:
                    display_text = text
                
                # Choose font
                use_font = small_font if field in ['prompt_positive', 'prompt_negative'] else header_font
                
                draw.text(
                    (x + self.img_width // 2, current_y + header_h // 2),
                    display_text, fill=header_text_rgb, font=use_font, anchor="mm"
                )
            
            current_y += header_h
        
        # Save Y position where images start
        img_area_start_y = current_y
        
        # Draw rows
        for row_idx, row_path in enumerate(valid_row_paths):
            row_y = img_area_start_y + row_idx * cell_height
            
            # Draw row headers with clear borders between columns
            level_x = self.gap_size
            for level, (field, header_w) in enumerate(zip(self.row_hierarchy, row_header_widths)):
                header_bg = self._parse_color('#FFFFFF')  # Always white background
                
                # Draw background (spans image height only)
                draw.rectangle(
                    [(level_x, row_y), (level_x + header_w - 2, row_y + self.img_height)],
                    fill=header_bg
                )
                
                # Draw right border to separate columns
                draw.line(
                    [(level_x + header_w - 1, row_y), (level_x + header_w - 1, row_y + self.img_height)],
                    fill=self._parse_color('#CCCCCC'), width=1
                )
                
                val = row_path[level] if level < len(row_path) else ""
                
                # Add field label as prefix for clarity (e.g., "Model: Flux2Dev")
                field_label = field.replace('_', ' ').title()
                text = self._format_header_value(val, field)
                display_text = f"{field_label}:\n{text}"
                
                use_font = small_font if field in ['prompt_positive', 'prompt_negative'] else header_font
                
                draw.text(
                    (level_x + header_w // 2, row_y + self.img_height // 2),
                    display_text, fill=header_text_rgb, font=use_font, anchor="mm"
                )
                
                level_x += header_w
            
            # Draw cells for this row
            for col_idx, col_path in enumerate(valid_col_paths):
                cell_x = row_header_total_width + col_idx * cell_width + self.gap_size
                cell_y = row_y
                
                # Check if this cell has an image
                img_idx = cell_map.get((row_path, col_path))
                
                if img_idx is not None and img_idx < len(self.images):
                    img = self.images[img_idx]
                    combo = self.combinations[img_idx] if img_idx < len(self.combinations) else {}
                    
                    # Resize if needed
                    if img.size != (self.img_width, self.img_height):
                        img = img.resize((self.img_width, self.img_height), Image.LANCZOS)
                    
                    # Draw border
                    if self.border_width > 0:
                        border_rgb = self._parse_color(self.border_color)
                        draw.rectangle(
                            [(cell_x - 1, cell_y - 1),
                             (cell_x + self.img_width + 1, cell_y + self.img_height + 1)],
                            outline=border_rgb, width=self.border_width
                        )
                    
                    # Paste image
                    grid_img.paste(img, (cell_x, cell_y))
                    
                    # Draw subtitle
                    if self.show_subtitles and self.subtitle_height > 0:
                        subtitle = self._generate_subtitle(combo, row_path, col_path)
                        if subtitle:
                            max_len = self.img_width // (self.subtitle_font_size // 2)
                            if len(subtitle) > max_len:
                                subtitle = subtitle[:max_len - 3] + "..."
                            draw.text(
                                (cell_x + self.img_width // 2, cell_y + self.img_height + 2),
                                subtitle, fill=header_text_rgb, font=subtitle_font, anchor="mt"
                            )
                else:
                    # Empty cell - this shouldn't happen with proper ragged handling
                    # But draw a subtle placeholder just in case
                    draw.rectangle(
                        [(cell_x, cell_y), (cell_x + self.img_width, cell_y + self.img_height)],
                        fill=self._parse_color('#E0E0E0')
                    )
        
        return grid_img
    
    def _format_header_value(self, val: Any, field: str) -> str:
        """Format a value for header display with clear labeling."""
        if val is None or val == '':
            return f"No {field.replace('_', ' ').title()}"
        
        if field in ['prompt_positive', 'prompt_negative']:
            # Wrap prompt with more lines allowed (8 lines instead of 3)
            lines = format_prompt_for_header(str(val), self.prompt_wrap_width, max_lines=8)
            return '\n'.join(lines) if lines else str(val)
        
        if field == 'lora_strength' or field.endswith('_strength'):
            return format_strength_value(val)
        
        # For row headers, add field label prefix for clarity
        text = str(val)
        # Don't truncate as aggressively - allow more space
        if len(text) > 40:
            text = text[:37] + "..."
        return text
    
    def _generate_subtitle(
        self, 
        combo: Dict, 
        row_path: Tuple, 
        col_path: Tuple
    ) -> str:
        """Generate subtitle text for a cell, excluding hierarchy fields."""
        if not self.subtitle_config:
            return ""
        
        # Fields already shown in hierarchy
        exclude_fields = set(self.row_hierarchy + self.col_hierarchy)
        
        # Map subtitle config keys to field names
        filter_map = {
            'model': 'model',
            'vae': 'vae', 
            'clip': 'clip',
            'lora': 'lora_name',
            'lora_strength': 'lora_strength',
            'sampler': 'sampler_name',
            'scheduler': 'scheduler',
            'cfg': 'cfg',
            'steps': 'steps',
            'seed': 'seed',
            'dimensions': ['width', 'height'],
            'prompt': 'prompt_positive',
            'negative_prompt': 'prompt_negative',
        }
        
        parts = []
        show_names = self.subtitle_config.get('show_field_names', False)
        
        for key, enabled in self.subtitle_config.items():
            if key == 'show_field_names' or not enabled:
                continue
            
            mapped = filter_map.get(key)
            if not mapped:
                continue
            
            fields = mapped if isinstance(mapped, list) else [mapped]
            
            for field in fields:
                if field in exclude_fields:
                    continue
                
                val = get_combo_field_value(combo, self.config, field)
                if val is not None and val != '':
                    formatted = format_strength_value(val) if 'strength' in field else str(val)
                    if len(formatted) > 30:
                        formatted = formatted[:27] + "..."
                    
                    if show_names:
                        name = field.replace('_', ' ').title()
                        parts.append(f"{name}: {formatted}")
                    else:
                        parts.append(formatted)
        
        return ' | '.join(parts)
    
    def _get_font(self, name: str, size: int) -> ImageFont.FreeTypeFont:
        """Get a font, falling back to default if not found."""
        try:
            if name and name != 'default':
                return ImageFont.truetype(name, size)
        except:
            pass
        
        # Try common fonts
        for font_name in ['arial.ttf', 'DejaVuSans.ttf', 'Roboto-Regular.ttf']:
            try:
                return ImageFont.truetype(font_name, size)
            except:
                pass
        
        return ImageFont.load_default()
    
    def _parse_color(self, color: str) -> Tuple[int, int, int]:
        """Parse color string to RGB tuple."""
        if isinstance(color, tuple):
            return color
        
        color = str(color).strip()
        if color.startswith('#'):
            color = color[1:]
        
        if len(color) == 6:
            try:
                return (
                    int(color[0:2], 16),
                    int(color[2:4], 16),
                    int(color[4:6], 16)
                )
            except ValueError:
                pass
        
        return (200, 200, 200)


def render_ragged_grid(
    images: List[Image.Image],
    combinations: List[Dict],
    config: Dict,
    row_hierarchy: List[str],
    col_hierarchy: List[str],
    format_config: Dict[str, Any],
    title: str = "",
    subtitle_config: Dict[str, bool] = None,
) -> Image.Image:
    """
    Main entry point for ragged hierarchy grid rendering.
    
    Args:
        images: List of PIL images
        combinations: List of combination dicts (from sampler)
        config: Full MODEL_COMPARE_CONFIG
        row_hierarchy: List of field names for row grouping (outer → inner)
        col_hierarchy: List of field names for column grouping (outer → inner)
        format_config: Visual styling config from GridFormatConfig
        title: Grid title
        subtitle_config: Which fields to show as subtitles
        
    Returns:
        Rendered grid as PIL Image
    """
    renderer = RaggedHierarchyGrid(
        combinations=combinations,
        config=config,
        images=images,
        row_hierarchy=row_hierarchy,
        col_hierarchy=col_hierarchy,
        format_config=format_config,
        title=title,
        subtitle_config=subtitle_config,
    )
    
    return renderer.render()
