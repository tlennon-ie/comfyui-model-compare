"""
Grid Compare Node
Takes the output images from SamplerCompare and arranges them into
a customizable comparison grid with labels and styling.
"""

import os
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo
from typing import Dict, List, Tuple, Any
import folder_paths
import json
import comfy.cli_args
args = comfy.cli_args.args


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
                "config": ("MODEL_COMPARE_CONFIG",),
                "labels": ("STRING",),
                "save_location": ("STRING", {
                    "default": "model-compare/ComfyUI",
                    "multiline": False,
                    "tooltip": "Output folder path for saving grid",
                }),
                "grid_title": ("STRING", {
                    "default": "Model Comparison Grid",
                    "multiline": False,
                    "tooltip": "Name for the saved grid file",
                }),
                "gap_size": ("INT", {
                    "default": 10,
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "tooltip": "Space between images in pixels",
                }),
                "border_color": ("STRING", {
                    "default": "#000000",
                    "multiline": False,
                    "tooltip": "Hex color for image borders",
                }),
                "border_width": ("INT", {
                    "default": 2,
                    "min": 0,
                    "max": 10,
                    "step": 1,
                    "tooltip": "Border width in pixels",
                }),
                "text_color": ("STRING", {
                    "default": "#000000",
                    "multiline": False,
                    "tooltip": "Hex color for text labels",
                }),
                "font_size": ("INT", {
                    "default": 40,
                    "min": 8,
                    "max": 200,
                    "step": 2,
                    "tooltip": "Label text size in points",
                }),
                "font_name": (fonts, {
                    "default": "default",
                    "tooltip": "Font for text labels",
                }),
                "show_positive_prompt": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Show positive prompt text below each prompt section",
                }),
                "show_negative_prompt": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Show negative prompt text below each prompt section",
                }),
                "save_prompt_grids_separately": ("BOOLEAN", {
                    "default": False,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Save each prompt variation as a separate grid file (useful for many prompts)",
                }),
                "save_individuals": ("BOOLEAN", {
                    "default": True,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Save individual images in addition to grid",
                }),
                "save_metadata": ("BOOLEAN", {
                    "default": True,
                    "label_on": "yes",
                    "label_off": "no",
                    "tooltip": "Embed workflow metadata in PNG files",
                }),
                # Video grid options
                "video_output_mode": (["images_only", "video_only", "both"], {
                    "default": "images_only",
                    "tooltip": "Output mode: images only, video only, or both (for mixed image/video results)"
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
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    CATEGORY = "Model Compare/Grid"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING")
    RETURN_NAMES = ("images", "save_path", "video_path")
    OUTPUT_IS_LIST = (False, False, False)
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

    def _get_unique_values(self, config: Dict[str, Any]) -> Dict[str, List[Any]]:
        """Extract unique values for each dimension from config."""
        # Extract from variations lists to maintain order
        models = []
        for m in config.get("model_variations", []):
            label = m.get("label", "")
            if not label:
                label = m["name"].replace("[Diffusion]", "").strip()
                if label.endswith(".safetensors"): label = label[:-12]
            models.append({"name": m["name"], "label": label})

        vaes = []
        for v in config.get("vae_variations", []):
            if isinstance(v, dict):
                name = v["name"]
                label = v.get("label", "")
                if not label:
                    label = name
                    if label.endswith(".safetensors"): label = label[:-12]
                vaes.append({"name": name, "label": label})
            else:
                # Fallback
                label = v
                if label.endswith(".safetensors"): label = label[:-12]
                vaes.append({"name": v, "label": label})
        
        # Extract CLIPs - handle both single (QWEN) and pair (FLUX) formats
        clips = []
        for c in config.get("clip_variations", []):
            label = c.get("label", "")
            if c.get("type") == "pair":
                name = f"{c['a']}/{c['b']}"
            else:
                name = c.get("model", "Unknown")
            
            if not label:
                label = name
                
            clips.append({"name": name, "label": label, "data": c})
            
        # Extract LoRA Groups and Strengths from combinations
        # We need to scan combinations to find all unique LoRA groups and their max strength counts
        lora_groups = []
        seen_groups = set()
        max_strengths = 0
        
        for combo in config.get("combinations", []):
            # Create a signature for the LoRA group
            names = tuple(combo.get("lora_names", []))
            if names not in seen_groups:
                seen_groups.add(names)
                # Create a display label for the group
                if not names:
                    label = "No LoRA"
                else:
                    # Use display names if available
                    display_names = combo.get("lora_display_names", names)
                    label = " + ".join(display_names)
                
                lora_groups.append({"names": names, "label": label})
            
            # Track max number of strengths (columns)
            strengths = combo.get("lora_strengths", ())
            max_strengths = max(max_strengths, len(strengths) if strengths else 1)

        return {
            "models": models,
            "vaes": vaes,
            "clips": clips,
            "lora_groups": lora_groups,
            "max_strengths": max_strengths
        }

    def _organize_nested_data(self, images: List[Image.Image], config: Dict[str, Any], unique_vals: Dict) -> Dict:
        """
        Organize images into a nested dictionary structure:
        data[clip_idx][group_idx][model_idx][vae_idx][strength_idx] = image
        """
        data = {}
        
        # Map unique values to indices for fast lookup
        model_to_idx = {m["name"]: i for i, m in enumerate(unique_vals["models"])}
        vae_to_idx = {v["name"]: i for i, v in enumerate(unique_vals["vaes"])}
        
        # CLIP mapping is trickier due to dict structure
        # We'll rely on the order in unique_vals["clips"] matching config["clip_variations"]
        # But we need to match the combo's clip_variation to our unique list
        
        combinations = config.get("combinations", [])
        
        for img_idx, combo in enumerate(combinations):
            if img_idx >= len(images):
                break
                
            image = images[img_idx]
            
            # Get indices
            model_name = combo.get("model")
            if model_name not in model_to_idx:
                continue # Should not happen if config is consistent
            m_idx = model_to_idx[model_name]
            
            vae_name = combo.get("vae")
            if vae_name not in vae_to_idx:
                continue
            v_idx = vae_to_idx[vae_name]
            
            # Find CLIP index
            # We compare the combo's clip_variation dict with our extracted clips
            c_idx = -1
            combo_clip = combo.get("clip_variation", {})
            for i, c in enumerate(unique_vals["clips"]):
                # Compare relevant fields
                if c["data"].get("type") == combo_clip.get("type"):
                    if c["data"].get("type") == "pair":
                        if c["data"].get("a") == combo_clip.get("a") and c["data"].get("b") == combo_clip.get("b"):
                            c_idx = i
                            break
                    else:
                        if c["data"].get("model") == combo_clip.get("model"):
                            c_idx = i
                            break
            if c_idx == -1: continue
            
            # Find LoRA Group index
            lora_names = tuple(combo.get("lora_names", []))
            g_idx = -1
            for i, g in enumerate(unique_vals["lora_groups"]):
                if g["names"] == lora_names:
                    g_idx = i
                    break
            if g_idx == -1: continue
            
            if c_idx not in data: data[c_idx] = {}
            if g_idx not in data[c_idx]: data[c_idx][g_idx] = {}
            if m_idx not in data[c_idx][g_idx]: data[c_idx][g_idx][m_idx] = {}
            if v_idx not in data[c_idx][g_idx][m_idx]: data[c_idx][g_idx][m_idx][v_idx] = []
            
            # Store image and its specific strength label
            strengths = combo.get("lora_strengths", ())
            # Generate a short label for the strength column (e.g. "0.1, 1.0")
            if not strengths:
                str_label = "-"
            else:
                str_label = ", ".join([f"{s:.2f}" for s in strengths])
                
            data[c_idx][g_idx][m_idx][v_idx].append({
                "image": image,
                "label": str_label,
                "full_strengths": strengths
            })
            
        return data

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
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
        save_prompt_grids_separately: bool = False,
        save_individuals: bool = False,
        save_metadata: bool = False,
        video_output_mode: str = "images_only",
        video_format: str = "mp4",
        video_codec: str = "libx264",
        video_quality: int = 23,
        prompt=None,
        extra_pnginfo=None,
        **kwargs  # Ignore any optional x_label, y_label, z_label
    ) -> Tuple[torch.Tensor, str, str]:
        """
        Create a comparison grid from images and labels.
        Organizes images by LoRA rows and strength columns with proper axis labels.
        
        For video output, handles multi-frame results and creates video grids.
        """
        print(f"[GridCompare] Creating comparison grid...")
        print(f"  Images shape: {images.shape}")
        print(f"  Labels input: {repr(labels)}")
        print(f"  Video output mode: {video_output_mode}")
        
        # Parse labels - try newline-separated first, then semicolon for backwards compatibility
        if "\n" in labels:
            label_list = [l.strip() for l in labels.split("\n") if l.strip()]
        else:
            label_list = [l.strip() for l in labels.split(";") if l.strip()]
        print(f"  Parsed {len(label_list)} labels")
        
        # Convert ALL images to PIL (needed for video grid)
        all_pil_images = self._tensor_to_pil_list(images)
        print(f"  Converted {len(all_pil_images)} images to PIL")
        
        # For image grid, extract only first frame per combination if we have multi-frame outputs
        combinations = config.get("combinations", [])
        has_frame_counts = any(combo.get("output_frame_count", 1) > 1 for combo in combinations)
        
        if has_frame_counts:
            # Extract first frame from each combination for image grid
            pil_images = []
            img_idx = 0
            for combo in combinations:
                frame_count = combo.get("output_frame_count", 1)
                if img_idx < len(all_pil_images):
                    pil_images.append(all_pil_images[img_idx])  # First frame only
                img_idx += frame_count  # Skip remaining frames
            print(f"  Extracted {len(pil_images)} first-frames for image grid (from {len(all_pil_images)} total)")
        else:
            pil_images = all_pil_images

        # Handle "Save each prompt as separate grid" option
        prompt_variations = config.get("prompt_variations", [])
        
        if save_prompt_grids_separately and len(prompt_variations) > 1 and len(combinations) == len(pil_images):
            print(f"[GridCompare] Creating separate grids for {len(prompt_variations)} prompt variations")
            return self._create_separate_prompt_grids(
                pil_images=pil_images,
                label_list=label_list,
                config=config,
                save_location=save_location,
                grid_title=grid_title,
                gap_size=gap_size,
                border_color=border_color,
                border_width=border_width,
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                show_positive_prompt=show_positive_prompt,
                show_negative_prompt=show_negative_prompt,
                save_individuals=save_individuals,
                save_metadata=save_metadata,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )

        # Check if sampling failed (e.g., "No successful samples" returned)
        if len(pil_images) > 0 and len(label_list) == 1 and label_list[0].lower().startswith("no "):
            print(f"[GridCompare] Sampling failed: {label_list[0]}")
            # Create a simple fallback grid showing error message
            grid_image = self._create_error_grid(
                images=pil_images,
                error_message=label_list[0],
                text_color=text_color,
                font_size=font_size,
                font_name=font_name,
                title=grid_title,
            )
        else:
            if len(pil_images) != len(label_list):
                print(f"[GridCompare] Warning: Image count ({len(pil_images)}) != label count ({len(label_list)})")
                # Pad labels if needed
                while len(label_list) < len(pil_images):
                    label_list.append(f"Image {len(label_list)}")

            # Organize images by LoRA and strength
            organized_data = self._organize_images_by_lora(config, pil_images, label_list)
            
            # Check if we should use the Nested Grid System
            # Use nested grid if we have multiple models, VAEs, or CLIPs AND not in grouped mode
            is_grouped = config.get("is_grouped", False)
            is_nested = (
                len(config.get("model_variations", [])) > 1 or
                len(config.get("vae_variations", [])) > 1 or
                len(config.get("clip_variations", [])) > 1
            ) and not is_grouped
            
            if is_grouped:
                # Grouped mode: simple side-by-side comparison
                # Each model group (Model + VAE + CLIP) is one column
                print(f"[GridCompare] Using Grouped Grid System (side-by-side comparison)")
                grid_image = self._create_grouped_grid(
                    images=pil_images,
                    labels=label_list,
                    config=config,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=grid_title,
                    show_positive_prompt=show_positive_prompt,
                    show_negative_prompt=show_negative_prompt,
                )
            elif is_nested:
                print(f"[GridCompare] Detected complex config, using Nested Grid System")
                grid_image = self._create_nested_grid(
                    images=pil_images,
                    config=config,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=grid_title,
                )
            elif organized_data["num_rows"] == 0 or organized_data["num_cols"] == 0:
                # Fallback to simple grid if label parsing failed
                print(f"[GridCompare] Label parsing failed, creating simple grid")
                grid_image = self._create_simple_grid(
                    images=pil_images,
                    labels=label_list,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=grid_title,
                )
            else:
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
            save_metadata=save_metadata,
            prompt=prompt,
            extra_pnginfo=extra_pnginfo,
        )

        print(f"[GridCompare] Grid saved to: {save_path}")

        # Handle video output if needed
        video_path = ""
        if video_output_mode in ["video_only", "both"]:
            video_path = self._create_video_grid(
                all_pil_images=all_pil_images,
                labels=label_list,
                config=config,
                save_location=save_location,
                grid_title=grid_title,
                video_format=video_format,
                video_codec=video_codec,
                video_quality=video_quality,
                gap_size=gap_size,
                font_size=font_size,
                text_color=text_color,
                border_color=border_color,
                border_width=border_width,
                font_name=font_name,
                show_positive_prompt=show_positive_prompt,
            )

        # Convert PIL back to tensor for output
        output_tensor = self._pil_to_tensor(grid_image)

        return (output_tensor, save_path, video_path)

    @staticmethod
    def _tensor_to_pil_list(images: torch.Tensor) -> List[Image.Image]:
        """Convert image tensor to list of PIL images."""
        images_list = []
        
        # Handle different tensor formats
        # Expected shapes:
        # - 4D: [batch, height, width, channels]
        # - 5D video: [batch, frames, height, width, channels]
        
        # If 5D and frames=1, squeeze it down to 4D
        if images.ndim == 5:
            if images.shape[1] == 1:  # Single frame video
                images = images.squeeze(1)  # Remove frame dimension
            else:
                # Multiple frames - take first frame of each batch
                images = images[:, 0, :, :, :]
        
        for i in range(images.shape[0]):
            img = images[i]
            
            # Handle different tensor formats
            if img.dtype == torch.float32 or img.dtype == torch.float16 or img.dtype == torch.bfloat16:
                # Assume range [0, 1]
                img_np = (img.cpu().numpy() * 255).astype(np.uint8)
            else:
                # Direct conversion for uint8 or other types
                img_np = img.cpu().numpy().astype(np.uint8)

            # Handle different shapes
            if img_np.ndim == 3 and img_np.shape[-1] == 4:
                # RGBA
                pil_img = Image.fromarray(img_np, mode='RGBA')
            elif img_np.ndim == 3 and img_np.shape[-1] == 3:
                # RGB
                pil_img = Image.fromarray(img_np, mode='RGB')
            elif img_np.ndim == 2:
                # Grayscale
                pil_img = Image.fromarray(img_np, mode='L')
            else:
                # Try to squeeze and retry
                img_np_squeezed = img_np.squeeze()
                if img_np_squeezed.ndim == 2:
                    pil_img = Image.fromarray(img_np_squeezed, mode='L')
                else:
                    raise ValueError(f"Cannot convert image with shape {img_np.shape} to PIL")

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

    def _create_error_grid(
        self,
        images: List[Image.Image],
        error_message: str,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """Create a simple grid showing error message when sampling fails."""
        if not images:
            return Image.new('RGB', (400, 100), color='white')
        
        # Use first image as reference size
        img_width, img_height = images[0].size
        
        # Create simple layout
        gap = 10
        header_height = font_size + 20
        
        grid_width = img_width + gap * 2
        grid_height = header_height + img_height + gap * 2
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        font = self._get_font(font_name, font_size)
        text_rgb = self._parse_color(text_color)
        
        # Draw error message
        msg_x = grid_width // 2
        msg_y = header_height // 2
        draw.text((msg_x, msg_y), error_message, fill=text_rgb, font=font, anchor="mm")
        
        # Draw placeholder image
        if images:
            grid_img.paste(images[0], (gap, header_height + gap))
        
        return grid_img

    def _create_separate_prompt_grids(
        self,
        pil_images: List[Image.Image],
        label_list: List[str],
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        show_positive_prompt: bool,
        show_negative_prompt: bool,
        save_individuals: bool,
        save_metadata: bool,
        prompt,
        extra_pnginfo,
    ) -> Tuple[torch.Tensor, str]:
        """
        Create separate grid images for each prompt variation.
        
        Returns the first grid as tensor and comma-separated paths for all grids.
        """
        prompt_variations = config.get("prompt_variations", [])
        combinations = config.get("combinations", [])
        num_model_groups = config.get("num_model_groups", 1)
        
        # Group images by prompt_index
        # Images are organized: [prompt1_model1, prompt1_model2, ..., prompt2_model1, prompt2_model2, ...]
        images_by_prompt: Dict[int, List[Tuple[Image.Image, str]]] = {}
        
        for i, (img, label) in enumerate(zip(pil_images, label_list)):
            if i < len(combinations):
                prompt_idx = combinations[i].get("prompt_index", 1)
            else:
                # Fallback: calculate from position
                prompt_idx = (i // num_model_groups) + 1
            
            if prompt_idx not in images_by_prompt:
                images_by_prompt[prompt_idx] = []
            images_by_prompt[prompt_idx].append((img, label))
        
        all_paths = []
        all_grid_tensors = []
        
        for prompt_idx in sorted(images_by_prompt.keys()):
            img_label_pairs = images_by_prompt[prompt_idx]
            prompt_images = [pair[0] for pair in img_label_pairs]
            prompt_labels = [pair[1] for pair in img_label_pairs]
            
            # Get the prompt text for this variation
            prompt_info = None
            for pv in prompt_variations:
                if pv.get("index") == prompt_idx:
                    prompt_info = pv
                    break
            
            # Create a modified config for this single prompt
            single_prompt_config = config.copy()
            single_prompt_config["prompt_variations"] = [prompt_info] if prompt_info else []
            single_prompt_config["num_model_groups"] = num_model_groups
            
            # Build title with prompt info
            prompt_title = f"{grid_title} - Prompt {prompt_idx}" if grid_title else f"Prompt {prompt_idx}"
            
            print(f"[GridCompare] Creating grid for prompt {prompt_idx} with {len(prompt_images)} images")
            
            # Create the grid for this prompt using grouped layout
            is_grouped = config.get("is_grouped", False)
            
            if is_grouped:
                grid_image = self._create_grouped_grid(
                    images=prompt_images,
                    labels=prompt_labels,
                    config=single_prompt_config,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=prompt_title,
                    show_positive_prompt=show_positive_prompt,
                    show_negative_prompt=show_negative_prompt,
                )
            else:
                # Use simple grid for non-grouped mode
                grid_image = self._create_simple_grid(
                    images=prompt_images,
                    labels=prompt_labels,
                    gap_size=gap_size,
                    border_color=border_color,
                    border_width=border_width,
                    text_color=text_color,
                    font_size=font_size,
                    font_name=font_name,
                    title=prompt_title,
                )
                
                # Add prompt text to bottom only for non-grouped mode (grouped mode already includes it)
                if show_positive_prompt or show_negative_prompt:
                    grid_image = self._add_prompt_text_to_grid(
                        grid_image=grid_image,
                        prompt_info=prompt_info,
                        show_positive=show_positive_prompt,
                        show_negative=show_negative_prompt,
                        text_color=text_color,
                        font_name=font_name,
                        font_size=font_size,
                    )
            
            # Save this grid
            save_title = f"{grid_title}_prompt{prompt_idx}" if grid_title else f"grid_prompt{prompt_idx}"
            save_path = self._save_images(
                grid_image=grid_image,
                individual_images=prompt_images if save_individuals else [],
                save_location=save_location,
                title=save_title,
                save_metadata=save_metadata,
                prompt=prompt,
                extra_pnginfo=extra_pnginfo,
            )
            all_paths.append(save_path)
            all_grid_tensors.append(self._pil_to_tensor(grid_image))
            print(f"[GridCompare] Prompt {prompt_idx} grid saved to: {save_path}")
        
        # Return all grid tensors stacked and all paths
        combined_paths = ", ".join(all_paths)
        print(f"[GridCompare] All {len(all_paths)} prompt grids saved")
        
        # Stack all grid tensors into a batch
        if all_grid_tensors:
            stacked_grids = torch.cat(all_grid_tensors, dim=0)
        else:
            stacked_grids = torch.zeros((1, 64, 64, 3))
        
        return (stacked_grids, combined_paths, "")  # No video path for separate prompt grids yet

    def _add_prompt_text_to_grid(
        self,
        grid_image: Image.Image,
        prompt_info: Dict[str, Any],
        show_positive: bool,
        show_negative: bool,
        text_color: str,
        font_name: str,
        font_size: int,
    ) -> Image.Image:
        """Add prompt text to bottom of grid image, centered and wrapped."""
        if not prompt_info:
            return grid_image
        
        prompt_font = self._get_font(font_name, int(font_size * 0.5))
        text_rgb = self._parse_color(text_color)
        
        # Calculate available width for text (with padding on both sides)
        text_padding = 20
        available_width = grid_image.width - text_padding * 2
        
        # Build wrapped text lines
        lines = []
        if show_positive and prompt_info.get("positive"):
            pos_text = prompt_info["positive"]
            lines.append(("header", "Positive Prompt:"))
            wrapped = self._wrap_text(pos_text, prompt_font, available_width)
            for line in wrapped.split('\n'):
                lines.append(("positive", line))
            lines.append(("spacer", ""))  # Add spacing between positive and negative
        
        if show_negative and prompt_info.get("negative"):
            neg_text = prompt_info["negative"]
            lines.append(("header_neg", "Negative Prompt:"))
            wrapped = self._wrap_text(neg_text, prompt_font, available_width)
            for line in wrapped.split('\n'):
                lines.append(("negative", line))
        
        if not lines:
            return grid_image
        
        # Calculate text height needed
        line_height = int(font_size * 0.6)
        spacer_height = int(font_size * 0.3)
        total_text_height = 0
        for line_type, _ in lines:
            if line_type == "spacer":
                total_text_height += spacer_height
            else:
                total_text_height += line_height
        text_height = total_text_height + text_padding * 2
        
        # Create new image with extra space at bottom
        new_width = grid_image.width
        new_height = grid_image.height + text_height
        new_image = Image.new('RGB', (new_width, new_height), color=(255, 255, 255))
        new_image.paste(grid_image, (0, 0))
        
        # Draw prompt text - centered
        draw = ImageDraw.Draw(new_image)
        y = grid_image.height + text_padding
        center_x = new_width // 2
        
        for line_type, line_text in lines:
            if line_type == "spacer":
                y += spacer_height
                continue
            elif line_type == "header":
                color = (80, 80, 80)  # Gray for headers
            elif line_type == "header_neg":
                color = (150, 50, 50)  # Dark red for negative header
            elif line_type == "negative":
                color = (150, 50, 50)  # Dark red for negative
            else:
                color = text_rgb
            
            # Draw centered text
            draw.text((center_x, y), line_text, fill=color, font=prompt_font, anchor="mt")
            y += line_height
        
        return new_image

    def _create_grouped_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        config: Dict[str, Any],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
        show_positive_prompt: bool = False,
        show_negative_prompt: bool = False,
    ) -> Image.Image:
        """
        Create a grid for grouped comparisons (Model+VAE+CLIP are grouped together).
        
        Layout:
        - Title at top
        - For each prompt variation:
            - Model labels row (one per column)
            - Images row (one per model group)
            - Prompt text row (spanning all columns) if enabled
        
        Columns = Model Groups (Model 1 vs Model 2 vs ...)
        Sections = Prompt variations (each gets its own row of images + optional prompt label)
        """
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get image dimensions from first image
        img_width, img_height = images[0].size
        
        # Determine grid layout
        num_model_groups = config.get("num_model_groups", 1)
        prompt_variations = config.get("prompt_variations", [])
        num_prompts = len(prompt_variations) if prompt_variations else 1
        
        # Columns = model groups
        num_cols = num_model_groups
        
        # Images are organized: [prompt1_model1, prompt1_model2, ..., prompt2_model1, prompt2_model2, ...]
        # Each prompt variation gets num_cols images
        
        print(f"[GridCompare] Grouped grid: {num_prompts} prompt sections × {num_cols} model columns = {num_prompts * num_cols} cells for {len(images)} images")
        
        # Get fonts
        title_font = self._get_font(font_name, font_size)
        label_font = self._get_font(font_name, int(font_size * 0.7))
        prompt_font = self._get_font(font_name, int(font_size * 0.5))
        text_rgb = self._parse_color(text_color)
        border_rgb = self._parse_color(border_color)
        
        # Calculate dimensions
        model_label_height = int(font_size * 1.2)
        title_height = font_size + 30 if title else 0
        
        # Calculate prompt text height (if enabled)
        prompt_text_height = 0
        if show_positive_prompt or show_negative_prompt:
            lines_needed = 0
            if show_positive_prompt:
                lines_needed += 6  # Header + 5 lines for positive prompt text
            if show_negative_prompt:
                lines_needed += 6  # Spacer + Header + 5 lines for negative prompt text
            prompt_text_height = int(font_size * 0.6 * lines_needed) + gap_size
        
        # Calculate cell/grid dimensions
        cell_width = img_width + gap_size
        section_height = model_label_height + img_height + gap_size + prompt_text_height
        
        grid_width = cell_width * num_cols + gap_size
        grid_height = title_height + section_height * num_prompts + gap_size
        
        # Create grid image
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        # Draw title
        current_y = 0
        if title:
            title_x = grid_width // 2
            title_y = title_height // 2
            draw.text((title_x, title_y), title, fill=text_rgb, font=title_font, anchor="mm")
            current_y = title_height
        
        # Draw each prompt section
        for prompt_idx in range(num_prompts):
            section_y = current_y + prompt_idx * section_height
            
            # Get prompt text for this section
            prompt_positive = ""
            prompt_negative = ""
            if prompt_variations and prompt_idx < len(prompt_variations):
                prompt_data = prompt_variations[prompt_idx]
                prompt_positive = prompt_data.get("positive", "")
                prompt_negative = prompt_data.get("negative", "")
            
            # Draw model labels and images for this prompt section
            for col in range(num_cols):
                img_idx = prompt_idx * num_cols + col
                if img_idx >= len(images):
                    continue
                
                x = gap_size + col * cell_width
                
                # Get label for this image (model name)
                label = labels[img_idx] if img_idx < len(labels) else f"Model {col + 1}"
                
                # Draw model label
                label_y = section_y + model_label_height // 2
                # Truncate label if too long
                max_label_width = img_width - 10
                display_label = label
                if label_font:
                    try:
                        while label_font.getbbox(display_label)[2] > max_label_width and len(display_label) > 10:
                            display_label = display_label[:-4] + "..."
                    except:
                        pass
                draw.text((x + img_width // 2, label_y), display_label, fill=text_rgb, font=label_font, anchor="mm")
                
                # Draw image
                img_y = section_y + model_label_height
                img = images[img_idx]
                
                # Resize if needed
                if img.size != (img_width, img_height):
                    img = img.resize((img_width, img_height), Image.LANCZOS)
                
                # Draw border
                if border_width > 0:
                    for i in range(border_width):
                        draw.rectangle(
                            [(x - i, img_y - i), (x + img_width + i, img_y + img_height + i)],
                            outline=border_rgb,
                            width=1,
                        )
                
                grid_img.paste(img, (x, img_y))
            
            # Draw prompt text spanning all columns (if enabled)
            if show_positive_prompt or show_negative_prompt:
                prompt_y = section_y + model_label_height + img_height + gap_size // 2
                prompt_x = gap_size
                prompt_width = grid_width - gap_size * 2
                
                if show_positive_prompt and prompt_positive:
                    # Draw header
                    draw.text((grid_width // 2, prompt_y), "Positive Prompt:", fill=(80, 80, 80), font=prompt_font, anchor="mt")
                    prompt_y += int(font_size * 0.6)
                    # Wrap and draw positive prompt
                    wrapped_pos = self._wrap_text(prompt_positive, prompt_font, prompt_width)
                    for line in wrapped_pos.split('\n'):
                        draw.text((grid_width // 2, prompt_y), line, fill=text_rgb, font=prompt_font, anchor="mt")
                        prompt_y += int(font_size * 0.6)
                
                if show_negative_prompt and prompt_negative:
                    prompt_y += int(font_size * 0.3)  # Add spacer
                    # Draw header
                    draw.text((grid_width // 2, prompt_y), "Negative Prompt:", fill=(150, 50, 50), font=prompt_font, anchor="mt")
                    prompt_y += int(font_size * 0.6)
                    # Wrap and draw negative prompt
                    wrapped_neg = self._wrap_text(prompt_negative, prompt_font, prompt_width)
                    for line in wrapped_neg.split('\n'):
                        draw.text((grid_width // 2, prompt_y), line, fill=(150, 50, 50), font=prompt_font, anchor="mt")
                        prompt_y += int(font_size * 0.6)
        
        return grid_img

    def _wrap_text(self, text: str, font, max_width: int) -> str:
        """Wrap text to fit within max_width."""
        if not font:
            return text
        
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                bbox = font.getbbox(test_line)
                width = bbox[2] - bbox[0]
            except:
                width = len(test_line) * 10
            
            if width <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return '\n'.join(lines) if lines else text

    def _create_simple_grid(
        self,
        images: List[Image.Image],
        labels: List[str],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """Create a simple grid when label parsing fails - just rows of images."""
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        
        # Get image dimensions from first image
        img_width, img_height = images[0].size
        
        # Create a single column grid
        label_height = font_size + 20
        title_height = label_height + gap_size if title else 0
        
        grid_width = img_width + gap_size * 2
        grid_height = title_height + len(images) * (img_height + label_height + gap_size) + gap_size
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        
        font = self._get_font(font_name, font_size)
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)
        
        current_y = gap_size
        
        # Draw title if provided
        if title:
            title_x = grid_width // 2
            draw.text((title_x, current_y), title, fill=text_rgb, font=font, anchor="mm")
            current_y += title_height
        
        # Draw each image with its label
        for idx, (img, label) in enumerate(zip(images, labels)):
            x = gap_size
            y = current_y
            
            # Draw label
            draw.text((x, y), label, fill=text_rgb, font=font)
            y += label_height
            
            # Draw border if specified
            if border_width > 0:
                for i in range(border_width):
                    draw.rectangle(
                        [(x - i, y - i), (x + img_width + i, y + img_height + i)],
                        outline=border_rgb,
                        width=1,
                    )
            
            # Paste image
            grid_img.paste(img, (x, y))
            current_y = y + img_height + gap_size
        
        return grid_img

    def _create_nested_grid(
        self,
        images: List[Image.Image],
        config: Dict[str, Any],
        gap_size: int,
        border_color: str,
        border_width: int,
        text_color: str,
        font_size: int,
        font_name: str,
        title: str = "",
    ) -> Image.Image:
        """
        Create a hierarchical nested grid:
        Cols: Model -> VAE -> Strength
        Rows: CLIP -> LoRA Group
        """
        unique_vals = self._get_unique_values(config)
        data = self._organize_nested_data(images, config, unique_vals)
        
        # --- Calculate Dimensions ---
        
        # 1. Determine cell size (from first image)
        if not images:
            return Image.new('RGB', (100, 100), color='white')
        img_width, img_height = images[0].size
        
        # 2. Determine number of columns per VAE (max variations)
        max_cols_per_vae = 1
        for c_idx in data:
            for g_idx in data[c_idx]:
                for m_idx in data[c_idx][g_idx]:
                    for v_idx in data[c_idx][g_idx][m_idx]:
                        max_cols_per_vae = max(max_cols_per_vae, len(data[c_idx][g_idx][m_idx][v_idx]))
        
        num_models = len(unique_vals["models"])
        num_vaes = len(unique_vals["vaes"])
        
        # Total Grid Columns = Models * VAEs * Max_Strengths
        total_data_cols = num_models * num_vaes * max_cols_per_vae
        
        # 3. Determine Label Widths (Rows)
        label_font = self._get_font(font_name, int(font_size * 0.8))
        
        # CLIP Label Width
        max_clip_width = 0
        for c in unique_vals["clips"]:
            w = len(c["label"]) * 10 # Estimate
            if label_font:
                try: w = label_font.getbbox(c["label"])[2]
                except: pass
            max_clip_width = max(max_clip_width, w)
        clip_label_width = max_clip_width + 40
        
        # LoRA Group Label Width
        max_group_width = 0
        for g in unique_vals["lora_groups"]:
            # Check if we should show this label
            # "The Lora name label on the left should only show the lora's that have variations or have the OR operator"
            # Variations: max_cols_per_vae > 1 (approximation, strictly it's per group)
            # OR operator: len(unique_vals["lora_groups"]) > 1
            show_label = (max_cols_per_vae > 1) or (len(unique_vals["lora_groups"]) > 1)
            if not show_label: continue

            # Wrap text logic estimation
            label_text = g["label"]
            # Simple estimation: assume we wrap at ~20 chars? 
            # Let's just measure the longest word or fixed width
            w = 200 # Minimum width
            if label_font:
                try: w = max(w, label_font.getbbox(label_text)[2])
                except: pass
            # Cap width to avoid huge labels
            w = min(w, 400) 
            max_group_width = max(max_group_width, w)
            
        group_label_width = max_group_width + 40 if max_group_width > 0 else 0
        
        total_label_width = clip_label_width + group_label_width
        
        # 4. Calculate Header Heights
        # "The model header column for each base model should be slightly larger font and bold"
        model_font_size = int(font_size * 1.2)
        model_header_font = self._get_font(font_name, model_font_size)
        header_font = self._get_font(font_name, font_size)
        sub_header_font = self._get_font(font_name, int(font_size * 0.9))
        small_header_font = self._get_font(font_name, int(font_size * 0.7))
        
        model_header_height = model_font_size + 30
        vae_header_height = int(font_size * 0.9) + 20
        
        # "The labels for lora strength should ONLY show for the Lora that has a variation set"
        show_strength_header = max_cols_per_vae > 1
        strength_header_height = (int(font_size * 0.7) + 20) if show_strength_header else 0
        
        total_header_height = model_header_height + vae_header_height + strength_header_height
        
        title_height = (font_size + 30) if title else 0
        
        # 5. Calculate Total Size
        # Rows = CLIPs * LoRA_Groups
        num_rows = len(unique_vals["clips"]) * len(unique_vals["lora_groups"])
        
        # Add extra space for CLIP separators
        clip_separator_height = gap_size * 2
        
        grid_width = total_label_width + total_data_cols * (img_width + gap_size) + gap_size
        grid_height = title_height + total_header_height + num_rows * (img_height + gap_size) + (len(unique_vals["clips"]) - 1) * clip_separator_height + gap_size
        
        # --- Render ---
        
        grid_img = Image.new('RGB', (grid_width, grid_height), color=(255, 255, 255))
        draw = ImageDraw.Draw(grid_img)
        border_rgb = self._parse_color(border_color)
        text_rgb = self._parse_color(text_color)
        
        current_y = gap_size
        
        # Draw Main Title
        if title:
            draw.text((grid_width // 2, current_y), title, fill=text_rgb, font=header_font, anchor="mt")
            current_y += title_height
            
        # --- Draw Headers ---
        
        # Model Headers
        model_width = num_vaes * max_cols_per_vae * (img_width + gap_size)
        for m_i, model_info in enumerate(unique_vals["models"]):
            x_start = total_label_width + gap_size + m_i * model_width
            # Center text in the model block
            center_x = x_start + model_width // 2
            
            # Use custom label
            display_name = model_info["label"]
            
            # Draw Bold (simulate by drawing with offset)
            draw.text((center_x, current_y), display_name, fill=text_rgb, font=model_header_font, anchor="mt")
            draw.text((center_x+1, current_y), display_name, fill=text_rgb, font=model_header_font, anchor="mt")
            
            # Draw separator line (Thick border for models)
            if border_width > 0:
                # Draw line at start of model block (except first one maybe?)
                # "the divide between the first 3 images and 2nd 3 images should have a clear separator"
                line_x = x_start - (gap_size // 2)
                if m_i > 0:
                    draw.line([(line_x, current_y), (line_x, grid_height)], fill=border_rgb, width=border_width * 2)
                
        current_y += model_header_height
        
        # VAE Headers
        vae_width = max_cols_per_vae * (img_width + gap_size)
        for m_i in range(num_models):
            for v_i, vae_info in enumerate(unique_vals["vaes"]):
                # Calculate absolute index
                abs_v_i = m_i * num_vaes + v_i
                x_start = total_label_width + gap_size + abs_v_i * vae_width
                center_x = x_start + vae_width // 2
                
                display_name = vae_info["label"]
                
                draw.text((center_x, current_y), display_name, fill=text_rgb, font=sub_header_font, anchor="mt")
                
                # Draw separator line (Normal width for VAEs)
                if border_width > 0:
                    line_x = x_start - (gap_size // 2)
                    # Don't draw over the model separator
                    if v_i > 0: 
                        draw.line([(line_x, current_y), (line_x, grid_height)], fill=border_rgb, width=1)

        current_y += vae_header_height
        
        # Strength Headers
        if show_strength_header:
            for m_i in range(num_models):
                for v_i in range(num_vaes):
                    for s_i in range(max_cols_per_vae):
                        # Find a label for this column index
                        label = f"Var {s_i+1}"
                        # Try to find a real label from data
                        found = False
                        for c_idx in data:
                            for g_idx in data[c_idx]:
                                if m_i in data[c_idx][g_idx] and v_idx in data[c_idx][g_idx][m_idx]:
                                    items = data[c_idx][g_idx][m_idx][v_idx]
                                    if s_i < len(items):
                                        label = items[s_i]["label"]
                                        found = True
                                        break
                            if found: break
                        
                        abs_col_i = (m_i * num_vaes * max_cols_per_vae) + (v_i * max_cols_per_vae) + s_i
                        x_start = total_label_width + gap_size + abs_col_i * (img_width + gap_size)
                        center_x = x_start + img_width // 2
                        
                        draw.text((center_x, current_y), label, fill=text_rgb, font=small_header_font, anchor="mt")

            current_y += strength_header_height
        
        # --- Draw Rows and Images ---
        
        def draw_multiline_text(draw, text, box, font, fill, anchor="lm"):
            """Helper to draw multiline text centered vertically in box"""
            x, y, w, h = box
            lines = []
            words = text.split()
            current_line = []
            
            # Simple word wrap
            for word in words:
                test_line = ' '.join(current_line + [word])
                if font.getbbox(test_line)[2] <= w:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word) # Word too long, force split
                        current_line = []
            if current_line:
                lines.append(' '.join(current_line))
            
            # Calculate total height
            line_height = font.getbbox("Ay")[3] + 4
            total_text_height = len(lines) * line_height
            
            start_y = y + (h - total_text_height) // 2
            
            for i, line in enumerate(lines):
                draw.text((x, start_y + i * line_height), line, fill=fill, font=font)

        for c_i, clip_info in enumerate(unique_vals["clips"]):
            # Draw CLIP Label Area
            clip_y_start = current_y
            clip_height = len(unique_vals["lora_groups"]) * (img_height + gap_size)
            
            # Draw CLIP Label (Vertical centered in its block)
            # "clearer definition between the clip rows"
            # Draw a background or distinct separator
            if c_i > 0:
                # Draw separator above this CLIP block
                sep_y = clip_y_start - (clip_separator_height // 2)
                draw.line([(0, sep_y), (grid_width, sep_y)], fill=border_rgb, width=border_width * 2)
            
            draw.text((gap_size, clip_y_start + clip_height // 2), clip_info["label"], fill=text_rgb, font=label_font, anchor="lm")
            
            # Separator between CLIP label and LoRA labels
            if border_width > 0:
                 draw.line([(clip_label_width, clip_y_start), (clip_label_width, clip_y_start + clip_height)], fill=border_rgb, width=border_width)
            
            for g_i, group_info in enumerate(unique_vals["lora_groups"]):
                row_y = current_y
                
                # Draw LoRA Group Label
                # Only if we decided to show it
                if group_label_width > 0:
                    # "multiline might be tidier"
                    label_box = (gap_size + clip_label_width + 10, row_y, group_label_width - 20, img_height)
                    draw_multiline_text(draw, group_info["label"], label_box, label_font, text_rgb)
                
                # Draw Images
                for m_i in range(num_models):
                    for v_i in range(num_vaes):
                        # Retrieve images for this cell
                        cell_images = []
                        if c_i in data and g_i in data[c_i]:
                            if m_i in data[c_i][g_i] and v_i in data[c_i][g_i][m_i]:
                                cell_images = data[c_i][g_i][m_i][v_i]
                        
                        for s_i in range(max_cols_per_vae):
                            abs_col_i = (m_i * num_vaes * max_cols_per_vae) + (v_i * max_cols_per_vae) + s_i
                            x = total_label_width + gap_size + abs_col_i * (img_width + gap_size)
                            
                            if s_i < len(cell_images):
                                # Draw Image
                                img = cell_images[s_i]["image"]
                                grid_img.paste(img, (x, row_y))
                                
                                # Border
                                if border_width > 0:
                                    for b in range(border_width):
                                        draw.rectangle(
                                            [(x - b, row_y - b), (x + img_width + b, row_y + img_height + b)],
                                            outline=border_rgb,
                                            width=1,
                                        )
                            else:
                                # Empty cell placeholder?
                                pass
                
                current_y += img_height + gap_size
            
            # Add gap after CLIP block
            current_y += clip_separator_height
                
        return grid_img

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
        label_font = self._get_font(font_name, int(font_size * 0.8))
        
        # Calculate label_width based on longest LoRA name
        max_label_width = 100  # Minimum width
        for row in rows:
            lora_name = row["lora_name"]
            # Estimate text width
            if label_font:
                try:
                    # Get bounding box of text
                    bbox = label_font.getbbox(lora_name)
                    text_width = bbox[2] - bbox[0]
                except:
                    text_width = len(lora_name) * 10
            else:
                # Default font estimate: ~10 pixels per character
                text_width = len(lora_name) * 10
            max_label_width = max(max_label_width, text_width + 40)  # Add padding
        
        label_width = max_label_width
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
            header_text = f"LoRA Strength\n{strength:.2f}"
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
        save_metadata: bool = False,
        prompt=None,
        extra_pnginfo=None,
    ) -> str:
        """Save grid and optionally individual images.
        
        Saves files like ComfyUI standard nodes:
        - Grid: output/{save_location}/{title}_0.png, {title}_1.png, etc.
        - Individuals: output/{save_location}/{title}_image_{idx}_{counter}.png
        """
        
        # Create metadata if requested
        metadata = None
        if save_metadata and not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for key in extra_pnginfo:
                    metadata.add_text(key, json.dumps(extra_pnginfo[key]))
        
        # Create save directory
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Find next available counter for grid file (following ComfyUI pattern)
        counter = 0
        while True:
            grid_path = os.path.join(save_dir, f"{title}_{counter}.png")
            if not os.path.exists(grid_path):
                break
            counter += 1
        
        # Save grid image with metadata
        grid_image.save(grid_path, pnginfo=metadata, compress_level=4)
        print(f"[GridCompare] Saved grid: {grid_path}")
        
        # Save individual images if requested
        if individual_images:
            for idx, img in enumerate(individual_images):
                img_counter = 0
                while True:
                    img_path = os.path.join(save_dir, f"{title}_image_{idx}_{img_counter}.png")
                    if not os.path.exists(img_path):
                        break
                    img_counter += 1
                
                img.save(img_path, pnginfo=metadata, compress_level=4)
            
            print(f"[GridCompare] Saved {len(individual_images)} individual images to {save_dir}")
        
        return save_dir

    def _create_video_grid(
        self,
        all_pil_images: List[Image.Image],
        labels: List[str],
        config: Dict[str, Any],
        save_location: str,
        grid_title: str,
        video_format: str,
        video_codec: str,
        video_quality: int,
        gap_size: int,
        font_size: int,
        text_color: str = "#000000",
        border_color: str = "#000000",
        border_width: int = 2,
        font_name: str = "default",
        show_positive_prompt: bool = False,
    ) -> str:
        """
        Create a video grid from multi-frame outputs.
        
        For video models, each model variation may output multiple frames.
        This method arranges them into a video grid where each cell shows
        the animated output of that model.
        
        Args:
            all_pil_images: List of all PIL images (all frames from all combinations)
        
        Returns:
            Path to the saved video file, or empty string if failed.
        """
        try:
            from .video_utils import create_video_grid, is_video_output, get_ffmpeg_path
        except ImportError:
            print("[GridCompare] video_utils not available, skipping video grid")
            return ""
        
        if get_ffmpeg_path() is None:
            print("[GridCompare] FFmpeg not found, skipping video grid")
            return ""
        
        combinations = config.get("combinations", [])
        model_variations = config.get("model_variations", [])
        
        if not combinations:
            print("[GridCompare] No combinations in config, skipping video grid")
            return ""
        
        print(f"[GridCompare] Creating video grid...")
        print(f"  Total PIL images: {len(all_pil_images)}")
        print(f"  Number of combinations: {len(combinations)}")
        
        # Collect video frames per combination using output_frame_count
        video_frames_list = []
        video_labels = []
        fps_list = []
        
        img_idx = 0
        for combo_idx, combo in enumerate(combinations):
            frame_count = combo.get("output_frame_count", 1)
            combo_frames = []
            
            for _ in range(frame_count):
                if img_idx < len(all_pil_images):
                    combo_frames.append(all_pil_images[img_idx])
                    img_idx += 1
            
            if combo_frames:
                video_frames_list.append(combo_frames)
                
                # Get label
                if combo_idx < len(labels):
                    video_labels.append(labels[combo_idx])
                else:
                    video_labels.append(f"Model {combo_idx + 1}")
                
                # Get FPS from model variation
                model_idx = combo.get("model_index", 0)
                if model_idx < len(model_variations):
                    fps = model_variations[model_idx].get("fps", 24)
                else:
                    fps = 24
                fps_list.append(fps)
                
                print(f"    Combo {combo_idx + 1}: {frame_count} frames at {fps} FPS")
        
        if not video_frames_list:
            print("[GridCompare] No video frames collected, skipping video grid")
            return ""
        
        # Check if we actually have video (multiple frames)
        has_video = any(len(frames) > 1 for frames in video_frames_list)
        if not has_video:
            print("[GridCompare] No multi-frame outputs, skipping video grid (all single frames)")
            return ""
        
        print(f"  Collected {len(video_frames_list)} video sequences")
        for i, frames in enumerate(video_frames_list):
            print(f"    Sequence {i + 1}: {len(frames)} frames at {fps_list[i]} FPS")
        
        # Determine grid layout
        num_videos = len(video_frames_list)
        grid_cols = min(num_videos, config.get("num_model_groups", 2))
        
        # Get cell size from first frame
        if video_frames_list and video_frames_list[0]:
            first_frame = video_frames_list[0][0]
            cell_size = (first_frame.width, first_frame.height)
        else:
            cell_size = (512, 512)
        
        # Create output path
        output_dir = folder_paths.get_output_directory()
        save_dir = os.path.join(output_dir, save_location)
        os.makedirs(save_dir, exist_ok=True)
        
        # Find next counter
        counter = 0
        while True:
            video_path = os.path.join(save_dir, f"{grid_title}_video_{counter}.{video_format}")
            if not os.path.exists(video_path):
                break
            counter += 1
        
        # Remove extension for create_video_grid (it adds it)
        video_path_base = video_path.rsplit('.', 1)[0]
        
        # Get positive prompt for display
        positive_prompt = ""
        if show_positive_prompt:
            prompt_variations = config.get("prompt_variations", [])
            if prompt_variations:
                positive_prompt = prompt_variations[0].get("positive", "")
        
        # Create video grid with styling matching image grid
        success = create_video_grid(
            video_frames_list=video_frames_list,
            labels=video_labels,
            output_path=video_path_base,
            fps_list=fps_list,
            grid_cols=grid_cols,
            cell_size=cell_size,
            padding=gap_size,
            label_height=font_size + 20,
            format=video_format,
            codec=video_codec,
            quality=video_quality,
            font_size=font_size,
            # New styling parameters to match image grid
            text_color=text_color,
            border_color=border_color,
            border_width=border_width,
            font_name=font_name,
            grid_title=grid_title,
            positive_prompt=positive_prompt,
        )
        
        if success:
            print(f"[GridCompare] Video grid saved to: {video_path}")
            return video_path
        else:
            print("[GridCompare] Failed to create video grid")
            return ""

    @classmethod
    def IS_CHANGED(cls, images, config, labels, save_location, grid_title, **kwargs):
        """
        Compute a hash to determine if re-execution is needed.
        """
        import hashlib
        
        # Hash key inputs - add defensive checks for None
        combo_count = len(config.get("combinations", [])) if config else 0
        img_shape = str(images.shape) if hasattr(images, 'shape') else "unknown"
        
        hash_input = f"{combo_count}|{img_shape}|{labels}|{save_location}|{grid_title}"
        
        # Add relevant kwargs
        for key in sorted(kwargs.keys()):
            val = kwargs[key]
            if isinstance(val, (str, int, float, bool)):
                hash_input += f"|{key}:{val}"
        
        return hashlib.md5(hash_input.encode()).hexdigest()


# Node mappings
NODE_CLASS_MAPPINGS = {
    "GridCompare": GridCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "GridCompare": "Grid Compare",
}
