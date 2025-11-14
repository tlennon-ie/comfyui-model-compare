"""
ComfyUI Model Compare
A comprehensive custom node for comparing different model configurations side-by-side.

Features:
- Load and configure multiple checkpoints, VAEs, text encoders, and LoRAs
- Generate all combinations of model configurations
- Sample and compare different configurations in a single workflow
- Create customizable comparison grids with labels and styling
- Save individual results and comparison grids

Author: Your Name
Repository: https://github.com/yourusername/comfyui-model-compare
License: MIT
"""

from .model_compare_loaders import NODE_CLASS_MAPPINGS as LOADER_MAPPINGS
from .model_compare_loaders import NODE_DISPLAY_NAME_MAPPINGS as LOADER_DISPLAYS
from .sampler_compare import NODE_CLASS_MAPPINGS as SAMPLER_MAPPINGS
from .sampler_compare import NODE_DISPLAY_NAME_MAPPINGS as SAMPLER_DISPLAYS
from .grid_compare import NODE_CLASS_MAPPINGS as GRID_MAPPINGS
from .grid_compare import NODE_DISPLAY_NAME_MAPPINGS as GRID_DISPLAYS

# Merge all node mappings
NODE_CLASS_MAPPINGS = {
    **LOADER_MAPPINGS,
    **SAMPLER_MAPPINGS,
    **GRID_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **LOADER_DISPLAYS,
    **SAMPLER_DISPLAYS,
    **GRID_DISPLAYS,
}

# Required for ComfyUI to recognize this as a valid custom node package
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# Version and metadata for ComfyUI Manager
__version__ = "1.0.0"
WEB_DIRECTORY = None  # No web components needed for now
