"""
Grid Format Config Node

Provides styling configuration for hierarchical grid rendering.
Separates visual styling from layout logic (GridPresetFormula) and rendering (GridCompare).

Features:
- Header color palette (comma-separated hex codes) with depth-based coloring
- Border and gap settings
- Font configuration for headers and cell labels
- Transparency controls
"""

from typing import Dict, Any, Tuple, List
import os


def parse_color_palette(palette_string: str) -> List[str]:
    """
    Parse a comma-separated string of hex colors into a list.
    
    Args:
        palette_string: Comma-separated hex codes (e.g., "#F2EDD7, #FADADD, #D4E6F1")
        
    Returns:
        List of hex color strings, cleaned and validated
    """
    if not palette_string or not palette_string.strip():
        return ["#F2EDD7", "#FADADD", "#D4E6F1", "#E5E7E9"]  # Scientific palette default
    
    colors = []
    for color in palette_string.split(","):
        color = color.strip()
        # Ensure it starts with #
        if not color.startswith("#"):
            color = "#" + color
        # Validate hex format (basic check)
        if len(color) in (4, 7) and all(c in "0123456789ABCDEFabcdef#" for c in color):
            colors.append(color.upper())
    
    return colors if colors else ["#F2EDD7", "#FADADD", "#D4E6F1", "#E5E7E9"]


def get_color_for_depth(palette: List[str], depth: int) -> str:
    """
    Get the color for a specific header depth level.
    
    Args:
        palette: List of hex color strings
        depth: Header depth level (0 = outermost, higher = inner)
        
    Returns:
        Hex color string for that depth
    """
    if not palette:
        return "#E5E7E9"
    
    # Cycle through palette if depth exceeds palette length
    return palette[depth % len(palette)]


def darken_color(hex_color: str, factor: float = 0.1) -> str:
    """
    Darken a hex color by a factor.
    
    Args:
        hex_color: Hex color string (e.g., "#FADADD")
        factor: Amount to darken (0.0 = no change, 1.0 = black)
        
    Returns:
        Darkened hex color string
    """
    hex_color = hex_color.lstrip("#")
    
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        r = int(r * (1 - factor))
        g = int(g * (1 - factor))
        b = int(b * (1 - factor))
        
        return f"#{r:02X}{g:02X}{b:02X}"
    except (ValueError, IndexError):
        return hex_color


