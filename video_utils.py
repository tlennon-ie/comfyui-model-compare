"""
Video encoding utilities for Model Compare Grid
Uses ffmpeg for video creation, inspired by comfyui-videohelpersuite
"""

import os
import shutil
import subprocess
import numpy as np
from typing import List, Tuple, Optional
from PIL import Image

# ENCODE_ARGS for safe subprocess output decoding
ENCODE_ARGS = ("utf-8", 'backslashreplace')

def get_ffmpeg_path() -> Optional[str]:
    """Find ffmpeg executable."""
    # Check environment variable
    if "VHS_FORCE_FFMPEG_PATH" in os.environ:
        return os.environ.get("VHS_FORCE_FFMPEG_PATH")
    
    # Try imageio_ffmpeg
    try:
        from imageio_ffmpeg import get_ffmpeg_exe
        return get_ffmpeg_exe()
    except:
        pass
    
    # Try system ffmpeg
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    
    # Check local directory
    for name in ["ffmpeg", "ffmpeg.exe"]:
        if os.path.isfile(name):
            return os.path.abspath(name)
    
    return None


def tensor_to_bytes(tensor) -> np.ndarray:
    """Convert tensor (0-1 float) to uint8 numpy array."""
    if hasattr(tensor, 'cpu'):
        tensor = tensor.cpu().numpy()
    return np.clip(tensor * 255 + 0.5, 0, 255).astype(np.uint8)


def pil_to_bytes(img: Image.Image) -> bytes:
    """Convert PIL Image to raw RGB bytes."""
    return np.array(img).tobytes()


def create_video_from_frames(
    frames: List[Image.Image],
    output_path: str,
    fps: int = 24,
    format: str = "mp4",
    codec: str = "libx264",
    quality: int = 23,  # CRF for h264/h265
    loop: int = 0,  # For GIF: 0 = infinite loop
) -> bool:
    """
    Create video from PIL Image frames using ffmpeg.
    
    Args:
        frames: List of PIL Images (all same size)
        output_path: Output file path (without extension, will be added)
        fps: Frames per second
        format: Output format ('mp4', 'gif', 'webm')
        codec: Video codec ('libx264', 'libx265', 'gif', 'libvpx-vp9')
        quality: Quality setting (CRF for mp4, lower = better)
        loop: Loop count for GIF (0 = infinite)
    
    Returns:
        True if successful, False otherwise
    """
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        print("[VideoUtils] FFmpeg not found! Cannot create video.")
        return False
    
    if not frames:
        print("[VideoUtils] No frames provided!")
        return False
    
    # Get dimensions from first frame
    width, height = frames[0].size
    
    # Ensure dimensions are even (required by most codecs)
    if width % 2 != 0 or height % 2 != 0:
        new_width = width + (width % 2)
        new_height = height + (height % 2)
        frames = [f.resize((new_width, new_height), Image.Resampling.LANCZOS) for f in frames]
        width, height = new_width, new_height
    
    # Build output path with extension
    if not output_path.endswith(f'.{format}'):
        output_path = f"{output_path}.{format}"
    
    # Build ffmpeg command based on format
    if format == 'gif':
        # GIF creation with palette for better quality
        args = [
            ffmpeg_path, '-y', '-v', 'error',
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-s', f'{width}x{height}',
            '-r', str(fps),
            '-i', '-',
            '-vf', f'split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
            '-loop', str(loop),
            output_path
        ]
    elif format == 'webm':
        # WebM with VP9
        args = [
            ffmpeg_path, '-y', '-v', 'error',
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-s', f'{width}x{height}',
            '-r', str(fps),
            '-i', '-',
            '-c:v', 'libvpx-vp9',
            '-crf', str(quality),
            '-b:v', '0',
            '-pix_fmt', 'yuv420p',
            output_path
        ]
    else:
        # MP4 with H.264 (default)
        args = [
            ffmpeg_path, '-y', '-v', 'error',
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-s', f'{width}x{height}',
            '-r', str(fps),
            '-i', '-',
            '-c:v', codec,
            '-crf', str(quality),
            '-pix_fmt', 'yuv420p',
            '-movflags', '+faststart',
            output_path
        ]
    
    try:
        # Run ffmpeg process
        proc = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Write frames to ffmpeg stdin
        for frame in frames:
            # Convert PIL Image to RGB bytes
            rgb_data = np.array(frame.convert('RGB')).tobytes()
            proc.stdin.write(rgb_data)
        
        proc.stdin.close()
        stderr = proc.stderr.read()
        proc.wait()
        
        if proc.returncode != 0:
            print(f"[VideoUtils] FFmpeg error: {stderr.decode(*ENCODE_ARGS)}")
            return False
        
        print(f"[VideoUtils] Created video: {output_path}")
        return True
        
    except Exception as e:
        print(f"[VideoUtils] Error creating video: {e}")
        return False


