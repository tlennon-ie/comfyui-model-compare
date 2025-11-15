#!/usr/bin/env python3
"""
Final verification test - simulates exact user scenario with 16 images.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

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

def create_test_image_with_text(width=256, height=256, text="", bg_color=(100, 100, 100)):
    """Create a test image with text label."""
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)
    # Draw text in center
    draw.text((width//2, height//2), text, fill=(255, 255, 255), anchor="mm")
    return img

def test_actual_user_scenario():
    """Test the exact user scenario: 4 LoRAs × 4 strengths = 16 images."""
    spec.loader.exec_module(grid_module)
    GridCompare = grid_module.GridCompare
    
    print("\n" + "="*70)
    print("FINAL VERIFICATION: User's Actual 16-Image Scenario")
    print("="*70)
    
    # Exact labels from user's setup
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
    
    # Create test images with labels
    pil_images = []
    colors = [
        (200, 50, 50), (200, 100, 50), (200, 150, 50), (200, 200, 50),  # Reds
        (50, 200, 50), (100, 200, 50), (150, 200, 50), (200, 200, 50),  # Greens
        (50, 50, 200), (100, 100, 200), (150, 150, 200), (200, 200, 200),  # Blues
        (200, 50, 200), (200, 100, 200), (200, 150, 200), (200, 200, 255),  # Magentas
    ]
    
    for i, label in enumerate(labels):
        # Extract LoRA name for label
        lora_part = label.split('(')[0].strip()
        img = create_test_image_with_text(256, 256, text=f"#{i}", bg_color=colors[i])
        pil_images.append(img)
    
    grid_compare = GridCompare()
    
    # Test organizing images
    organized_data = grid_compare._organize_images_by_lora({}, pil_images, labels)
    
    print(f"\n✓ Grid Organization:")
    print(f"  Rows: {organized_data['num_rows']} (LoRAs)")
    print(f"  Columns: {organized_data['num_cols']} (Strength values)")
    print(f"  Column headers: {organized_data['column_headers']}")
    
    print(f"\n✓ Row Details:")
    for row_idx, row in enumerate(organized_data['rows'], 1):
        lora_name = row['lora_name']
        num_images = len(row['images'])
        strengths = [f"{img['strength']:.2f}" for img in row['images']]
        print(f"  Row {row_idx}: '{lora_name}' → {num_images} images with strengths {strengths}")
    
    # Validation
    print(f"\n" + "="*70)
    print("VALIDATION RESULTS:")
    print("="*70)
    
    success = True
    
    # Check 1: 4 rows (one per LoRA)
    if organized_data['num_rows'] == 4:
        print("✅ Correct number of rows (4)")
    else:
        print(f"❌ Wrong number of rows: {organized_data['num_rows']} (expected 4)")
        success = False
    
    # Check 2: 4 columns (one per strength)
    if organized_data['num_cols'] == 4:
        print("✅ Correct number of columns (4)")
    else:
        print(f"❌ Wrong number of columns: {organized_data['num_cols']} (expected 4)")
        success = False
    
    # Check 3: Correct strength headers
    expected_strengths = [0.0, 0.75, 1.25, 1.5]
    if organized_data['column_headers'] == expected_strengths:
        print(f"✅ Correct strength headers: {expected_strengths}")
    else:
        print(f"❌ Wrong strength headers: {organized_data['column_headers']} (expected {expected_strengths})")
        success = False
    
    # Check 4: Correct LoRA names in order
    expected_loras = ['Skin 1', 'Skin 1.1', 'Skin 1.2 (4000 step)', 'Skin 1.2 (7000 step)']
    actual_loras = [row['lora_name'] for row in organized_data['rows']]
    if actual_loras == expected_loras:
        print(f"✅ Correct LoRA names (no Lightning LoRA)")
    else:
        print(f"❌ Wrong LoRA names: {actual_loras}")
        print(f"   Expected: {expected_loras}")
        success = False
    
    # Check 5: Each row has 4 images
    all_correct = True
    for row_idx, row in enumerate(organized_data['rows'], 1):
        if len(row['images']) == 4:
            print(f"✅ Row {row_idx} has 4 images")
        else:
            print(f"❌ Row {row_idx} has {len(row['images'])} images (expected 4)")
            all_correct = False
            success = False
    
    # Test creating actual grid image
    print(f"\n" + "="*70)
    print("GRID RENDERING:")
    print("="*70)
    
    try:
        grid_image = grid_compare._create_organized_grid(
            organized_data=organized_data,
            gap_size=15,
            border_color="#000000",
            border_width=2,
            text_color="#000000",
            font_size=18,
            font_name="default",
            title="Model Comparison: Lightning + 4 Skin LoRAs",
        )
        
        print(f"✅ Grid rendered successfully")
        print(f"   Dimensions: {grid_image.width} × {grid_image.height} pixels")
        
        # Save the grid
        output_dir = os.path.join(os.path.dirname(__file__), "test_output")
        os.makedirs(output_dir, exist_ok=True)
        grid_path = os.path.join(output_dir, "final_verification_grid.png")
        grid_image.save(grid_path)
        print(f"✅ Grid saved to: {grid_path}")
        
    except Exception as e:
        print(f"❌ Grid rendering failed: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    # Final result
    print(f"\n" + "="*70)
    if success:
        print("✅ FINAL VERIFICATION PASSED - Ready for production!")
        print("="*70 + "\n")
    else:
        print("❌ FINAL VERIFICATION FAILED - See errors above")
        print("="*70 + "\n")
    
    return success

if __name__ == "__main__":
    try:
        success = test_actual_user_scenario()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
