"""
Histogram Analyzer Node - Displays image histogram with multiple visualization modes
"""

import torch
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo
from typing import Tuple, Dict, List
import json
import os
import folder_paths
from comfy.cli_args import args
from .histogram_generator import HistogramGenerator


class HistogramAnalyzer:
    """
    Analyze and visualize image histograms with multiple modes and statistics.
    Outputs separate image for each histogram type.
    """
    
    def __init__(self):
        self.histogram_gen = HistogramGenerator()
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "width": ("INT", {
                    "default": 800,
                    "min": 300,
                    "max": 2400,
                    "step": 100,
                    "tooltip": "Output histogram width in pixels",
                }),
                "height": ("INT", {
                    "default": 400,
                    "min": 200,
                    "max": 1200,
                    "step": 50,
                    "tooltip": "Output histogram height in pixels",
                }),
                "bins": ([128, 256, 512], {
                    "default": 256,
                    "tooltip": "Number of histogram bins - higher = more detail but slower",
                }),
                "show_grid": ("BOOLEAN", {
                    "default": True,
                    "label_on": "enabled",
                    "label_off": "disabled",
                    "tooltip": "Display grid lines for reference",
                }),
                "show_statistics": ("BOOLEAN", {
                    "default": True,
                    "label_on": "enabled",
                    "label_off": "disabled",
                    "tooltip": "Display min, max, mean statistics",
                }),
            },
            "optional": {
                "save_images": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Save histogram images to disk",
                }),
                "save_location": ("STRING", {
                    "default": "histograms",
                    "multiline": False,
                    "tooltip": "Output folder path for saved images",
                }),
                "save_metadata": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Embed workflow metadata in PNG files",
                }),
            },
            "hidden": {
                "prompt": "PROMPT", 
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }
    
    CATEGORY = "image/analysis"
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("rgb_histogram", "individual_histogram", "luminance_histogram", "hue_histogram", "hsv_histogram", "all_types_grid", "statistics")
    FUNCTION = "analyze"
    OUTPUT_NODE = True
    
    def analyze(self, image: torch.Tensor, width: int, height: int, bins: int, 
                show_grid: bool, show_statistics: bool, save_images: bool = False, 
                save_location: str = "histograms", save_metadata: bool = False,
                prompt=None, extra_pnginfo=None) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, str]:
        """
        Generate all histogram visualizations from input image.
        """
        print(f"[HistogramAnalyzer] Analyzing image histogram - generating all types")
        print(f"  Image shape: {image.shape}")
        
        # Convert ComfyUI tensor to numpy
        if isinstance(image, torch.Tensor):
            img_numpy = image.cpu().numpy()
            if img_numpy.ndim == 5:
                # 5D: [batch, frames, height, width, channels] - take first batch, first frame
                img_numpy = img_numpy[0, 0]
            elif img_numpy.ndim == 4:
                # 4D: [batch, height, width, channels] - take first batch
                img_numpy = img_numpy[0]
        else:
            img_numpy = np.array(image)
        
        # Ensure correct format
        if img_numpy.ndim == 2:
            img_numpy = np.stack([img_numpy] * 3, axis=-1)
        elif img_numpy.ndim == 3 and img_numpy.shape[2] == 4:
            img_numpy = img_numpy[:, :, :3]
        
        # Compute histogram and statistics
        histogram = self.histogram_gen.compute_histogram(img_numpy, bins=bins)
        statistics = self.histogram_gen.compute_statistics(img_numpy)
        
        print(f"[HistogramAnalyzer] Histogram computed, generating visualizations...")
        
        # Generate all histogram types
        rgb_image = self.histogram_gen.draw_histogram_rgb(
            histogram, width, height, show_grid, show_statistics, statistics
        )
        individual_image = self.histogram_gen.draw_histogram_individual(
            histogram, width, height, show_grid, show_statistics, statistics
        )
        luminance_image = self.histogram_gen.draw_histogram_luminance(
            histogram, width, height, show_grid, show_statistics, statistics
        )
        hue_image = self.histogram_gen.draw_histogram_hue(
            histogram, width, height, show_grid, show_statistics, statistics, histogram.get('hsv')
        )
        hsv_image = self.histogram_gen.draw_histogram_hsv(
            histogram, width, height, show_grid, show_statistics, statistics, histogram.get('hsv')
        )
        
        # Create all-types grid (5 rows x 1 column)
        # Note: create_histogram_grid expects tensors now if we change it, 
        # but let's check histogram_generator.py. 
        # Wait, histogram_generator.create_histogram_grid takes TENSORS as input?
        # Let's check line 141 of histogram_generator.py: 
        # def create_histogram_grid(self, images: List[torch.Tensor], ...
        # Yes, it takes tensors.
        
        all_types_grid = self.histogram_gen.create_histogram_grid(
            [rgb_image, individual_image, luminance_image, hue_image, hsv_image],
            layout="vertical"
        )
        
        # Save if requested
        if save_images:
            # _save_images expects PIL images or tensors. 
            # If we pass tensors, it converts them.
            self._save_images(
                [rgb_image, individual_image, luminance_image, hue_image, hsv_image, all_types_grid],
                ["rgb", "individual", "luminance", "hue", "hsv", "all_types"],
                save_location, save_metadata, prompt, extra_pnginfo
            )
        
        # Collect tensors directly
        tensors = [rgb_image, individual_image, luminance_image, hue_image, hsv_image, all_types_grid]
        
        # Format statistics as JSON string
        stats_json = json.dumps(statistics, indent=2)
        
        print(f"[HistogramAnalyzer] Analysis complete")
        
        return (*tensors, stats_json)
    
    def _save_images(self, images: list, names: list, save_location: str, save_metadata: bool, prompt, extra_pnginfo):
        """Save histogram images with optional metadata."""
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Find next available counter
        counter = 0
        while True:
            test_path = os.path.join(save_dir, f"histogram_{counter:05d}_rgb.png")
            if not os.path.exists(test_path):
                break
            counter += 1
        
        # Create metadata if requested
        metadata = None
        if save_metadata and not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for key in extra_pnginfo:
                    metadata.add_text(key, json.dumps(extra_pnginfo[key]))
        
        # Save each image
        for img, name in zip(images, names):
            # Convert tensor to PIL if needed
            if isinstance(img, torch.Tensor):
                img_pil = self._tensor_to_pil(img)
            else:
                img_pil = img
            
            filename = f"histogram_{counter:05d}_{name}.png"
            filepath = os.path.join(save_dir, filename)
            img_pil.save(filepath, pnginfo=metadata, compress_level=4)
            print(f"[HistogramAnalyzer] Saved: {filename}")
    
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