def create_video_grid(
    video_frames_list: List[List[Image.Image]],
    labels: List[str],
    output_path: str,
    fps_list: List[int],
    grid_cols: int = 2,
    cell_size: Tuple[int, int] = (512, 512),
    padding: int = 10,
    label_height: int = 40,
    format: str = "mp4",
    codec: str = "libx264",
    quality: int = 23,
    font_size: int = 20,
    bg_color: Tuple[int, int, int] = (32, 32, 32),
    # New styling parameters to match image grid
    text_color: str = "#FFFFFF",
    border_color: str = "#000000",
    border_width: int = 2,
    font_name: str = "default",
    grid_title: str = "",
    positive_prompt: str = "",
) -> bool:
    """
    Create a video grid from multiple video sequences with styling matching image grid.
    
    For sequences of different lengths, shorter videos will freeze on last frame.
    For sequences with different FPS, they are normalized to the max FPS.
    
    Args:
        video_frames_list: List of frame lists (one per video)
        labels: List of labels for each video
        output_path: Output file path
        fps_list: List of FPS values for each video
        grid_cols: Number of columns in grid
        cell_size: Size of each cell (width, height)
        padding: Padding between cells
        label_height: Height reserved for labels
        format: Output format
        codec: Video codec
        quality: Quality setting
        font_size: Font size for labels
        bg_color: Background color tuple (R, G, B)
        text_color: Hex color for text
        border_color: Hex color for borders
        border_width: Border width in pixels
        font_name: Font name for labels
        grid_title: Title to show at top of grid
        positive_prompt: Positive prompt to show at bottom
    
    Returns:
        True if successful
    """
    from PIL import ImageDraw, ImageFont
    
    if not video_frames_list:
        print("[VideoUtils] No videos provided!")
        return False
    
    # Parse colors from hex
    def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    text_rgb = hex_to_rgb(text_color) if text_color.startswith('#') else (255, 255, 255)
    border_rgb = hex_to_rgb(border_color) if border_color.startswith('#') else (0, 0, 0)
    
    num_videos = len(video_frames_list)
    grid_rows = (num_videos + grid_cols - 1) // grid_cols
    
    # Calculate space for title and prompt
    title_height = font_size + 20 if grid_title else 0
    prompt_height = 0
    if positive_prompt:
        # Estimate prompt height (wrap text)
        prompt_font_size = max(12, font_size // 2)
        num_prompt_lines = max(1, len(positive_prompt) // 80 + 1)  # Approx 80 chars per line
        prompt_height = prompt_font_size * num_prompt_lines + 30
    
    # Calculate grid dimensions
    grid_width = grid_cols * (cell_size[0] + padding) + padding
    grid_height = (
        title_height +
        grid_rows * (cell_size[1] + label_height + padding) + padding +
        prompt_height
    )
    
    # Find max frame count and normalize FPS
    max_fps = max(fps_list) if fps_list else 24
    
    # Calculate total frames needed (based on longest video at its native FPS)
    max_duration = 0
    for i, frames in enumerate(video_frames_list):
        if frames:
            fps = fps_list[i] if i < len(fps_list) else 24
            duration = len(frames) / fps
            max_duration = max(max_duration, duration)
    
    total_output_frames = int(max_duration * max_fps)
    if total_output_frames == 0:
        total_output_frames = 1
    
    print(f"[VideoUtils] Creating video grid: {grid_cols}x{grid_rows}, {total_output_frames} frames at {max_fps} FPS")
    
    # Load fonts
    def load_font(name: str, size: int):
        if name != "default":
            try:
                font_dir = "C:\\Windows\\Fonts" if os.name == 'nt' else "/usr/share/fonts"
                font_path = os.path.join(font_dir, name)
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, size)
            except:
                pass
        # Fallback fonts
        for fallback in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                return ImageFont.truetype(fallback, size)
            except:
                continue
        return ImageFont.load_default()
    
    font = load_font(font_name, font_size)
    title_font = load_font(font_name, font_size + 10)
    prompt_font = load_font(font_name, max(12, font_size // 2))
    
    # Generate grid frames
    grid_frames = []
    
    for frame_idx in range(total_output_frames):
        # Create grid background
        grid_img = Image.new('RGB', (grid_width, grid_height), bg_color)
        draw = ImageDraw.Draw(grid_img)
        
        # Draw title at top
        if grid_title:
            bbox = draw.textbbox((0, 0), grid_title, font=title_font)
            title_width = bbox[2] - bbox[0]
            title_x = (grid_width - title_width) // 2
            draw.text((title_x, 10), grid_title, fill=text_rgb, font=title_font)
        
        # Time position in seconds
        time_pos = frame_idx / max_fps
        
        for vid_idx, video_frames in enumerate(video_frames_list):
            if not video_frames:
                continue
            
            row = vid_idx // grid_cols
            col = vid_idx % grid_cols
            
            # Get FPS for this video
            vid_fps = fps_list[vid_idx] if vid_idx < len(fps_list) else 24
            
            # Calculate which frame to show at this time
            source_frame_idx = int(time_pos * vid_fps)
            # Clamp to valid range (freeze on last frame if video ended)
            source_frame_idx = min(source_frame_idx, len(video_frames) - 1)
            
            frame = video_frames[source_frame_idx]
            
            # Resize frame to cell size
            frame_resized = frame.resize(cell_size, Image.Resampling.LANCZOS)
            
            # Calculate position (offset by title height)
            x = padding + col * (cell_size[0] + padding)
            y = title_height + padding + row * (cell_size[1] + label_height + padding)
            
            # Draw border around cell
            if border_width > 0:
                draw.rectangle(
                    [x - border_width, y + label_height - border_width,
                     x + cell_size[0] + border_width, y + label_height + cell_size[1] + border_width],
                    outline=border_rgb,
                    width=border_width
                )
            
            # Paste frame
            grid_img.paste(frame_resized, (x, y + label_height))
            
            # Draw label
            label = labels[vid_idx] if vid_idx < len(labels) else f"Video {vid_idx + 1}"
            # Truncate label if too long
            max_label_len = max(20, cell_size[0] // (font_size // 2))
            if len(label) > max_label_len:
                label = label[:max_label_len - 3] + "..."
            
            # Center label above cell
            bbox = draw.textbbox((0, 0), label, font=font)
            text_width = bbox[2] - bbox[0]
            text_x = x + (cell_size[0] - text_width) // 2
            draw.text((text_x, y + 5), label, fill=text_rgb, font=font)
        
        # Draw positive prompt at bottom
        if positive_prompt:
            prompt_y = grid_height - prompt_height + 10
            # Word wrap prompt
            words = positive_prompt.split()
            lines = []
            current_line = ""
            max_line_width = grid_width - 40
            
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=prompt_font)
                if bbox[2] - bbox[0] <= max_line_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            
            # Draw "Positive Prompt:" label
            draw.text((20, prompt_y), "Positive Prompt:", fill=text_rgb, font=prompt_font)
            prompt_y += prompt_font.size + 5
            
            # Draw wrapped prompt text
            for line in lines[:3]:  # Limit to 3 lines
                draw.text((20, prompt_y), line, fill=text_rgb, font=prompt_font)
                prompt_y += prompt_font.size + 2
        
        grid_frames.append(grid_img)
    
    # Create video from grid frames
    return create_video_from_frames(
        grid_frames,
        output_path,
        fps=max_fps,
        format=format,
        codec=codec,
        quality=quality
    )


def is_video_output(images_batch, num_frames_threshold: int = 2) -> bool:
    """
    Check if the output appears to be video (multiple frames from video model).
    
    Args:
        images_batch: Tensor or list of images
        num_frames_threshold: Minimum frames to consider as video
    
    Returns:
        True if appears to be video output
    """
    if hasattr(images_batch, 'shape'):
        # Tensor - check first dimension (batch/frames)
        return images_batch.shape[0] >= num_frames_threshold
    elif isinstance(images_batch, list):
        return len(images_batch) >= num_frames_threshold
    return False
