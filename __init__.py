"""
ComfyUI Model Compare - Simple Edition
A streamlined custom node for comparing different model configurations side-by-side.

Features:
- Load and configure models with multiple LoRA combinations
- Support for FLUX and QWEN diffusion models
- Generate comparison grids with multiple LoRA strengths
- Create customizable comparison grids with labels
- Histogram analysis for image comparison

Author: Your Name
Repository: https://github.com/yourusername/comfyui-model-compare
License: MIT
"""

from .model_compare_loaders import NODE_CLASS_MAPPINGS as LOADER_MAPPINGS
from .model_compare_loaders import NODE_DISPLAY_NAME_MAPPINGS as LOADER_DISPLAYS
from .prompt_compare import NODE_CLASS_MAPPINGS as PROMPT_MAPPINGS
from .prompt_compare import NODE_DISPLAY_NAME_MAPPINGS as PROMPT_DISPLAYS
from .sampler_compare_simple import NODE_CLASS_MAPPINGS as SAMPLER_SIMPLE_MAPPINGS
from .sampler_compare_simple import NODE_DISPLAY_NAME_MAPPINGS as SAMPLER_SIMPLE_DISPLAYS
from .sampler_compare_advanced import NODE_CLASS_MAPPINGS as SAMPLER_ADVANCED_MAPPINGS
from .sampler_compare_advanced import NODE_DISPLAY_NAME_MAPPINGS as SAMPLER_ADVANCED_DISPLAYS
from .grid_compare import NODE_CLASS_MAPPINGS as GRID_MAPPINGS
from .grid_compare import NODE_DISPLAY_NAME_MAPPINGS as GRID_DISPLAYS
from .histogram_analyzer import NODE_CLASS_MAPPINGS as HISTOGRAM_MAPPINGS
from .histogram_analyzer import NODE_DISPLAY_NAME_MAPPINGS as HISTOGRAM_DISPLAYS
from .video_preview import NODE_CLASS_MAPPINGS as VIDEO_PREVIEW_MAPPINGS
from .video_preview import NODE_DISPLAY_NAME_MAPPINGS as VIDEO_PREVIEW_DISPLAYS

# Merge all node mappings - only include the active nodes
NODE_CLASS_MAPPINGS = {
    **LOADER_MAPPINGS,
    **PROMPT_MAPPINGS,
    **SAMPLER_SIMPLE_MAPPINGS,
    **SAMPLER_ADVANCED_MAPPINGS,
    **GRID_MAPPINGS,
    **HISTOGRAM_MAPPINGS,
    **VIDEO_PREVIEW_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **LOADER_DISPLAYS,
    **PROMPT_DISPLAYS,
    **SAMPLER_SIMPLE_DISPLAYS,
    **SAMPLER_ADVANCED_DISPLAYS,
    **GRID_DISPLAYS,
    **HISTOGRAM_DISPLAYS,
    **VIDEO_PREVIEW_DISPLAYS,
}

# Required for ComfyUI to recognize this as a valid custom node package
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# Version and metadata for ComfyUI Manager
__version__ = "3.0.0"
WEB_DIRECTORY = "web"  # Web components for dynamic UI updates
