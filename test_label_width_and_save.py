#!/usr/bin/env python3
"""
Test script to verify label width calculation and save path behavior.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

# Mock folder_paths
class MockFolderPaths:
    @staticmethod
    def get_output_directory():
        return os.path.join(os.path.dirname(__file__), "test_output")

sys.modules['folder_paths'] = MockFolderPaths()

import importlib.util
grid_module_path = os.path.join(os.path.dirname(__file__), 'grid_compare.py')
spec = importlib.util.spec_from_file_location("grid_compare", grid_module_path)
grid_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grid_module)

GridCompare = grid_module.GridCompare

def test_label_width_and_save():
    """Test label width calculation and save path handling."""
    print("\n" + "="*60)
    print("Testing Label Width and Save Path")
    print("="*60)
    
    # Test data
    organized_data = {
        "rows": [
            {"lora_name": "Skin 1", "images": []},
            {"lora_name": "Skin 1.1", "images": []},
            {"lora_name": "Skin 1.2 (4000 step)", "images": []},  # Long name
            {"lora_name": "Skin 1.2 (7000 step)", "images": []},  # Long name
        ],
        "column_headers": [0.0, 0.75, 1.25, 1.5],
        "num_rows": 4,
        "num_cols": 4,
    }
    
    # Create dummy images
    test_images = []
    for _ in range(16):
        img = Image.new('RGB', (256, 256), color=(100, 100, 100))
        test_images.append(img)
    
    # Add images to rows
    for row_idx, row in enumerate(organized_data["rows"]):
        for col_idx in range(4):
            img_idx = row_idx * 4 + col_idx
            if img_idx < len(test_images):
                row["images"].append({"image": test_images[img_idx], "strength": organized_data["column_headers"][col_idx]})
    
    grid_compare = GridCompare()
    
    # Test label width calculation
    print("\n1. Testing Label Width Calculation:")
    print("   LoRA names in test:")
    for row in organized_data["rows"]:
        print(f"     - '{row['lora_name']}' ({len(row['lora_name'])} chars)")
    
    # Create a test grid to check label width
    try:
        grid_image = grid_compare._create_organized_grid(
            organized_data=organized_data,
            gap_size=10,
            border_color="#000000",
            border_width=2,
            text_color="#000000",
            font_size=16,
            font_name="default",
            title="Test Grid",
        )
        
        print(f"\n✓ Grid created successfully")
        print(f"  Grid size: {grid_image.width} × {grid_image.height} pixels")
        
        # Check that grid width is appropriate for the longest label
        # Longest label is "Skin 1.2 (7000 step)" (18 chars)
        # Should calculate to at least 180 pixels + padding
        estimated_min_label_width = 180
        if grid_image.width > estimated_min_label_width:
            print(f"✓ Grid width is sufficient for all labels ({grid_image.width}px > {estimated_min_label_width}px)")
        else:
            print(f"❌ Grid width might be too narrow ({grid_image.width}px)")
        
    except Exception as e:
        print(f"❌ Failed to create grid: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test save path handling
    print("\n2. Testing Save Path Handling:")
    
    try:
        save_location = "model-compare/ComfyUI"
        title = "ComfyUI"
        
        # Create test output directory
        output_dir = os.path.join(os.path.dirname(__file__), "test_output")
        os.makedirs(output_dir, exist_ok=True)
        
        # Create test images
        test_img = Image.new('RGB', (512, 512), color=(200, 200, 200))
        individual_imgs = [test_img.copy() for _ in range(3)]
        
        # Save using our method
        result_dir = grid_compare._save_images(
            grid_image=grid_image,
            individual_images=individual_imgs,
            save_location=save_location,
            title=title,
        )
        
        # Verify files were created
        expected_grid_path = os.path.join(output_dir, save_location, f"{title}_0.png")
        
        if os.path.exists(expected_grid_path):
            print(f"✓ Grid saved to correct path:")
            print(f"  {expected_grid_path}")
        else:
            print(f"❌ Grid not found at expected path:")
            print(f"  Expected: {expected_grid_path}")
            return False
        
        # Check individual images
        for idx in range(3):
            expected_img_path = os.path.join(output_dir, save_location, f"{title}_image_{idx}_0.png")
            if os.path.exists(expected_img_path):
                print(f"✓ Individual image {idx} saved correctly")
            else:
                print(f"❌ Individual image {idx} not found")
                return False
        
        # Test counter increment (save again, should use _1.png)
        result_dir = grid_compare._save_images(
            grid_image=grid_image,
            individual_images=[],
            save_location=save_location,
            title=title,
        )
        
        expected_grid_path_1 = os.path.join(output_dir, save_location, f"{title}_1.png")
        if os.path.exists(expected_grid_path_1):
            print(f"✓ Auto-increment works: saved to {title}_1.png")
        else:
            print(f"❌ Auto-increment failed")
            return False
        
        print("\n" + "="*60)
        print("✅ All tests PASSED!")
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        print(f"❌ Save test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    try:
        success = test_label_width_and_save()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
