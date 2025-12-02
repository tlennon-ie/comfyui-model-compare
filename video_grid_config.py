"""
Video Grid Config Node

Optional configuration for video output in Grid Compare.
When connected, enables video grid generation with these settings.
"""


class VideoGridConfig:
    """
    Configure video output options for Grid Compare.
    
    Connect this node's output to Grid Compare's video_config input
    to enable video grid generation with custom settings.
    """
    
    CATEGORY = "Model Compare/Grid"
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "video_output_mode": (["video_only", "both"], {
                    "default": "both",
                    "tooltip": "Output mode: video only or both images and video"
                }),
                "video_format": (["mp4", "gif", "webm"], {
                    "default": "mp4",
                    "tooltip": "Video format for video grid output"
                }),
                "video_codec": (["libx264", "libx265"], {
                    "default": "libx264",
                    "tooltip": "Video codec (h264 recommended for compatibility)"
                }),
                "video_quality": ("INT", {
                    "default": 23,
                    "min": 1,
                    "max": 51,
                    "step": 1,
                    "tooltip": "Video quality (CRF: lower = better, 18-28 recommended)"
                }),
            },
        }
    
    RETURN_TYPES = ("VIDEO_GRID_CONFIG",)
    RETURN_NAMES = ("video_config",)
    FUNCTION = "create_config"
    
    def create_config(
        self,
        video_output_mode: str = "both",
        video_format: str = "mp4",
        video_codec: str = "libx264",
        video_quality: int = 23,
    ):
        """Create video configuration dict."""
        config = {
            "video_output_mode": video_output_mode,
            "video_format": video_format,
            "video_codec": video_codec,
            "video_quality": video_quality,
        }
        return (config,)


# Node mappings
NODE_CLASS_MAPPINGS = {
    "VideoGridConfig": VideoGridConfig,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "VideoGridConfig": "Ⓜ️ Model Compare - Video Grid Config",
}
