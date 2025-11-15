"""
Grid Compare Node
Takes the output images from SamplerCompare and arranges them into
a customizable comparison grid with labels and styling.
"""

import os
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Dict, List, Tuple, Any
import folder_paths


class GridCompare:
    """
    Create a comparison grid from sampled images.
    Arranges images based on model combinations and adds labels.
    """

    @classmethod
    def INPUT_TYPES(cls):
        # Get available fonts from system
        fonts = ["default"]
        font_dir = "C:\\Windows\\Fonts" if os.name == 'nt' else "/usr/share/fonts"
        if os.path.exists(font_dir):
            try:
                fonts.extend([f for f in os.listdir(font_dir) if f.endswith('.ttf')])
            except:
                pass

        return {
            "required": {
                "images": ("IMAGE",),
                "labels": ("STRING",),
                "config": ("MODEL_COMPARE_CONFIG",),
                "save_location": ("STRING", {
                    "default": "model-compare/ComfyUI",
                    "multiline": False,
                }),
                "grid_title": ("STRING", {
                    "default": "Model Comparison Grid",
                    "multiline": False,
                }),
                "gap_size": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                }),
                "border_color": ("STRING", {
                    "default": "#000000",
                    "multiline": False,
                    "tooltip": "Hex color for borders (e.g., #000000 for black)",
                }),
                "border_width": ("INT", {
                    "default": 2,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                }),
                "text_color": ("STRING", {
                    "default": "#FFFFFF",
                    "multiline": False,
                    "tooltip": "Hex color for text labels",
                }),
                "font_size": ("INT", {
                    "default": 48,
                    "min": 8,
                    "max": 200,
                    "step": 2,
                }),
                "font_name": (fonts, {
                    "default": "default",
                }),
                "save_individuals": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                }),
            },
            "optional": {},
        }

    CATEGORY = "image"
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("grid_image", "save_path")
    FUNCTION = "create_grid"
    OUTPUT_NODE = True
    
    def _detect_varying_parameters(self, config: Dict[str, Any]) -> Tuple[int, int]:
        """
        Analyze the config to determine grid dimensions based on AND/OR logic.
        Rows = number of OR groups (one row per OR-separated LoRA)
        Cols = number of strength variations
        """
        if "combinations" not in config or not config["combinations"]:
            return 1, 1
        
        combinations = config["combinations"]
        num_combinations = len(combinations)
        
        # Get LoRA combiners to determine grid rows
        lora_combiners = config.get('lora_combiners', [])
        if not lora_combiners:
            # No combiners info, use square-ish layout
            cols = max(1, int(num_combinations ** 0.5))
            rows = (num_combinations + cols - 1) // cols
            return rows, cols
        
        # Count OR operators to determine number of rows
        # OR separates LoRA groups, so row count = number of OR groups
        or_count = sum(1 for op in lora_combiners if op == 'OR')
        rows = or_count + 1  # OR count + 1 = number of groups/rows
        
        # Columns = combinations per row
        cols = num_combinations // max(1, rows) if rows > 0 else num_combinations
        
        return rows, cols

    def create_grid(
        self,
        images: torch.Tensor,
        labels: str,
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        save_individuals: bool,
        **kwargs  # Ignore any optional x_label, y_label, z_label
    ) -> Tuple[torch.Tensor, str]:
        """
        Create a comparison grid from images and labels.
        Arranges by LoRA strength (columns) and LoRA names (rows).
        """
        print(f"[GridCompare] Creating comparison grid...")
        print(f"  Images shape: {images.shape}")
        print(f"  Labels input: {repr(labels)}")
        
        # Parse labels - they come as semicolon-separated from sampler
        label_list = [l.strip() for l in labels.split(";") if l.strip()]
        print(f"  Parsed {len(label_list)} labels")
        
        # Convert images to PIL
        pil_images = self._tensor_to_pil_list(images)
        print(f"  Converted {len(pil_images)} images to PIL")

        if len(pil_images) != len(label_list):
            print(f"[GridCompare] Warning: Image count ({len(pil_images)}) != label count ({len(label_list)})")
            # Pad labels if needed
            while len(label_list) < len(pil_images):
                label_list.append(f"Image {len(label_list)}")

        # Determine grid layout based on which parameters vary
        rows, cols = self._detect_varying_parameters(config)
        
        print(f"[GridCompare] Grid layout: {rows} rows x {cols} columns ({len(pil_images)} images)")

        # Create grid
        grid_image = self._create_grid_image(
            pil_images=pil_images,
            labels=label_list,
            rows=rows,
            cols=cols,
            gap_size=gap_size,
            border_color=border_color,
            border_width=border_width,
            text_color=text_color,
            font_size=font_size,
            font_name=font_name,
            title=grid_title,
        )

        # Save images
        save_path = self._save_images(
            grid_image=grid_image,
            individual_images=pil_images if save_individuals else [],
            save_location=save_location,
            title=grid_title,
        )

        print(f"[GridCompare] Grid saved to: {save_path}")

        # Convert PIL back to tensor for output
        output_tensor = self._pil_to_tensor(grid_image)

        return (output_tensor, save_path)

    @staticmethod
    def _tensor_to_pil_list(images: torch.Tensor) -> List[Image.Image]:
        """Convert image tensor to list of PIL images."""
        images_list = []
        
        for i in range(images.shape[0]):
            img = images[i]
            
            # Handle different tensor formats
            if img.dtype == torch.float32:
                # Assume range [0, 1]
                img_np = (img.numpy() * 255).astype(np.uint8)
            else:
                # Direct conversion for uint8 or other types
                img_np = img.numpy().astype(np.uint8)

            # Handle different shapes
            if img_np.shape[-1] == 4:
                # RGBA
                pil_img = Image.fromarray(img_np, mode='RGBA')
            elif img_np.shape[-1] == 3:
                # RGB
                pil_img = Image.fromarray(img_np, mode='RGB')
            else:
                # Grayscale
                pil_img = Image.fromarray(img_np.squeeze(), mode='L')

            images_list.append(pil_img)

        return images_list

    @staticmethod
    def _pil_to_tensor(pil_image: Image.Image) -> torch.Tensor:
        """Convert PIL image to tensor."""
        img_np = np.array(pil_image).astype(np.float32) / 255.0
        if img_np.ndim == 2:
            img_np = np.stack([img_np] * 3, axis=-1)
        img_tensor = torch.from_numpy(img_np)[None, :]
        return img_tensor

    @staticmethod
    def _parse_color(color_str: str) -> Tuple[int, int, int]:
        """Parse hex color string to RGB tuple."""
        color_str = color_str.lstrip('#')
        if len(color_str) == 6:
            return tuple(int(color_str[i:i+2], 16) for i in (0, 2, 4))
        else:
            return (0, 0, 0)  # Default to black

    @staticmethod
    def _get_font(font_name: str, font_size: int):
        """Load font from system. Returns None if default should be used."""
        if font_name == "default":
            return None  # Use PIL default font
        
        try:
            # Windows system fonts
            if os.name == 'nt':
                font_path = f"C:\\Windows\\Fonts\\{font_name}"
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, font_size)
            
            # Linux system fonts
            linux_paths = [
                f"/usr/share/fonts/truetype/dejavu/{font_name}",
                f"/usr/share/fonts/truetype/{font_name}",
                f"/usr/share/fonts/{font_name}",
            ]
            for font_path in linux_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, font_size)
            
            # Try direct path
            if os.path.exists(font_name):
                return ImageFont.truetype(font_name, font_size)
            
            # If no font found, use default
            return None
        except Exception as e:
            print(f"[GridCompare] Font loading failed: {e}, using default")
            return None

    def _create_grid_image(
        self,
        pil_images: List[Image.Image],
        labels: List[str],
        rows: int,
        cols: int,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """Create a grid image from PIL images."""

        if not pil_images:
            return Image.new('RGB', (100, 100), color='white')

        # Get image dimensions
        img_width, img_height = pil_images[0].size

        # Calculate grid dimensions
        label_height = font_size + 20
        label_width = 200
        
        grid_width = cols * (img_width + gap_size) + gap_size + label_width
        grid_height = rows * (img_height + gap_size) + gap_size + label_height * 2

        if title:
            grid_height += label_height

        # Create grid image
        grid_color = self._parse_color("#FFFFFF")
        grid_img = Image.new('RGB', (grid_width, grid_height), color=grid_color)
        draw = ImageDraw.Draw(grid_img)
        font = self._get_font(font_name, font_size)
        label_font = self._get_font(font_name, int(font_size * 0.8))
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)

        # Draw title
        current_y = gap_size
        if title:
            draw.text((grid_width // 2, current_y), title, fill=text_rgb, font=font, anchor="mm")
            current_y += label_height

        # Draw images and labels
        current_y = current_y + label_height + gap_size
        for idx, pil_img in enumerate(pil_images):
            row = idx // cols
            col = idx % cols

            x = label_width + gap_size + col * (img_width + gap_size)
            y = current_y + row * (img_height + gap_size)

            # Draw border
            if border_width > 0:
                for i in range(border_width):
                    draw.rectangle(
                        [(x - i, y - i), (x + img_width + i, y + img_height + i)],
                        outline=border_rgb,
                        width=1,
                    )

            # Paste image
            grid_img.paste(pil_img, (x, y))

            # Draw label below image
            if idx < len(labels):
                label_text = labels[idx]
                # Wrap long text
                max_width = img_width
                wrapped_lines = []
                for line in label_text.split('\n'):
                    while line:
                        # Try to fit as much as possible
                        wrapped_lines.append(line[:30])  # Limit to 30 chars per line
                        line = line[30:]
                
                # Draw each line of the label
                for line_idx, line in enumerate(wrapped_lines[:2]):  # Limit to 2 lines
                    label_y = y + img_height + gap_size // 2 + line_idx * (font_size // 2)
                    draw.text(
                        (x + img_width // 2, label_y),
                        line,
                        fill=text_rgb,
                        font=label_font,
                        anchor="mm",
                    )
                print(f"[GridCompare] Drew label for image {idx}: {label_text[:50]}")

        return grid_img

    @staticmethod
    def _save_images(
        grid_image: Image.Image,
        individual_images: List[Image.Image],
        save_location: str,
        title: str,
    ) -> str:
        """Save grid and optionally individual images."""
        
        # Create save directory
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)

        # Create a subdirectory for this comparison
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        comparison_dir = os.path.join(save_dir, f"{title}_{timestamp}")
        os.makedirs(comparison_dir, exist_ok=True)

        # Save grid image
        grid_path = os.path.join(comparison_dir, "grid.png")
        grid_image.save(grid_path, quality=95)
        print(f"[GridCompare] Saved grid: {grid_path}")

        # Save individual images if requested
        if individual_images:
            individual_dir = os.path.join(comparison_dir, "individual")
            os.makedirs(individual_dir, exist_ok=True)
            
            for idx, img in enumerate(individual_images):
                img_path = os.path.join(individual_dir, f"image_{idx:04d}.png")
                img.save(img_path, quality=95)
            
            print(f"[GridCompare] Saved {len(individual_images)} individual images")

        return comparison_dir


# Node mappings
NODE_CLASS_MAPPINGS = {
    "GridCompare": GridCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GridCompare": "Grid Compare",
}
