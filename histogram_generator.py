"""
Histogram Generator - Core histogram computation and visualization
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont
import torch
from typing import Dict, Tuple, List


class HistogramGenerator:
    """Generate and visualize histograms from image data."""
    
    def __init__(self):
        pass
    
    def compute_histogram(self, img_numpy: np.ndarray, bins: int = 256) -> Dict:
        """Compute histogram data for RGB and HSV."""
        histogram = {}
        
        # Ensure image is in [0, 255] range
        if img_numpy.dtype in [np.float32, np.float64]:
            if img_numpy.max() <= 1.0:
                img_numpy = (img_numpy * 255).astype(np.uint8)
            else:
                img_numpy = np.clip(img_numpy, 0, 255).astype(np.uint8)
        else:
            img_numpy = img_numpy.astype(np.uint8)
        
        # RGB histogram
        histogram['r'] = np.histogram(img_numpy[:, :, 0], bins=bins, range=(0, 256))[0]
        histogram['g'] = np.histogram(img_numpy[:, :, 1], bins=bins, range=(0, 256))[0]
        histogram['b'] = np.histogram(img_numpy[:, :, 2], bins=bins, range=(0, 256))[0]
        
        # Luminance (Y) histogram
        luminance = 0.299 * img_numpy[:, :, 0] + 0.587 * img_numpy[:, :, 1] + 0.114 * img_numpy[:, :, 2]
        histogram['luminance'] = np.histogram(luminance, bins=bins, range=(0, 256))[0]
        
        # Convert to HSV for hue histogram
        img_pil = Image.fromarray(img_numpy, mode='RGB')
        img_hsv = img_pil.convert('HSV')
        hsv_array = np.array(img_hsv)
        
        histogram['hue'] = np.histogram(hsv_array[:, :, 0], bins=bins, range=(0, 256))[0]
        histogram['saturation'] = np.histogram(hsv_array[:, :, 1], bins=bins, range=(0, 256))[0]
        histogram['value'] = np.histogram(hsv_array[:, :, 2], bins=bins, range=(0, 256))[0]
        histogram['hsv'] = hsv_array
        
        return histogram
    
    def compute_statistics(self, img_numpy: np.ndarray) -> Dict:
        """Compute basic statistics for the image."""
        if img_numpy.dtype in [np.float32, np.float64]:
            if img_numpy.max() <= 1.0:
                img_numpy = (img_numpy * 255).astype(np.uint8)
            else:
                img_numpy = np.clip(img_numpy, 0, 255).astype(np.uint8)
        else:
            img_numpy = img_numpy.astype(np.uint8)
        
        return {
            'r_min': int(img_numpy[:, :, 0].min()),
            'r_max': int(img_numpy[:, :, 0].max()),
            'r_mean': float(img_numpy[:, :, 0].mean()),
            'g_min': int(img_numpy[:, :, 1].min()),
            'g_max': int(img_numpy[:, :, 1].max()),
            'g_mean': float(img_numpy[:, :, 1].mean()),
            'b_min': int(img_numpy[:, :, 2].min()),
            'b_max': int(img_numpy[:, :, 2].max()),
            'b_mean': float(img_numpy[:, :, 2].mean()),
        }
    
    def draw_histogram_rgb(self, histogram: Dict, width: int, height: int, 
                          show_grid: bool, show_statistics: bool, statistics: Dict = None) -> torch.Tensor:
        """Draw RGB histogram."""
        img = self._create_histogram_image(
            [histogram['r'], histogram['g'], histogram['b']],
            colors=['red', 'green', 'blue'],
            width=width, height=height,
            title="RGB Histogram",
            show_grid=show_grid,
            show_statistics=show_statistics,
            statistics=statistics
        )
        return self._pil_to_tensor(img)
    
    def draw_histogram_individual(self, histogram: Dict, width: int, height: int,
                                 show_grid: bool, show_statistics: bool, statistics: Dict = None) -> torch.Tensor:
        """Draw individual R, G, B histograms side by side."""
        img = self._create_histogram_image(
            [histogram['r'], histogram['g'], histogram['b']],
            colors=['red', 'green', 'blue'],
            width=width, height=height,
            title="Individual R, G, B Histograms",
            show_grid=show_grid,
            show_statistics=show_statistics,
            statistics=statistics,
            separate=True
        )
        return self._pil_to_tensor(img)
    
    def draw_histogram_luminance(self, histogram: Dict, width: int, height: int,
                                show_grid: bool, show_statistics: bool, statistics: Dict = None) -> torch.Tensor:
        """Draw luminance histogram."""
        img = self._create_histogram_image(
            [histogram['luminance']],
            colors=['gray'],
            width=width, height=height,
            title="Luminance Histogram",
            show_grid=show_grid,
            show_statistics=show_statistics
        )
        return self._pil_to_tensor(img)
    
    def draw_histogram_hue(self, histogram: Dict, width: int, height: int,
                          show_grid: bool, show_statistics: bool, statistics: Dict = None, hsv_array: np.ndarray = None) -> torch.Tensor:
        """Draw hue histogram."""
        img = self._create_histogram_image(
            [histogram['hue']],
            colors=['orange'],
            width=width, height=height,
            title="Hue Histogram",
            show_grid=show_grid,
            show_statistics=show_statistics
        )
        return self._pil_to_tensor(img)
    
    def draw_histogram_hsv(self, histogram: Dict, width: int, height: int,
                          show_grid: bool, show_statistics: bool, statistics: Dict = None, hsv_array: np.ndarray = None) -> torch.Tensor:
        """Draw HSV histogram (hue, saturation, value)."""
        img = self._create_histogram_image(
            [histogram['hue'], histogram['saturation'], histogram['value']],
            colors=['orange', 'cyan', 'purple'],
            width=width, height=height,
            title="HSV Histogram (H, S, V)",
            show_grid=show_grid,
            show_statistics=show_statistics
        )
        return self._pil_to_tensor(img)
    
    def create_histogram_grid(self, images: List[torch.Tensor], layout: str = "vertical") -> torch.Tensor:
        """Combine multiple histogram images into a grid."""
        pil_images = [self._tensor_to_pil(img) for img in images]
        
        if layout == "vertical":
            # Stack vertically
            total_width = max(img.width for img in pil_images)
            total_height = sum(img.height for img in pil_images)
            
            grid = Image.new('RGB', (total_width, total_height), color=(40, 40, 40))
            y_offset = 0
            for img in pil_images:
                grid.paste(img, (0, y_offset))
                y_offset += img.height
        else:
            # Stack horizontally
            total_width = sum(img.width for img in pil_images)
            total_height = max(img.height for img in pil_images)
            
            grid = Image.new('RGB', (total_width, total_height), color=(40, 40, 40))
            x_offset = 0
            for img in pil_images:
                grid.paste(img, (x_offset, 0))
                x_offset += img.width
        
        return self._pil_to_tensor(grid)
    
    def _create_histogram_image(self, histograms: List[np.ndarray], colors: List[str],
                               width: int, height: int, title: str, show_grid: bool,
                               show_statistics: bool, statistics: Dict = None, separate: bool = False) -> Image.Image:
        """Create a histogram image with given parameters."""
        padding = 40
        title_height = 30 if title else 0
        stats_height = 80 if show_statistics else 0
        
        plot_width = width - 2 * padding
        plot_height = height - padding - title_height - stats_height
        
        # Create base image
        img = Image.new('RGB', (width, height), color=(40, 40, 40))
        draw = ImageDraw.Draw(img)
        
        # Draw title
        if title:
            try:
                font = ImageFont.load_default()
                draw.text((padding, 5), title, fill=(255, 255, 255), font=font)
            except:
                pass
        
        # Normalize histograms
        max_val = max(h.max() for h in histograms)
        if max_val == 0:
            max_val = 1
        
        # Draw histograms
        if separate and len(histograms) == 3:
            # Draw 3 separate histograms side by side
            sub_width = plot_width // 3
            for idx, (hist, color) in enumerate(zip(histograms, colors)):
                x_offset = padding + idx * sub_width
                self._draw_single_histogram(
                    draw, hist, color, x_offset, padding + title_height,
                    sub_width, plot_height, show_grid, max_val
                )
        else:
            # Draw overlaid histograms
            for hist, color in zip(histograms, colors):
                self._draw_single_histogram(
                    draw, hist, color, padding, padding + title_height,
                    plot_width, plot_height, show_grid, max_val
                )
        
        # Draw statistics
        if show_statistics and statistics:
            stats_y = padding + title_height + plot_height + 5
            stat_text = (
                f"R: min={statistics.get('r_min', 0)} max={statistics.get('r_max', 255)} "
                f"mean={statistics.get('r_mean', 0):.1f}  "
                f"G: min={statistics.get('g_min', 0)} max={statistics.get('g_max', 255)} "
                f"mean={statistics.get('g_mean', 0):.1f}  "
                f"B: min={statistics.get('b_min', 0)} max={statistics.get('b_max', 255)} "
                f"mean={statistics.get('b_mean', 0):.1f}"
            )
            try:
                font = ImageFont.load_default()
                draw.text((padding, stats_y), stat_text, fill=(255, 255, 255), font=font)
            except:
                pass
        
        return img
    
    def _draw_single_histogram(self, draw: ImageDraw.ImageDraw, histogram: np.ndarray,
                              color: str, x: int, y: int, width: int, height: int,
                              show_grid: bool, max_val: float):
        """Draw a single histogram on the image."""
        # Convert color name to RGB
        color_map = {
            'red': (255, 0, 0),
            'green': (0, 128, 0),
            'blue': (0, 0, 255),
            'gray': (128, 128, 128),
            'orange': (255, 165, 0),
            'cyan': (0, 255, 255),
            'purple': (128, 0, 128),
        }
        rgb_color = color_map.get(color, (0, 0, 0))
        
        # Draw grid
        if show_grid:
            for i in range(0, 256, 32):
                x_pos = x + (i / 256) * width
                draw.line([(x_pos, y), (x_pos, y + height)], fill=(200, 200, 200), width=1)
        
        # Draw histogram bars
        bin_width = width / len(histogram)
        for i, val in enumerate(histogram):
            if max_val > 0:
                bar_height = (val / max_val) * height
                x1 = x + i * bin_width
                y1 = y + height - bar_height
                x2 = x + (i + 1) * bin_width
                y2 = y + height
                
                draw.rectangle([x1, y1, x2, y2], fill=rgb_color, outline=rgb_color)
    
    def _pil_to_tensor(self, img: Image.Image) -> torch.Tensor:
        """Convert PIL Image to ComfyUI tensor format (batch, height, width, channels)."""
        img_array = np.array(img).astype(np.float32) / 255.0
        if img_array.ndim == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        # Shape: (height, width, 3) -> (1, height, width, 3)
        return torch.from_numpy(img_array).unsqueeze(0)
    
    def _tensor_to_pil(self, tensor: torch.Tensor) -> Image.Image:
        """Convert ComfyUI tensor to PIL Image."""
        if isinstance(tensor, torch.Tensor):
            img_numpy = tensor.cpu().numpy()
            if img_numpy.ndim == 4:
                img_numpy = img_numpy[0]
            
            if img_numpy.dtype in [np.float32, np.float64]:
                if img_numpy.max() <= 1.0:
                    img_numpy = (img_numpy * 255).astype(np.uint8)
                else:
                    img_numpy = np.clip(img_numpy, 0, 255).astype(np.uint8)
            else:
                img_numpy = img_numpy.astype(np.uint8)
            
            return Image.fromarray(img_numpy, mode='RGB')
        else:
            return Image.fromarray(tensor, mode='RGB')
