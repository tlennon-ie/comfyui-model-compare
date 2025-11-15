#!/usr/bin/env python3
"""
Test script to verify grid rendering works end-to-end.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
from PIL import Image

# Import the grid compare class by loading it directly
import importlib.util
grid_module_path = os.path.join(os.path.dirname(__file__), 'grid_compare.py')
spec = importlib.util.spec_from_file_location("grid_compare", grid_module_path)
grid_module = importlib.util.module_from_spec(spec)

# Mock folder_paths since we don't need it for this test
class MockFolderPaths:
    @staticmethod
    def get_output_directory():
        return os.path.join(os.path.dirname(__file__), "test_output")

sys.modules['folder_paths'] = MockFolderPaths()

def create_test_image(width=256, height=256, color=(100, 100, 100)):
    """Create a simple test image with text."""
    img = Image.new('RGB', (width, height), color=color)
    return img

def test_grid_rendering():
    """Test the actual grid rendering."""
    spec.loader.exec_module(grid_module)
    GridCompare = grid_module.GridCompare
    
    print("\n" + "="*60)
    print("Testing Grid Rendering: Full End-to-End")
    print("="*60)
    
    config = {
        "combinations": [
            {
                "lora_names": ["Lightning", "Skin 1"],
                "lora_strengths": [1.0, 0.00],
                "lora_display_names": ["Lightning", "Skin 1"],
            },
            {
                "lora_names": ["Lightning", "Skin 1"],
                "lora_strengths": [1.0, 0.75],
                "lora_display_names": ["Lightning", "Skin 1"],
            },
            {
                "lora_names": ["Lightning", "Skin 1"],
                "lora_strengths": [1.0, 1.25],
                "lora_display_names": ["Lightning", "Skin 1"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.1"],
                "lora_strengths": [1.0, 0.00],
                "lora_display_names": ["Lightning", "Skin 1.1"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.1"],
                "lora_strengths": [1.0, 0.75],
                "lora_display_names": ["Lightning", "Skin 1.1"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.1"],
                "lora_strengths": [1.0, 1.25],
                "lora_display_names": ["Lightning", "Skin 1.1"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.2"],
                "lora_strengths": [1.0, 0.00],
                "lora_display_names": ["Lightning", "Skin 1.2 (4000 step)"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.2"],
                "lora_strengths": [1.0, 0.75],
                "lora_display_names": ["Lightning", "Skin 1.2 (4000 step)"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.2"],
                "lora_strengths": [1.0, 1.25],
                "lora_display_names": ["Lightning", "Skin 1.2 (4000 step)"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.2"],
                "lora_strengths": [1.0, 0.00],
                "lora_display_names": ["Lightning", "Skin 1.2 (7000 step)"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.2"],
                "lora_strengths": [1.0, 0.75],
                "lora_display_names": ["Lightning", "Skin 1.2 (7000 step)"],
            },
            {
                "lora_names": ["Lightning", "Skin 1.2"],
                "lora_strengths": [1.0, 1.25],
                "lora_display_names": ["Lightning", "Skin 1.2 (7000 step)"],
            },
        ],
        "lora_combiners": ["AND", "OR"],
    }
    
    # Create test images and labels
    pil_images = []
    labels = []
    
    colors = [
        (255, 100, 100), (100, 255, 100), (100, 100, 255),
        (255, 255, 100), (255, 100, 255), (100, 255, 255),
        (200, 100, 100), (100, 200, 100), (100, 100, 200),
        (200, 200, 100), (200, 100, 200), (100, 200, 200),
    ]
    
    for i in range(12):
        img = create_test_image(color=colors[i])
        pil_images.append(img)
        labels.append(f"Image {i}")
    
    grid_compare = GridCompare()
    
    # Test organizing images
    organized_data = grid_compare._organize_images_by_lora(config, pil_images, labels)
    print(f"\nOrganized: {organized_data['num_rows']} rows × {organized_data['num_cols']} columns")
    
    # Test creating grid
    try:
        grid_image = grid_compare._create_organized_grid(
            organized_data=organized_data,
            gap_size=10,
            border_color="#000000",
            border_width=2,
            text_color="#000000",
            font_size=16,
            font_name="default",
            title="Model Comparison Grid",
        )
        
        print(f"✓ Grid rendered successfully")
        print(f"  Grid size: {grid_image.width} × {grid_image.height} pixels")
        
        # Verify dimensions are reasonable
        expected_width = 250 + 10 + 3 * (256 + 10) + 10  # label_width + gap + 3 cols + gaps
        expected_height_min = 50 + 60 + 4 * (256 + 10) + 10  # title + headers + 4 rows + gaps
        
        if grid_image.width >= expected_width - 50 and grid_image.height >= expected_height_min - 50:
            print(f"✓ Grid dimensions are reasonable")
            print(f"  Expected width ≈ {expected_width}, got {grid_image.width}")
            print(f"  Expected height ≈ {expected_height_min}, got {grid_image.height}")
        else:
            print(f"❌ Grid dimensions seem wrong")
            print(f"  Expected width ≈ {expected_width}, got {grid_image.width}")
            print(f"  Expected height ≈ {expected_height_min}, got {grid_image.height}")
            return False
        
        # Save test image for visual inspection
        output_dir = os.path.join(os.path.dirname(__file__), "test_output")
        os.makedirs(output_dir, exist_ok=True)
        test_path = os.path.join(output_dir, "test_grid.png")
        grid_image.save(test_path)
        print(f"✓ Test grid saved to: {test_path}")
        
        print("\n" + "="*60)
        print("✅ Grid rendering test PASSED!")
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        print(f"❌ Grid rendering failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = test_grid_rendering()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