class HistogramComparator:
    """
    Compare two images side-by-side histograms.
    Outputs separate images for each histogram type comparison.
    """
    
    def __init__(self):
        self.histogram_gen = HistogramGenerator()
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image_1": ("IMAGE",),
                "image_2": ("IMAGE",),
                "width": ("INT", {
                    "default": 1200,
                    "min": 400,
                    "max": 2400,
                    "step": 100,
                    "tooltip": "Output histogram width in pixels",
                }),
                "height": ("INT", {
                    "default": 400,
                    "min": 200,
                    "max": 1200,
                    "step": 50,
                    "tooltip": "Output histogram height in pixels",
                }),
                "show_grid": ("BOOLEAN", {
                    "default": True,
                    "label_on": "enabled",
                    "label_off": "disabled",
                    "tooltip": "Display grid lines for reference",
                }),
            },
            "optional": {
                "save_images": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Save comparison images to disk",
                }),
                "save_location": ("STRING", {
                    "default": "histograms",
                    "multiline": False,
                    "tooltip": "Output folder path for saved images",
                }),
                "save_metadata": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Embed workflow metadata in PNG files",
                }),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO"
            },
        }
    
    CATEGORY = "image/analysis"
    RETURN_TYPES = ("IMAGE", "IMAGE", "IMAGE", "IMAGE", "IMAGE", "STRING")
    RETURN_NAMES = ("rgb_comparison", "individual_comparison", "luminance_comparison", "hue_comparison", "all_types_grid", "difference_stats")
    FUNCTION = "compare"
    OUTPUT_NODE = True
    
    def compare(self, image_1: torch.Tensor, image_2: torch.Tensor, width: int, height: int, 
                show_grid: bool, save_images: bool = False, save_location: str = "histograms",
                save_metadata: bool = False, prompt=None, extra_pnginfo=None) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, str]:
        """
        Compare histograms of two images side-by-side.
        """
        print(f"[HistogramComparator] Comparing two image histograms - generating all types")
        
        # Convert tensors to numpy - handle 4D and 5D tensors
        if image_1.ndim == 5:
            # 5D: [batch, frames, height, width, channels] - take first batch, first frame
            img1_np = image_1.cpu().numpy()[0, 0]
        elif image_1.ndim == 4:
            # 4D: [batch, height, width, channels] - take first batch
            img1_np = image_1.cpu().numpy()[0]
        else:
            img1_np = image_1.cpu().numpy()
        
        if image_2.ndim == 5:
            # 5D: [batch, frames, height, width, channels] - take first batch, first frame
            img2_np = image_2.cpu().numpy()[0, 0]
        elif image_2.ndim == 4:
            # 4D: [batch, height, width, channels] - take first batch
            img2_np = image_2.cpu().numpy()[0]
        else:
            img2_np = image_2.cpu().numpy()
        
        # Compute histograms
        hist1 = self.histogram_gen.compute_histogram(img1_np, bins=256)
        hist2 = self.histogram_gen.compute_histogram(img2_np, bins=256)
        
        stats1 = self.histogram_gen.compute_statistics(img1_np)
        stats2 = self.histogram_gen.compute_statistics(img2_np)
        
        half_width = width // 2 - 10
        
        # Generate all comparison types
        rgb_comp = self._create_comparison(
            self._tensor_to_pil(self.histogram_gen.draw_histogram_rgb(hist1, half_width, height, show_grid, True, stats1)),
            self._tensor_to_pil(self.histogram_gen.draw_histogram_rgb(hist2, half_width, height, show_grid, True, stats2)),
            width,
            "RGB Histogram Comparison"
        )
        
        individual_comp = self._create_comparison(
            self._tensor_to_pil(self.histogram_gen.draw_histogram_individual(hist1, half_width, height, show_grid, True, stats1)),
            self._tensor_to_pil(self.histogram_gen.draw_histogram_individual(hist2, half_width, height, show_grid, True, stats2)),
            width,
            "Individual Channel Comparison"
        )
        
        luminance_comp = self._create_comparison(
            self._tensor_to_pil(self.histogram_gen.draw_histogram_luminance(hist1, half_width, height, show_grid, True, stats1)),
            self._tensor_to_pil(self.histogram_gen.draw_histogram_luminance(hist2, half_width, height, show_grid, True, stats2)),
            width,
            "Luminance Histogram Comparison"
        )
        
        hue_comp = self._create_comparison(
            self._tensor_to_pil(self.histogram_gen.draw_histogram_hue(hist1, half_width, height, show_grid, True, stats1, hist1.get('hsv'))),
            self._tensor_to_pil(self.histogram_gen.draw_histogram_hue(hist2, half_width, height, show_grid, True, stats2, hist2.get('hsv'))),
            width,
            "Hue Distribution Comparison"
        )
        
        # Create all-types grid (4 rows x 1 column: rows=types)
        all_types_grid = self._create_comparison_grid(
            [rgb_comp, individual_comp, luminance_comp, hue_comp],
            layout="vertical"
        )
        
        # Calculate difference statistics
        differences = self._calculate_differences(stats1, stats2)
        
        # Save if requested
        if save_images:
            self._save_comparison_images(
                [rgb_comp, individual_comp, luminance_comp, hue_comp, all_types_grid],
                ["rgb", "individual", "luminance", "hue", "all_types"],
                save_location, save_metadata, prompt, extra_pnginfo
            )
        
        # Convert PIL images to tensors
        tensors = []
        for pil_img in [rgb_comp, individual_comp, luminance_comp, hue_comp, all_types_grid]:
            img_array = np.array(pil_img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_array).unsqueeze(0)  # Add batch dimension: (h,w,c) -> (1,h,w,c)
            tensors.append(img_tensor)
        
        diff_json = json.dumps(differences, indent=2)
        
        return (*tensors, diff_json)
    
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
    
    def _create_comparison(self, img1: Image.Image, img2: Image.Image, total_width: int, title: str = "") -> Image.Image:
        """Create side-by-side comparison image with title."""
        from PIL import ImageDraw, ImageFont
        
        half_width = total_width // 2 - 10
        height = img1.height
        title_height = 35 if title else 0
        
        comparison = Image.new('RGB', (total_width, height + title_height), color=(20, 20, 20))
        
        # Add title if provided
        if title:
            draw = ImageDraw.Draw(comparison)
            try:
                title_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 14)
            except:
                title_font = None
            draw.text((total_width // 2 - len(title) * 3, 5), title, fill=(200, 200, 200), font=title_font)
            draw.line([(0, 30), (total_width, 30)], fill=(60, 60, 60), width=1)
        
        comparison.paste(img1, (0, title_height))
        comparison.paste(img2, (half_width + 10, title_height))
        
        # Add labels for Image 1 and Image 2
        draw = ImageDraw.Draw(comparison)
        try:
            label_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 11)
        except:
            label_font = None
        draw.text((10, title_height + 5), "Image 1", fill=(150, 200, 150), font=label_font)
        draw.text((half_width, title_height + 5), "Image 2", fill=(150, 200, 150), font=label_font)
        
    def _calculate_differences(self, stats1: dict, stats2: dict) -> dict:
        """Calculate differences between two image statistics."""
        differences = {
            'red': {},
            'green': {},
            'blue': {},
            'luminance': {}
        }
        
        for ch in ['red', 'green', 'blue', 'luminance']:
            for stat in ['min', 'max', 'mean', 'median']:
                val1 = stats1[ch][stat]
                val2 = stats2[ch][stat]
                diff = val2 - val1
                diff_percent = (diff / max(abs(val1), 0.001)) * 100
                
                differences[ch][stat] = {
                    'image1': val1,
                    'image2': val2,
                    'difference': diff,
                    'difference_percent': diff_percent
                }
        
        return differences
    
    def _create_comparison_grid(self, images: List[Image.Image], layout: str = "vertical") -> Image.Image:
        """Combine multiple comparison images into a grid."""
        if layout == "vertical":
            # Stack vertically
            total_width = max(img.width for img in images)
            total_height = sum(img.height for img in images)
            
            grid = Image.new('RGB', (total_width, total_height), color=(40, 40, 40))
            y_offset = 0
            for img in images:
                grid.paste(img, (0, y_offset))
                y_offset += img.height
        else:
            # Stack horizontally
            total_width = sum(img.width for img in images)
            total_height = max(img.height for img in images)
            
            grid = Image.new('RGB', (total_width, total_height), color=(40, 40, 40))
            x_offset = 0
            for img in images:
                grid.paste(img, (x_offset, 0))
                x_offset += img.width
        
        return grid
    
    def _save_comparison_images(self, images: list, names: list, save_location: str, save_metadata: bool, prompt, extra_pnginfo):
        """Save comparison images with optional metadata."""
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Find next available counter
        counter = 0
        while True:
            test_path = os.path.join(save_dir, f"comparison_{counter:05d}_rgb.png")
            if not os.path.exists(test_path):
                break
            counter += 1
        
        # Create metadata if requested
        metadata = None
        if save_metadata and not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for key in extra_pnginfo:
                    metadata.add_text(key, json.dumps(extra_pnginfo[key]))
        
        # Save each image
        for img, name in zip(images, names):
            filename = f"comparison_{counter:05d}_{name}.png"
            filepath = os.path.join(save_dir, filename)
            img.save(filepath, pnginfo=metadata, compress_level=4)
            print(f"[HistogramComparator] Saved: {filename}")


# Node registration
NODE_CLASS_MAPPINGS = {
    "HistogramAnalyzer": HistogramAnalyzer,
    "HistogramComparator": HistogramComparator,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "HistogramAnalyzer": "Histogram Analyzer",
    "HistogramComparator": "Histogram Comparator",
}
