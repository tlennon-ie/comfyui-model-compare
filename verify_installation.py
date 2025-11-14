"""
Installation Verification Script for ComfyUI Model Compare

Run this script to verify that all files are properly installed and
the package can be imported correctly.

Usage:
    python verify_installation.py
"""

import os
import sys
import json
from pathlib import Path


def verify_installation():
    """Verify the installation of comfyui-model-compare."""
    
    print("=" * 70)
    print("ComfyUI Model Compare - Installation Verification")
    print("=" * 70)
    print()
    
    # Get the current directory
    current_dir = Path(__file__).parent
    package_name = current_dir.name
    
    print(f"Package Directory: {current_dir}")
    print(f"Package Name: {package_name}")
    print()
    
    # Check 1: Core Python files
    print("✓ Checking core Python files...")
    core_files = [
        "__init__.py",
        "model_compare_loaders.py",
        "sampler_compare.py",
        "grid_compare.py",
    ]
    
    missing_files = []
    for filename in core_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} (MISSING)")
            missing_files.append(filename)
    
    print()
    
    # Check 2: Documentation files
    print("✓ Checking documentation files...")
    doc_files = [
        "README.md",
        "SETUP.md",
        "TECHNICAL.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "QUICK_REFERENCE.md",
        "PROJECT_SUMMARY.md",
    ]
    
    for filename in doc_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} (MISSING)")
    
    print()
    
    # Check 3: Configuration files
    print("✓ Checking configuration files...")
    config_files = [
        "requirements.txt",
        "node_list.json",
        "LICENSE",
        ".gitignore",
    ]
    
    for filename in config_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} (MISSING)")
    
    print()
    
    # Check 4: Example files
    print("✓ Checking example files...")
    example_files = [
        "example_workflow.json",
    ]
    
    for filename in example_files:
        filepath = current_dir / filename
        if filepath.exists():
            print(f"  ✓ {filename}")
        else:
            print(f"  ✗ {filename} (MISSING)")
    
    print()
    
    # Check 5: Import test
    print("✓ Testing Python imports...")
    try:
        sys.path.insert(0, str(current_dir.parent))
        from model_compare_loaders import (
            ModelCompareLoaders,
            ModelCompareLoadersAdvanced,
            NODE_CLASS_MAPPINGS as LOADER_MAPPINGS,
        )
        print("  ✓ model_compare_loaders imported successfully")
        print(f"    - ModelCompareLoaders")
        print(f"    - ModelCompareLoadersAdvanced")
    except Exception as e:
        print(f"  ✗ Failed to import model_compare_loaders: {e}")
    
    try:
        from sampler_compare import (
            SamplerCompare,
            NODE_CLASS_MAPPINGS as SAMPLER_MAPPINGS,
        )
        print("  ✓ sampler_compare imported successfully")
        print(f"    - SamplerCompare")
    except Exception as e:
        print(f"  ✗ Failed to import sampler_compare: {e}")
    
    try:
        from grid_compare import (
            GridCompare,
            NODE_CLASS_MAPPINGS as GRID_MAPPINGS,
        )
        print("  ✓ grid_compare imported successfully")
        print(f"    - GridCompare")
    except Exception as e:
        print(f"  ✗ Failed to import grid_compare: {e}")
    
    try:
        import __init__ as pkg_init
        print("  ✓ Package __init__ loaded successfully")
        print(f"    - NODE_CLASS_MAPPINGS contains {len(pkg_init.NODE_CLASS_MAPPINGS)} nodes")
        print(f"    - Nodes: {', '.join(pkg_init.NODE_CLASS_MAPPINGS.keys())}")
    except Exception as e:
        print(f"  ✗ Failed to load package init: {e}")
    
    print()
    
    # Check 6: JSON validation
    print("✓ Validating JSON files...")
    json_files = {
        "node_list.json": "ComfyUI Manager metadata",
        "example_workflow.json": "Example workflow",
    }
    
    for filename, description in json_files.items():
        filepath = current_dir / filename
        try:
            with open(filepath, 'r') as f:
                json.load(f)
            print(f"  ✓ {filename} - Valid JSON ({description})")
        except json.JSONDecodeError as e:
            print(f"  ✗ {filename} - Invalid JSON: {e}")
        except FileNotFoundError:
            print(f"  ✗ {filename} - File not found")
    
    print()
    
    # Check 7: Dependencies
    print("✓ Checking Python dependencies...")
    dependencies = {
        "PIL": "Pillow",
        "torch": "PyTorch",
        "numpy": "NumPy",
        "folder_paths": "ComfyUI (built-in)",
        "comfy": "ComfyUI (built-in)",
    }
    
    for module_name, package_name in dependencies.items():
        try:
            __import__(module_name)
            print(f"  ✓ {package_name} ({module_name})")
        except ImportError:
            if package_name.endswith("(built-in)"):
                print(f"  ✗ {package_name} - ComfyUI may not be installed correctly")
            else:
                print(f"  ✗ {package_name} ({module_name}) - Not installed")
    
    print()
    
    # Summary
    print("=" * 70)
    if not missing_files:
        print("✓ Installation verification PASSED")
        print()
        print("Next steps:")
        print("1. Restart ComfyUI server")
        print("2. Hard refresh browser (Ctrl+F5)")
        print("3. Look for Model Compare nodes in the Add Node menu")
        print("4. Load example_workflow.json to test")
    else:
        print("✗ Installation verification FAILED")
        print()
        print("Missing files:")
        for f in missing_files:
            print(f"  - {f}")
        print()
        print("Please download the missing files or reinstall the package")
    
    print("=" * 70)


if __name__ == "__main__":
    verify_installation()
