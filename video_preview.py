"""
Video Preview Node
Preview video output in ComfyUI UI.

NOTE: ComfyUI's UI uses {"images": [...], "animated": (True,)} format for video preview.
The "video" key is NOT recognized by the standard ComfyUI preview widget.
"""

import os
import torch
import numpy as np
from typing import Dict, Any, Tuple, List
from PIL import Image
import folder_paths
import json


class VideoPreview:
    """
    Preview video files in the ComfyUI interface.
    Uses the animated image format for video display.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Path to video file (from Grid Compare video_path output)"
                }),
            },
            "optional": {
                "images": ("IMAGE", {
                    "tooltip": "Optional: Pass images through for chaining"
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    CATEGORY = "Video Helper Suite 🎥 Model Compare"
    RETURN_TYPES = ("STRING", "IMAGE")
    RETURN_NAMES = ("video_path", "images")
    FUNCTION = "preview_video"
    OUTPUT_NODE = True

    def preview_video(
        self,
        video_path: str,
        images=None,
        prompt=None,
        extra_pnginfo=None,
    ) -> Tuple[str, Any]:
        """
        Preview video in the ComfyUI UI.
        Uses the animated image format for video display.
        """
        result_ui = {}
        
        if video_path and os.path.exists(video_path):
            # Get video info for UI display
            filename = os.path.basename(video_path)
            
            # Make path relative to output directory
            output_dir = folder_paths.get_output_directory()
            if video_path.startswith(output_dir):
                subfolder = os.path.relpath(os.path.dirname(video_path), output_dir)
            else:
                subfolder = ""
            
            # Use "images" key with "animated" flag for video preview in UI
            # This is the correct format for ComfyUI's preview widget
            result_ui["images"] = [{
                "filename": filename,
                "subfolder": subfolder,
                "type": "output",
            }]
            # Mark as animated content (video)
            result_ui["animated"] = (True,)
            
            print(f"[VideoPreview] Previewing video: {video_path}")
        else:
            print(f"[VideoPreview] No video file at: {video_path}")
            result_ui["text"] = ["No video file found"]
        
        # Pass through images if provided
        output_images = images
        if output_images is None:
            # Create a small placeholder tensor
            output_images = torch.zeros((1, 64, 64, 3))
        
        return {"ui": result_ui, "result": (video_path, output_images)}


class VideoGridPreview:
    """
    Combined preview for both image and video grids from Grid Compare.
    Shows image grid in standard preview and provides video info for display.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE", {
                    "tooltip": "Image grid from Grid Compare"
                }),
                "image_path": ("STRING", {
                    "default": "",
                    "tooltip": "Image save path from Grid Compare"
                }),
            },
            "optional": {
                "video_path": ("STRING", {
                    "default": "",
                    "tooltip": "Video path from Grid Compare (optional)"
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    CATEGORY = "Video Helper Suite 🎥 Model Compare"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("images", "image_path", "video_path")
    FUNCTION = "preview_grid"
    OUTPUT_NODE = True

    def preview_grid(
        self,
        images: torch.Tensor,
        image_path: str,
        video_path: str = "",
        prompt=None,
        extra_pnginfo=None,
    ) -> Tuple[torch.Tensor, str, str]:
        """
        Preview both image and video grids.
        If video_path is provided, shows video using animated format.
        Otherwise shows the image grid in standard ComfyUI preview.
        """
        result_ui = {}
        
        # Check if we have a video to display
        if video_path and os.path.exists(video_path):
            # Video preview takes priority - use animated images format
            filename = os.path.basename(video_path)
            output_dir = folder_paths.get_output_directory()
            
            if video_path.startswith(output_dir):
                subfolder = os.path.relpath(os.path.dirname(video_path), output_dir)
            else:
                subfolder = ""
            
            # Use images key with animated flag for video
            result_ui["images"] = [{
                "filename": filename,
                "subfolder": subfolder,
                "type": "output",
            }]
            result_ui["animated"] = (True,)
            print(f"[VideoGridPreview] Video preview: {video_path}")
            
        elif images is not None and images.numel() > 0:
            # Fall back to image preview
            previews = []
            for i in range(images.shape[0]):
                img = images[i]
                img_np = (img.cpu().numpy() * 255).astype(np.uint8)
                
                # Save temp preview image
                temp_dir = folder_paths.get_temp_directory()
                os.makedirs(temp_dir, exist_ok=True)
                preview_path = os.path.join(temp_dir, f"preview_grid_{i}.png")
                
                pil_img = Image.fromarray(img_np)
                pil_img.save(preview_path)
                
                previews.append({
                    "filename": os.path.basename(preview_path),
                    "subfolder": "",
                    "type": "temp",
                })
            
            result_ui["images"] = previews
        
        # Log info
        if image_path:
            print(f"[VideoGridPreview] Image grid: {image_path}")
        
        return {"ui": result_ui, "result": (images, image_path, video_path)}


# Node mappings
NODE_CLASS_MAPPINGS = {
    "VideoPreview": VideoPreview,
    "VideoGridPreview": VideoGridPreview,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoPreview": "Video Preview 🎥",
    "VideoGridPreview": "Video Grid Preview 🎥",
}
