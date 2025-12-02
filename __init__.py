"""
ComfyUI Model Compare - Advanced Edition
A streamlined custom node for comparing different model configurations side-by-side.

Features:
- Load and configure models with multiple LoRA combinations
- Support for FLUX, QWEN, WAN, Hunyuan diffusion models
- Generate comparison grids with multiple configurations
- Create customizable comparison grids with labels
- Histogram analysis for image comparison
- Gallery viewer for browsing all generated grids

Author: Your Name
Repository: https://github.com/yourusername/comfyui-model-compare
License: MIT
"""

from .model_compare_loaders import NODE_CLASS_MAPPINGS as LOADER_MAPPINGS
from .model_compare_loaders import NODE_DISPLAY_NAME_MAPPINGS as LOADER_DISPLAYS
from .prompt_compare import NODE_CLASS_MAPPINGS as PROMPT_MAPPINGS
from .prompt_compare import NODE_DISPLAY_NAME_MAPPINGS as PROMPT_DISPLAYS
from .sampling_config_chain import NODE_CLASS_MAPPINGS as CONFIG_CHAIN_MAPPINGS
from .sampling_config_chain import NODE_DISPLAY_NAME_MAPPINGS as CONFIG_CHAIN_DISPLAYS
from .lora_compare import NODE_CLASS_MAPPINGS as LORA_MAPPINGS
from .lora_compare import NODE_DISPLAY_NAME_MAPPINGS as LORA_DISPLAYS
from .sampler_compare_advanced import NODE_CLASS_MAPPINGS as SAMPLER_ADVANCED_MAPPINGS
from .sampler_compare_advanced import NODE_DISPLAY_NAME_MAPPINGS as SAMPLER_ADVANCED_DISPLAYS
from .grid_compare import NODE_CLASS_MAPPINGS as GRID_MAPPINGS
from .grid_compare import NODE_DISPLAY_NAME_MAPPINGS as GRID_DISPLAYS
from .video_grid_config import NODE_CLASS_MAPPINGS as VIDEO_CONFIG_MAPPINGS
from .video_grid_config import NODE_DISPLAY_NAME_MAPPINGS as VIDEO_CONFIG_DISPLAYS
from .histogram_analyzer import NODE_CLASS_MAPPINGS as HISTOGRAM_MAPPINGS
from .histogram_analyzer import NODE_DISPLAY_NAME_MAPPINGS as HISTOGRAM_DISPLAYS
from .video_preview import NODE_CLASS_MAPPINGS as VIDEO_PREVIEW_MAPPINGS
from .video_preview import NODE_DISPLAY_NAME_MAPPINGS as VIDEO_PREVIEW_DISPLAYS
from .compare_tracker import NODE_CLASS_MAPPINGS as TRACKER_MAPPINGS
from .compare_tracker import NODE_DISPLAY_NAME_MAPPINGS as TRACKER_DISPLAYS

# Import gallery routes to register them with the server
try:
    from . import gallery_routes
except Exception as e:
    print(f"[ModelCompare] Warning: Could not load gallery routes: {e}")

# Import preset analysis routes
try:
    from . import preset_routes
except Exception as e:
    print(f"[ModelCompare] Warning: Could not load preset routes: {e}")

# Merge all node mappings - only include the active nodes
NODE_CLASS_MAPPINGS = {
    **LOADER_MAPPINGS,
    **PROMPT_MAPPINGS,
    **CONFIG_CHAIN_MAPPINGS,
    **LORA_MAPPINGS,
    **SAMPLER_ADVANCED_MAPPINGS,
    **GRID_MAPPINGS,
    **VIDEO_CONFIG_MAPPINGS,
    **HISTOGRAM_MAPPINGS,
    **VIDEO_PREVIEW_MAPPINGS,
    **TRACKER_MAPPINGS,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    **LOADER_DISPLAYS,
    **PROMPT_DISPLAYS,
    **CONFIG_CHAIN_DISPLAYS,
    **LORA_DISPLAYS,
    **SAMPLER_ADVANCED_DISPLAYS,
    **GRID_DISPLAYS,
    **VIDEO_CONFIG_DISPLAYS,
    **HISTOGRAM_DISPLAYS,
    **VIDEO_PREVIEW_DISPLAYS,
    **TRACKER_DISPLAYS,
}

# Required for ComfyUI to recognize this as a valid custom node package
__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS']

# Version and metadata for ComfyUI Manager
__version__ = "3.0.0"
WEB_DIRECTORY = "web"  # Web components for dynamic UI updates
