#!/usr/bin/env python3
"""
Test script to verify grid layout with actual label format from samplers.
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

def test_grid_layout_with_actual_labels():
    """Test the grid layout with actual sampler-generated labels."""
    spec.loader.exec_module(grid_module)
    GridCompare = grid_module.GridCompare
    
    print("\n" + "="*60)
    print("Testing Grid Layout: Actual Label Format")
    print("="*60)
    
    # Your actual labels from the sampler output
    labels = [
        "Skin 1(0.00)",
        "Skin 1(0.75)",
        "Skin 1(1.25)",
        "Skin 1(1.50)",
        "Skin 1.1(0.00)",
        "Skin 1.1(0.75)",
        "Skin 1.1(1.25)",
        "Skin 1.1(1.50)",
        "Skin 1.2 (4000 step)(0.00)",
        "Skin 1.2 (4000 step)(0.75)",
        "Skin 1.2 (4000 step)(1.25)",
        "Skin 1.2 (4000 step)(1.50)",
        "Skin 1.2 (7000 step)(0.00)",
        "Skin 1.2 (7000 step)(0.75)",
        "Skin 1.2 (7000 step)(1.25)",
        "Skin 1.2 (7000 step)(1.50)",
    ]
    
    # Create test images
    pil_images = []
    colors = [
        (255, 100, 100), (100, 255, 100), (100, 100, 255), (255, 255, 100),
        (255, 100, 255), (100, 255, 255), (200, 100, 100), (100, 200, 100),
        (100, 100, 200), (200, 200, 100), (200, 100, 200), (100, 200, 200),
        (255, 150, 100), (150, 255, 100), (150, 100, 255), (255, 255, 150),
    ]
    
    for i in range(16):
        img = create_test_image(color=colors[i])
        pil_images.append(img)
    
    # Empty config (not used anymore)
    config = {"combinations": []}
    
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
        print(f"  Row {row_idx + 1}: '{lora_name}' ({num_images} images)")
        for img_idx, img_data in enumerate(row['images']):
            strength = img_data['strength']
            print(f"    [{img_idx}] Strength {strength:.2f}")
    
    # Verify correct organization
    expected_rows = 4
    expected_cols = 4
    expected_strengths = [0.0, 0.75, 1.25, 1.50]
    expected_lora_names = [
        "Skin 1",
        "Skin 1.1",
        "Skin 1.2 (4000 step)",
        "Skin 1.2 (7000 step)",
    ]
    
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
    
    if organized_data['column_headers'] != expected_strengths:
        print(f"❌ ERROR: Expected strengths {expected_strengths}, got {organized_data['column_headers']}")
        success = False
    else:
        print(f"✓ Correct column headers: {expected_strengths}")
    
    actual_lora_names = [row['lora_name'] for row in organized_data['rows']]
    if actual_lora_names != expected_lora_names:
        print(f"❌ ERROR: Expected LoRA names {expected_lora_names}")
        print(f"         Got {actual_lora_names}")
        success = False
    else:
        print(f"✓ Correct LoRA names: {expected_lora_names}")
    
    # Check that each row has the correct number of images
    for row_idx, row in enumerate(organized_data['rows']):
        if len(row['images']) != expected_cols:
            print(f"❌ ERROR: Row {row_idx} has {len(row['images'])} images, expected {expected_cols}")
            success = False
    
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
        success = test_grid_layout_with_actual_labels()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
