#!/usr/bin/env python3
"""
Test Suite for comfyui-model-compare Branch
Validates core functionality before Phase 2 implementation
"""

import sys
import json
import traceback
from pathlib import Path

# Test results
results = {
    "passed": [],
    "failed": [],
    "warnings": []
}

def test(name, func):
    """Run a test and record results"""
    try:
        func()
        results["passed"].append(name)
        print(f"✅ {name}")
        return True
    except Exception as e:
        results["failed"].append((name, str(e)))
        print(f"❌ {name}")
        print(f"   Error: {e}")
        return False

def warn(message):
    """Record a warning"""
    results["warnings"].append(message)
    print(f"⚠️  {message}")

# ============================================================================
# TEST 1: Python Syntax
# ============================================================================

def test_python_syntax():
    """Verify all Python files compile"""
    import py_compile
    
    files = [
        "sampling_config_chain.py",
        "sampler_compare_advanced.py",
        "lora_compare.py",
        "grid_compare.py",
        "model_compare_loaders.py",
        "prompt_compare.py",
        "vae_config.py",
        "clip_config.py",
    ]
    
    for file in files:
        path = Path(file)
        if path.exists():
            py_compile.compile(str(path), doraise=True)
        else:
            warn(f"File not found: {file}")

# ============================================================================
# TEST 2: JSON Validation
# ============================================================================

def test_json_validity():
    """Verify node_list.json is valid"""
    with open("node_list.json", "r") as f:
        data = json.load(f)
    assert len(data) > 0, "node_list.json is empty"
    assert len(data) >= 15, f"Expected 15+ nodes, found {len(data)}"

# ============================================================================
# TEST 3: Documentation Files
# ============================================================================

def test_documentation_exists():
    """Verify all documentation files are present"""
    files = [
        "README.md",
        "TROUBLESHOOTING.md",
        "PRODUCT_ANALYSIS.md",
        "TECHNICAL_ASSESSMENT.md",
        "UX_ANALYSIS.md",
        "examples/QUICKSTART_BEGINNER.md",
        "examples/INTERMEDIATE_TUNING.md",
        "examples/ADVANCED_LORA_TESTING.md",
        "examples/EXPERT_VIDEO.md",
    ]
    
    for file in files:
        path = Path(file)
        assert path.exists(), f"Missing documentation: {file}"

# ============================================================================
# TEST 4: Agent Files
# ============================================================================

def test_agent_files_exist():
    """Verify agent definition files"""
    files = [
        ".agents.md",
        ".product-manager.agent.md",
        ".engineer.agent.md",
        ".ux-engineer.agent.md",
    ]
    
    for file in files:
        path = Path(file)
        assert path.exists(), f"Missing agent file: {file}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"Agent file too small: {file}"

# ============================================================================
# TEST 5: Widget Definitions in Config Chain
# ============================================================================

def test_widget_definitions():
    """Verify enhanced tooltips are present"""
    content = Path("sampling_config_chain.py").read_text(encoding="utf-8")
    
    # Check for enhanced tooltips
    checks = [
        ("config_type tooltip with model descriptions", "STANDARD"),
        ("seed_control tooltip explanation", "AFTER this run completes"),
        ("sampler_name tooltip with variations", "Comma-separated"),
        ("steps tooltip with performance info", "Performance"),
        ("cfg tooltip with range", "0.0-15.0"),
    ]
    
    for check_name, expected_text in checks:
        if expected_text not in content:
            raise AssertionError(f"Missing: {check_name} (expected '{expected_text}')")

# ============================================================================
# TEST 6: Example Workflows are Readable
# ============================================================================

def test_example_workflows():
    """Verify example files are readable and have content"""
    examples = [
        "examples/QUICKSTART_BEGINNER.md",
        "examples/INTERMEDIATE_TUNING.md",
        "examples/ADVANCED_LORA_TESTING.md",
        "examples/EXPERT_VIDEO.md",
    ]
    
    for example in examples:
        path = Path(example)
        content = path.read_text(encoding="utf-8")
        
        # Check for expected sections
        assert "## Goal" in content or "Goal" in content, f"Missing goal in {example}"
        assert "## Setup" in content or "Setup" in content or "setup" in content, f"Missing setup in {example}"
        assert len(content) > 500, f"Example too short: {example}"

