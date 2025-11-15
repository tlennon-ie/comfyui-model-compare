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

    def _organize_images_by_lora(self, config: Dict[str, Any], pil_images: List[Image.Image], labels: List[str]) -> Dict[str, Any]:
        """
        Organize images into a structure grouped by LoRA and strength.
        Parses labels to extract LoRA names and strength values (labels format: "LoRA_Name(strength)")
        Returns a dict with rows of images, where each row represents one LoRA with multiple strengths.
        """
        if not labels or not pil_images:
            return {
                "rows": [],
                "column_headers": [],
                "num_rows": 0,
                "num_cols": 0,
            }
        
        # Parse labels to extract LoRA names and strengths
        # Label format: "LoRA_Name(strength)" e.g., "Skin 1(0.00)"
        lora_groups = {}  # lora_name -> list of (strength, image, label, image_index)
        strength_values = set()
        
        print(f"[GridCompare] Parsing {len(labels)} labels for grid organization")
        
        for idx, label in enumerate(labels):
            if idx >= len(pil_images):
                break
            
            # Parse label to extract LoRA name and strength
            # Format: "LoRA_Name(strength)"
            if '(' in label and ')' in label:
                try:
                    # Split on the last opening parenthesis to handle LoRA names with numbers
                    last_paren = label.rfind('(')
                    lora_name = label[:last_paren].strip()
                    strength_str = label[last_paren+1:-1].strip()  # Remove '(' and ')'
                    strength = float(strength_str)
                    
                    if lora_name not in lora_groups:
                        lora_groups[lora_name] = []
                    
                    lora_groups[lora_name].append({
                        "strength": strength,
                        "image": pil_images[idx],
                        "label": label,
                        "image_index": idx,
                    })
                    
                    strength_values.add(strength)
                    print(f"  [Label {idx}] LoRA: '{lora_name}' | Strength: {strength:.2f}")
                except (ValueError, IndexError) as e:
                    print(f"  [Label {idx}] Failed to parse '{label}': {e}")
                    continue
            else:
                print(f"  [Label {idx}] Skipping invalid format: '{label}'")
        
        if not lora_groups or not strength_values:
            print(f"[GridCompare] No valid labels parsed!")
            return {
                "rows": [],
                "column_headers": [],
                "num_rows": 0,
                "num_cols": 0,
            }
        
        # Sort strength values for column headers
        sorted_strengths = sorted(list(strength_values))
        print(f"[GridCompare] Found {len(lora_groups)} unique LoRAs with strengths: {sorted_strengths}")
        
        # Organize into rows, maintaining order of first appearance
        rows = []
        lora_order = []  # Track order in which LoRAs first appeared
        
        for idx, label in enumerate(labels):
            if idx >= len(pil_images):
                break
            
            if '(' in label and ')' in label:
                try:
                    last_paren = label.rfind('(')
                    lora_name = label[:last_paren].strip()
                    
                    if lora_name not in lora_order:
                        lora_order.append(lora_name)
                except:
                    continue
        
        # Create rows in the order LoRAs first appeared
        for lora_name in lora_order:
            if lora_name in lora_groups:
                # Sort this LoRA's strengths
                lora_data = sorted(lora_groups[lora_name], key=lambda x: x["strength"])
                rows.append({
                    "lora_name": lora_name,
                    "images": lora_data,
                })
        
        print(f"[GridCompare] Organized grid: {len(rows)} rows × {len(sorted_strengths)} columns")
        
        return {
            "rows": rows,
            "column_headers": sorted_strengths,
            "num_rows": len(rows),
            "num_cols": len(sorted_strengths),
        }

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
        Organizes images by LoRA rows and strength columns with proper axis labels.
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

        # Organize images by LoRA and strength
        organized_data = self._organize_images_by_lora(config, pil_images, label_list)
        
        # Create grid with proper organization
        grid_image = self._create_organized_grid(
            organized_data=organized_data,
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

    def _create_organized_grid(
        self,
        organized_data: Dict[str, Any],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """
        Create a grid image organized by LoRA and strength.
        Rows represent different LoRAs, columns represent different strengths.
        Strength values shown as column headers above, LoRA names as row labels on left.
        """
        rows = organized_data.get("rows", [])
        column_headers = organized_data.get("column_headers", [])
        
        if not rows or not column_headers:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get first image to determine cell dimensions
        first_image = rows[0]["images"][0]["image"] if rows[0]["images"] else None
        if not first_image:
            return Image.new('RGB', (100, 100), color='white')
        
        img_width, img_height = first_image.size
        
        # Calculate layout dimensions
        label_height = font_size + 20
        label_width = 250  # Width for LoRA names on left
        header_height = label_height + gap_size  # Height for strength headers
        title_height = label_height + gap_size if title else 0
        
        num_rows = len(rows)
        num_cols = len(column_headers)
        
        grid_width = label_width + gap_size + num_cols * (img_width + gap_size) + gap_size
        grid_height = title_height + header_height + num_rows * (img_height + gap_size) + gap_size
        
        # Create grid image
        grid_color = self._parse_color("#FFFFFF")
        grid_img = Image.new('RGB', (grid_width, grid_height), color=grid_color)
        draw = ImageDraw.Draw(grid_img)
        font = self._get_font(font_name, font_size)
        label_font = self._get_font(font_name, int(font_size * 0.8))
        header_font = self._get_font(font_name, int(font_size * 0.9))
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)
        
        # Draw title
        current_y = gap_size
        if title:
            title_x = label_width + (num_cols * (img_width + gap_size)) // 2
            draw.text((title_x, current_y), title, fill=text_rgb, font=font, anchor="mm")
            current_y += title_height
        
        # Draw column headers (strength values)
        header_y = current_y
        for col_idx, strength in enumerate(column_headers):
            x = label_width + gap_size + col_idx * (img_width + gap_size) + img_width // 2
            header_text = f"{strength:.2f}"
            draw.text((x, header_y), header_text, fill=text_rgb, font=header_font, anchor="mm")
        
        current_y += header_height
        
        # Draw rows with LoRA labels and images
        for row_idx, row_data in enumerate(rows):
            lora_name = row_data["lora_name"]
            images_data = row_data["images"]
            
            # Draw LoRA name on left
            lora_y = current_y + img_height // 2
            draw.text((gap_size + label_width // 2, lora_y), lora_name, fill=text_rgb, font=label_font, anchor="mm")
            
            # Draw images for this row
            for col_idx, img_data in enumerate(images_data):
                pil_img = img_data["image"]
                
                x = label_width + gap_size + col_idx * (img_width + gap_size)
                y = current_y
                
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
            
            current_y += img_height + gap_size
        
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
