# Contributing to ComfyUI Model Compare

Thank you for your interest in contributing! Here are some guidelines to help you get started.

## Development Setup

1. **Fork the repository** on GitHub
2. **Clone your fork**:
   ```bash
   git clone https://github.com/yourusername/comfyui-model-compare.git
   cd comfyui-model-compare
   ```

3. **Create a feature branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

4. **Install development dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Code Style

- **Python**: Follow PEP 8 standards
- **Naming**: Use descriptive names for variables and functions
- **Comments**: Add docstrings to all classes and methods
- **Type hints**: Use type hints where possible

Example:
```python
def compute_combinations(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Compute all possible combinations of models and LoRA strengths.
    
    Args:
        config: Configuration dictionary with model selections
        
    Returns:
        List of combination dictionaries with model assignments
    """
    pass
```

## Making Changes

### Adding Features

1. **Update the relevant node file**:
   - `model_compare_loaders.py` - For loader configurations
   - `sampler_compare.py` - For sampling logic
   - `grid_compare.py` - For grid generation/styling

2. **Add input types** in `INPUT_TYPES()` classmethod:
   ```python
   @classmethod
   def INPUT_TYPES(cls):
       return {
           "required": {
               "new_param": ("TYPE", {"default": value}),
           },
           "optional": {
               "optional_param": ("TYPE", {}),
           },
       }
   ```

3. **Update function signature** and implementation
4. **Add logging** for debugging:
   ```python
   print(f"[NodeName] Message: {variable}")
   ```

5. **Update tests** if applicable

### Fixing Bugs

1. **Identify the bug** - Add description with examples
2. **Create a minimal test case** to reproduce
3. **Implement the fix** with comments explaining the change
4. **Test thoroughly** - Ensure fix doesn't break other features

## Testing

### Manual Testing

Test your changes in ComfyUI:

1. Restart ComfyUI server
2. Hard refresh browser (Ctrl+F5 or Cmd+Shift+R)
3. Load a workflow using your modified node
4. Check console (F12) for errors
5. Verify output matches expectations

### Example Test Scenario

```
1. Add ModelCompareLoaders node
2. Set: 2 checkpoints, 1 VAE, 0 text encoders, 1 LoRA
3. Add ModelCompareLoadersAdvanced node
4. Select 2 different checkpoints
5. Select 1 VAE
6. Select 1 LoRA with strengths: "0.5, 1.0"
7. Verify combinations count: 2 × 1 × (2 values) = 4
8. Add SamplerCompare and verify sampling works
9. Add GridCompare and verify grid generation
```

## Documentation

### Update README.md when:
- Adding new node
- Changing node behavior
- Adding new features
- Fixing documented behavior

### Update docstrings when:
- Changing function parameters
- Changing return types
- Adding new methods

Example:
```python
def create_grid(
    self,
    images: torch.Tensor,
    labels: str,
    ...
) -> Tuple[torch.Tensor, str]:
    """
    Create a comparison grid from images and labels.
    
    Args:
        images: Tensor of shape (N, H, W, C)
        labels: Newline-separated string of image labels
        ...
        
    Returns:
        Tuple of (grid_image_tensor, save_directory_path)
        
    Raises:
        ValueError: If images and labels counts don't match
    """
```

## Submitting Changes

### Before Submitting

1. **Test your changes** thoroughly
2. **Update documentation** if needed
3. **Update CHANGELOG** (if repo has one):
   ```
   ### Version X.X.X (Date)
   - Added: Brief description
   - Fixed: Brief description
   - Changed: Brief description
   ```

4. **Check for code style issues**:
   ```bash
   # Optional: Use flake8 if installed
   flake8 model_compare_loaders.py
   ```

### Pull Request Process

1. **Push your changes**:
   ```bash
   git add .
   git commit -m "Clear, descriptive commit message"
   git push origin feature/your-feature-name
   ```

2. **Create a Pull Request** on GitHub:
   - Provide clear title and description
   - Reference any related issues (#123)
   - Include before/after screenshots if UI-related

3. **PR Title Format**:
   - `feat: Add new grid border styles`
   - `fix: Correct LoRA strength parsing`
   - `docs: Update LoRA strength format examples`

4. **PR Description Template**:
   ```markdown
   ## Description
   Brief description of changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - Tested with: [describe test scenario]
   - Workflows tested: [link to example]
   
   ## Screenshots (if applicable)
   [Before/after images]
   
   ## Checklist
   - [ ] Code follows style guidelines
   - [ ] Documentation updated
   - [ ] No new warnings generated
   - [ ] Manual testing completed
   ```

## Areas for Contribution

### High Priority
- [ ] Web UI components for node configuration
- [ ] Performance optimization for large batch sizes
- [ ] Enhanced error handling and user messaging
- [ ] Unit tests for node logic

### Medium Priority
- [ ] Video comparison support
- [ ] Statistical analysis (SSIM, LPIPS)
- [ ] Preset configuration templates
- [ ] Advanced grid layouts

### Low Priority
- [ ] Interactive result browser
- [ ] Cloud storage integration
- [ ] Additional font/styling options
- [ ] Batch workflow chaining

## Reporting Issues

### Bug Reports

Include:
- ComfyUI version
- Python version
- Exact error message and traceback
- Steps to reproduce
- Expected vs actual behavior
- Screenshots/videos if applicable
- Complete node configuration

Template:
```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Add ModelCompareLoaders
2. Set parameters to...
3. Click execute
4. Error occurs

## Expected Behavior
What should happen

## Actual Behavior
What actually happened

## Error Message
[Full error traceback]

## Environment
- ComfyUI: [version]
- Python: [version]
- GPU: [type]
- OS: [Windows/Linux/Mac]
```

### Feature Requests

Include:
- Clear description of desired feature
- Motivation and use case
- Proposed implementation (optional)
- Examples or mockups (if applicable)

## Questions?

- Check existing issues and discussions
- Read the README and SETUP.md
- Search closed issues for similar questions
- Create a new discussion for general questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Code of Conduct

- Be respectful and inclusive
- Constructive criticism only
- No harassment or discrimination
- Assume good intent

Thank you for contributing to ComfyUI Model Compare! 🎉