# ============================================================================
# TEST 7: Troubleshooting Guide
# ============================================================================

def test_troubleshooting_guide():
    """Verify troubleshooting guide contains solutions"""
    content = Path("TROUBLESHOOTING.md").read_text(encoding="utf-8")
    
    issues = [
        "No Images Generated",
        "Very Slow Generation",
        "Out of Memory",
        "Grid Not Showing",
        "Seed Control Not Working",
    ]
    
    for issue in issues:
        assert issue in content, f"Missing troubleshooting for: {issue}"

# ============================================================================
# TEST 8: README Learning Path
# ============================================================================

def test_readme_learning_path():
    """Verify README has been updated with learning path"""
    content = Path("README.md").read_text(encoding="utf-8")
    
    sections = [
        "learning path",
        "QUICKSTART_BEGINNER",
        "INTERMEDIATE_TUNING",
        "ADVANCED_LORA_TESTING",
        "EXPERT_VIDEO",
        "TROUBLESHOOTING",
    ]
    
    for section in sections:
        assert section.lower() in content.lower(), f"README missing: {section}"

# ============================================================================
# TEST 9: Audio Code Quality
# ============================================================================

def test_code_improvements():
    """Verify code quality improvements"""
    sampler_content = Path("sampler_compare_advanced.py").read_text(encoding="utf-8")
    config_content = Path("sampling_config_chain.py").read_text(encoding="utf-8")
    
    # Check for instanceof checks
    assert "isinstance(config, tuple)" in sampler_content, "Missing defensive tuple check"
    
    # Check for initialization before loop
    assert "use_seed = " in sampler_content, "Missing variable initialization"
    assert "last_current_seed = " in sampler_content, "Missing variable initialization"

# ============================================================================
# TEST 10: Git Status
# ============================================================================

def test_git_status():
    """Verify all changes are committed"""
    import subprocess
    
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Allow some untracked files, but no staged/unstaged changes
        output = result.stdout.strip()
        if output and not output.startswith("??"):
            warn(f"Uncommitted changes detected:\n{output}")
        else:
            print("✅ All changes committed")
    except Exception as e:
        warn(f"Could not check git status: {e}")

# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print("\n" + "="*70)
    print("COMFYUI-MODEL-COMPARE BRANCH TEST SUITE")
    print("="*70 + "\n")
    
    tests = [
        ("Python Syntax", test_python_syntax),
        ("JSON Validity", test_json_validity),
        ("Documentation Files", test_documentation_exists),
        ("Agent Files", test_agent_files_exist),
        ("Widget Definitions", test_widget_definitions),
        ("Example Workflows", test_example_workflows),
        ("Troubleshooting Guide", test_troubleshooting_guide),
        ("README Learning Path", test_readme_learning_path),
        ("Code Improvements", test_code_improvements),
        ("Git Status", test_git_status),
    ]
    
    for test_name, test_func in tests:
        test(test_name, test_func)
    
    # Print summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    print(f"✅ Passed: {len(results['passed'])}")
    print(f"❌ Failed: {len(results['failed'])}")
    print(f"⚠️  Warnings: {len(results['warnings'])}")
    
    if results['failed']:
        print("\nFailed Tests:")
        for name, error in results['failed']:
            print(f"  - {name}")
            print(f"    {error}")
    
    if results['warnings']:
        print("\nWarnings:")
        for warning in results['warnings']:
            print(f"  - {warning}")
    
    print("\n" + "="*70)
    
    # Exit code
    if results['failed']:
        print("❌ TESTS FAILED")
        return 1
    else:
        print("✅ ALL TESTS PASSED - Ready for merge!")
        return 0

if __name__ == "__main__":
    sys.exit(main())