class GridFormatConfig:
    """
    Configure visual styling for hierarchical comparison grids.
    
    Provides a clean separation of concerns:
    - GridPresetFormula: Determines layout hierarchy (which fields go where)
    - GridFormatConfig: Determines visual styling (colors, fonts, borders)
    - GridCompare: Renders the final grid using both inputs
    
    Header Color Palette:
    - Comma-separated hex codes define colors for each hierarchy depth
    - Level 0 (outermost) uses first color, Level 1 uses second, etc.
    - If hierarchy is deeper than palette, colors cycle from start
    
    Default "Scientific" palette: #F2EDD7, #FADADD, #D4E6F1, #E5E7E9
    (Cream → Light Pink → Light Blue → Light Gray)
    """
    
    CATEGORY = "Model Compare/Grid"
    
    @classmethod
    def INPUT_TYPES(cls):
        # Get available fonts from system
        fonts = ["default", "arial", "segoeui", "consolas", "calibri"]
        font_dir = "C:\\Windows\\Fonts" if os.name == 'nt' else "/usr/share/fonts"
        if os.path.exists(font_dir):
            try:
                system_fonts = [f for f in os.listdir(font_dir) if f.lower().endswith('.ttf')]
                fonts.extend(system_fonts[:50])  # Limit to avoid huge dropdown
            except:
                pass
        
        return {
            "required": {
                # === Header Styling ===
                "header_colors": ("STRING", {
                    "default": "#F2EDD7, #FADADD, #D4E6F1, #E5E7E9",
                    "multiline": False,
                    "tooltip": "Comma-separated hex colors for header depth levels. Level 0 (outer) uses first color, Level 1 uses second, etc. Cycles if deeper than palette."
                }),
                "header_font_size": ("INT", {
                    "default": 32,
                    "min": 8,
                    "max": 120,
                    "step": 2,
                    "tooltip": "Base font size for header text. Outer headers may be slightly larger."
                }),
                "header_font_name": (fonts, {
                    "default": "default",
                    "tooltip": "Font for header labels"
                }),
                "header_text_color": ("STRING", {
                    "default": "#1A1A1A",
                    "multiline": False,
                    "tooltip": "Text color for header labels (hex code)"
                }),
                "header_padding": ("INT", {
                    "default": 12,
                    "min": 0,
                    "max": 50,
                    "step": 2,
                    "tooltip": "Padding inside header cells (pixels)"
                }),
                
                # === Border & Gap Styling ===
                "border_color": ("STRING", {
                    "default": "#2C2C2C",
                    "multiline": False,
                    "tooltip": "Color for grid borders (hex code)"
                }),
                "border_width": ("INT", {
                    "default": 2,
                    "min": 0,
                    "max": 20,
                    "step": 1,
                    "tooltip": "Width of grid borders in pixels"
                }),
                "gap_size": ("INT", {
                    "default": 4,
                    "min": 0,
                    "max": 50,
                    "step": 1,
                    "tooltip": "Gap between grid cells in pixels"
                }),
                "outer_border_width": ("INT", {
                    "default": 4,
                    "min": 0,
                    "max": 30,
                    "step": 1,
                    "tooltip": "Width of outer grid border in pixels"
                }),
                
                # === Cell Styling ===
                "cell_text_color": ("STRING", {
                    "default": "#1A1A1A",
                    "multiline": False,
                    "tooltip": "Text color for cell subtitles (hex code)"
                }),
                "cell_font_size": ("INT", {
                    "default": 18,
                    "min": 6,
                    "max": 72,
                    "step": 1,
                    "tooltip": "Font size for cell subtitle text"
                }),
                "cell_font_name": (fonts, {
                    "default": "default",
                    "tooltip": "Font for cell subtitle text"
                }),
                "cell_background": ("STRING", {
                    "default": "#FFFFFF",
                    "multiline": False,
                    "tooltip": "Background color for image cells (hex code)"
                }),
                
                # === Prompt Display ===
                "prompt_wrap_width": ("INT", {
                    "default": 80,
                    "min": 20,
                    "max": 300,
                    "step": 5,
                    "tooltip": "Characters per line for prompt text wrapping in headers (0 = no wrap)"
                }),
                
                # === Grid Background ===
                "grid_background": ("STRING", {
                    "default": "#F5F5F5",
                    "multiline": False,
                    "tooltip": "Overall grid background color (hex code)"
                }),
            },
            "optional": {
                # === Advanced Options ===
                "header_transparency": ("FLOAT", {
                    "default": 1.0,
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "tooltip": "Header background opacity (0.0 = transparent, 1.0 = opaque)"
                }),
                "scale_header_font_by_depth": ("BOOLEAN", {
                    "default": True,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Outer headers get slightly larger font, inner headers slightly smaller"
                }),
                "show_grid_title": ("BOOLEAN", {
                    "default": True,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Show title bar at top of grid"
                }),
                "title_font_size": ("INT", {
                    "default": 48,
                    "min": 12,
                    "max": 150,
                    "step": 2,
                    "tooltip": "Font size for grid title"
                }),
                "title_background": ("STRING", {
                    "default": "#2C2C2C",
                    "multiline": False,
                    "tooltip": "Background color for title bar (hex code)"
                }),
                "title_text_color": ("STRING", {
                    "default": "#FFFFFF",
                    "multiline": False,
                    "tooltip": "Text color for title (hex code)"
                }),
            },
        }
    
    RETURN_TYPES = ("GRID_FORMAT_CONFIG",)
    RETURN_NAMES = ("format_config",)
    FUNCTION = "create_config"
    
    def create_config(
        self,
        # Required
        header_colors: str,
        header_font_size: int,
        header_font_name: str,
        header_text_color: str,
        header_padding: int,
        border_color: str,
        border_width: int,
        gap_size: int,
        outer_border_width: int,
        cell_text_color: str,
        cell_font_size: int,
        cell_font_name: str,
        cell_background: str,
        prompt_wrap_width: int,
        grid_background: str,
        # Optional
        header_transparency: float = 1.0,
        scale_header_font_by_depth: bool = True,
        show_grid_title: bool = True,
        title_font_size: int = 48,
        title_background: str = "#2C2C2C",
        title_text_color: str = "#FFFFFF",
    ) -> Tuple[Dict[str, Any]]:
        """Create the format configuration dictionary."""
        
        # Parse the color palette
        palette = parse_color_palette(header_colors)
        
        config = {
            # Header styling
            "header_colors": palette,
            "header_colors_raw": header_colors,
            "header_font_size": header_font_size,
            "header_font_name": header_font_name,
            "header_text_color": header_text_color,
            "header_padding": header_padding,
            "header_transparency": header_transparency,
            "scale_header_font_by_depth": scale_header_font_by_depth,
            
            # Border & gap styling
            "border_color": border_color,
            "border_width": border_width,
            "gap_size": gap_size,
            "outer_border_width": outer_border_width,
            
            # Cell styling
            "cell_text_color": cell_text_color,
            "cell_font_size": cell_font_size,
            "cell_font_name": cell_font_name,
            "cell_background": cell_background,
            
            # Prompt display
            "prompt_wrap_width": prompt_wrap_width,
            
            # Grid background
            "grid_background": grid_background,
            
            # Title styling
            "show_grid_title": show_grid_title,
            "title_font_size": title_font_size,
            "title_background": title_background,
            "title_text_color": title_text_color,
        }
        
        return (config,)


def get_default_format_config() -> Dict[str, Any]:
    """
    Return default "Technical Grid" format config.
    
    Used when GridCompare doesn't receive a GridFormatConfig input.
    Clean, professional look with black borders and neutral colors.
    """
    return {
        # Header styling - Technical/neutral palette
        "header_colors": ["#E8E8E8", "#D4D4D4", "#C0C0C0", "#ACACAC"],
        "header_colors_raw": "#E8E8E8, #D4D4D4, #C0C0C0, #ACACAC",
        "header_font_size": 32,
        "header_font_name": "default",
        "header_text_color": "#1A1A1A",
        "header_padding": 12,
        "header_transparency": 1.0,
        "scale_header_font_by_depth": True,
        
        # Border & gap styling - Clean black borders
        "border_color": "#000000",
        "border_width": 2,
        "gap_size": 4,
        "outer_border_width": 4,
        
        # Cell styling
        "cell_text_color": "#1A1A1A",
        "cell_font_size": 18,
        "cell_font_name": "default",
        "cell_background": "#FFFFFF",
        
        # Prompt display
        "prompt_wrap_width": 80,
        
        # Grid background
        "grid_background": "#F0F0F0",
        
        # Title styling
        "show_grid_title": True,
        "title_font_size": 48,
        "title_background": "#1A1A1A",
        "title_text_color": "#FFFFFF",
    }


# Node registration
NODE_CLASS_MAPPINGS = {
    "GridFormatConfig": GridFormatConfig,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GridFormatConfig": "Ⓜ️ Model Compare - Grid Format Config",
}
