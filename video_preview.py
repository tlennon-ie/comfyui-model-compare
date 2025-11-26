"""
Video Preview Node
Preview video output in ComfyUI UI.
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
    Similar to Preview Image but for video files created by Grid Compare.
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
        Returns the video path and passes through images.
        """
        result = {
            "ui": {},
        }
        
        if video_path and os.path.exists(video_path):
            # Get video info for UI display
            filename = os.path.basename(video_path)
            subfolder = os.path.dirname(video_path)
            
            # Make path relative to output directory
            output_dir = folder_paths.get_output_directory()
            if video_path.startswith(output_dir):
                subfolder = os.path.relpath(os.path.dirname(video_path), output_dir)
            else:
                subfolder = ""
            
            result["ui"]["video"] = [{
                "filename": filename,
                "subfolder": subfolder,
                "type": "output",
                "format": video_path.rsplit('.', 1)[-1] if '.' in video_path else "mp4",
            }]
            
            print(f"[VideoPreview] Previewing: {video_path}")
        else:
            print(f"[VideoPreview] No video file at: {video_path}")
            result["ui"]["text"] = ["No video file found"]
        
        # Pass through images if provided
        output_images = images
        if output_images is None:
            # Create a small placeholder tensor
            output_images = torch.zeros((1, 64, 64, 3))
        
        return {"ui": result["ui"], "result": (video_path, output_images)}


class VideoGridPreview:
    """
    Combined preview for both image and video grids from Grid Compare.
    Shows image grid in standard preview and provides video path for external viewing.
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
        Shows the image grid in standard ComfyUI preview.
        """
        result_ui = {}
        
        # Process images for preview
        if images is not None and images.numel() > 0:
            # Convert to list of preview images
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
        
        # Add video info if available
        if video_path and os.path.exists(video_path):
            filename = os.path.basename(video_path)
            output_dir = folder_paths.get_output_directory()
            
            if video_path.startswith(output_dir):
                subfolder = os.path.relpath(os.path.dirname(video_path), output_dir)
            else:
                subfolder = ""
            
            result_ui["video"] = [{
                "filename": filename,
                "subfolder": subfolder,
                "type": "output",
                "format": video_path.rsplit('.', 1)[-1] if '.' in video_path else "mp4",
            }]
            print(f"[VideoGridPreview] Video available: {video_path}")
        
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
