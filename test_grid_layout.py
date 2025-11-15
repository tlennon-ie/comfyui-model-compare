#!/usr/bin/env python3
"""
Test script to verify grid layout organization.
Simulates your Lightning + 4-skin test case.
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
    """Create a simple test image."""
    return Image.new('RGB', (width, height), color=color)

def test_grid_layout():
    """Test the semantic grid layout."""
    # Now import after mocking
    spec.loader.exec_module(grid_module)
    GridCompare = grid_module.GridCompare
    
    print("\n" + "="*60)
    print("Testing Grid Layout: Lightning + 4 Skin LoRAs")
    print("="*60)
    
    # Create test config matching your setup:
    # 1 Lightning LoRA (AND, strength 1.0)
    # 4 skin LoRAs (OR, 3 strengths each: 0.00, 0.75, 1.25)
    
    config = {
        "combinations": [
            # Row 1: Skin 1 with different strengths
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
            # Row 2: Skin 1.1 with different strengths
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
            # Row 3: Skin 1.2 (4000 step) with different strengths
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
            # Row 4: Skin 1.2 (7000 step) with different strengths
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
        (255, 100, 100),  # Red
        (100, 255, 100),  # Green
        (100, 100, 255),  # Blue
        (255, 255, 100),  # Yellow
        (255, 100, 255),  # Magenta
        (100, 255, 255),  # Cyan
        (200, 100, 100),  # Dark Red
        (100, 200, 100),  # Dark Green
        (100, 100, 200),  # Dark Blue
        (200, 200, 100),  # Dark Yellow
        (200, 100, 200),  # Dark Magenta
        (100, 200, 200),  # Dark Cyan
    ]
    
    for i in range(12):
        img = create_test_image(color=colors[i])
        pil_images.append(img)
        labels.append(f"Image {i}")
    
    # Test organizing images
    grid_compare = GridCompare()
    organized_data = grid_compare._organize_images_by_lora(config, pil_images, labels)
    
    print("\nOrganized Grid Structure:")
    print(f"  Number of rows: {organized_data['num_rows']}")
    print(f"  Number of columns: {organized_data['num_cols']}")
    print(f"  Column headers (strengths): {organized_data['column_headers']}")
    
    print("\nRow Details:")
    for row_idx, row in enumerate(organized_data['rows']):
        lora_name = row['lora_name']
        num_images = len(row['images'])
        print(f"  Row {row_idx + 1}: {lora_name} ({num_images} images)")
        for img_idx, img_data in enumerate(row['images']):
            strength = img_data['strength']
            print(f"    - Strength {strength:.2f}")
    
    # Verify correct organization
    expected_rows = 4
    expected_cols = 3
    
    success = True
    if organized_data['num_rows'] != expected_rows:
        print(f"\n❌ ERROR: Expected {expected_rows} rows, got {organized_data['num_rows']}")
        success = False
    else:
        print(f"\n✓ Correct number of rows: {expected_rows}")
    
    if organized_data['num_cols'] != expected_cols:
        print(f"❌ ERROR: Expected {expected_cols} columns, got {organized_data['num_cols']}")
        success = False
    else:
        print(f"✓ Correct number of columns: {expected_cols}")
    
    expected_strengths = [0.0, 0.75, 1.25]
    if organized_data['column_headers'] != expected_strengths:
        print(f"❌ ERROR: Expected strengths {expected_strengths}, got {organized_data['column_headers']}")
        success = False
    else:
        print(f"✓ Correct column headers: {expected_strengths}")
    
    expected_lora_names = [
        "Skin 1",
        "Skin 1.1",
        "Skin 1.2 (4000 step)",
        "Skin 1.2 (7000 step)",
    ]
    actual_lora_names = [row['lora_name'] for row in organized_data['rows']]
    if actual_lora_names != expected_lora_names:
        print(f"❌ ERROR: Expected LoRA names {expected_lora_names}")
        print(f"         Got {actual_lora_names}")
        success = False
    else:
        print(f"✓ Correct LoRA names: {expected_lora_names}")
    
    if success:
        print("\n" + "="*60)
        print("✅ All tests PASSED! Grid layout is correct.")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("❌ Some tests FAILED. See errors above.")
        print("="*60 + "\n")
    
    return success

if __name__ == "__main__":
    try:
        success = test_grid_layout()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
