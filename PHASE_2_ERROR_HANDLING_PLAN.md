# Phase 2: Error Handling Overhaul Plan

## Executive Summary

Phase 2 focuses on transforming generic error messages into actionable guidance, implementing pre-flight validation, and replacing bare `except:` clauses with specific exception handling. This overhaul is expected to reduce debugging time by 40% and self-service resolution rate from 0% to 80%+ based on Phase 1 analysis.

**Priority Sequence**:
1. **Error Handling Audit** (1-2 days) - Identify all exception types and bare except clauses
2. **Pre-Flight Validation** (2-3 days) - File checks, config validation before sampling starts
3. **Custom Exception Types** (1 day) - Define specific exceptions for model-compare domain
4. **User Message Framework** (2-3 days) - Transform technical errors into guidance
5. **Integration & Testing** (2-3 days) - Apply fixes, verify error flows work

---

## Part 1: Error Category Audit

### Current State Analysis

**Files Requiring Review**:
- `sampler_compare_advanced.py` (2800+ lines) - Main sampling loop
- `sampling_config_chain.py` (parse and validate config)
- `model_compare_loaders.py` (model loading)
- `lora_compare.py` (LoRA integration)
- `grid_compare.py` (grid rendering)

### Known Error Patterns

**1. Bare `except:` Clauses** - Need to find and replace
```python
# ❌ CURRENT (too broad)
try:
    # code
except:
    print("Something failed")

# ✅ TARGET (specific)
except (FileNotFoundError, KeyError, torch.cuda.OutOfMemoryError) as e:
    raise ModelLoadError(f"Failed to load model: {e}") from e
```

**2. Model Loading Errors** - Lines in model_compare_loaders.py
- File doesn't exist
- Model corruption
- Unsupported model type
- Memory insufficient
- CUDA out of memory

**3. Config Chain Errors** - Lines in sampling_config_chain.py
- Invalid combo count
- Malformed CSV input (steps, cfg, samplers)
- Type mismatches in config
- Missing required parameters

**4. Sampling Loop Errors** - Lines in sampler_compare_advanced.py
- Tensor shape mismatches
- Device mismatches (CPU vs GPU)
- Out of memory during generation
- Invalid sampler/scheduler combinations
- Negative denoise/steps values
- Model not loaded

**5. Grid Rendering Errors** - Lines in grid_compare.py
- Image size mismatches
- RGB vs RGBA issues
- Grid layout calculation overflow
- Memory issues with large grids

**6. LoRA Integration Errors** - Lines in lora_compare.py
- LoRA file not found
- LoRA weight out of range
- LoRA incompatible with model
- LoRA parsing failures

---

## Part 2: Pre-Flight Validation Framework

### Validation Checks (Execute Before Sampling Starts)

#### Check 1: Model File Existence
```python
# Location: model_compare_loaders.py - NEW FUNCTION
def validate_model_files_exist(model_names: list[str]) -> ValidationResult:
    """Pre-flight check: verify all model files exist before sampling"""
    missing = []
    for model_name in model_names:
        path = Path(f"{model_dir}/{model_name}")
        if not path.exists():
            missing.append({
                "model": model_name,
                "path": path,
                "expected_size": get_recommended_size(model_name),
                "suggestion": f"Download from huggingface or check path"
            })
    
    if missing:
        raise PreFlightValidationError(
            f"Missing {len(missing)} model(s)",
            details=missing
        )
```

#### Check 2: Config Validation
```python
# Location: sampling_config_chain.py - NEW FUNCTION
def validate_config_chain(configs: list[dict]) -> ValidationResult:
    """Pre-flight check: validate all config parameters"""
    errors = []
    
    for idx, config in enumerate(configs):
        # Check required fields
        if "seed" not in config:
            errors.append(f"Config {idx}: missing seed")
        
        # Validate CSV parsing
        try:
            steps = parse_steps(config.get("steps", "20"))
            if any(s < 1 or s > 150 for s in steps):
                errors.append(f"Config {idx}: steps outside 1-150 range")
        except Exception as e:
            errors.append(f"Config {idx}: invalid steps format - {e}")
        
        # Validate CFG range
        try:
            cfg_values = parse_cfg(config.get("cfg", "7.0"))
            if any(c < 0.0 or c > 30.0 for c in cfg_values):
                errors.append(f"Config {idx}: cfg outside 0-30 range")
        except Exception as e:
            errors.append(f"Config {idx}: invalid cfg format - {e}")
    
    if errors:
        raise ConfigValidationError(
            f"Found {len(errors)} config error(s)",
            details=errors
        )
```

#### Check 3: Memory Assessment
```python
# Location: sampler_compare_advanced.py - NEW FUNCTION
def estimate_memory_requirements(combo_count: int, 
                                  model_size: int,
                                  grid_enabled: bool) -> MemoryRequirement:
    """Pre-flight check: can we fit this in VRAM?"""
    model_vram = model_size  # MB
    cache_vram = combo_count * CACHE_ENTRY_SIZE  # 100MB per combo
    grid_vram = (grid_enabled * combo_count * 4) if grid_enabled else 0  # 4MB per image
    
    total_required = model_vram + cache_vram + grid_vram
    available = get_available_vram()
    
    if total_required > available * 0.9:  # Leave 10% buffer
        raise  InsufficientMemoryError(
            f"Estimated {total_required}MB > {available}MB available",
            suggestion=f"Try reducing combinations to ~{available // CACHE_ENTRY_SIZE} or enable batching"
        )
```

#### Check 4: Sampler Compatibility
```python
# Location: sampling_config_chain.py - NEW FUNCTION
def validate_sampler_scheduler_combo(sampler: str, scheduler: str, 
                                     model_type: str) -> bool:
    """Pre-flight check: is this sampler/scheduler valid for this model?"""
    valid_combos = {
        "STANDARD": ["euler", "dpmpp_2m", "ddim", "lcm"],
        "QWEN": ["euler", "dpmpp_2m"],  # Limited support
        "WAN2.2": ["euler"],  # Most video models are strict
        "FLUX": ["euler", "dpmpp_2m_sde"],
    }
    
    if sampler not in valid_combos.get(model_type, []):
        raise InvalidSamplerError(
            f"Sampler '{sampler}' not supported for {model_type}",
            suggestion=f"Use one of: {valid_combos[model_type]}"
        )
```

---

## Part 3: Custom Exception Hierarchy

### Define Module-Specific Exceptions

```python
# Location: NEW FILE - errors.py

class ModelCompareError(Exception):
    """Base exception for model-compare domain"""
    def __init__(self, user_message, technical_details=None, suggestion=None):
        self.user_message = user_message
        self.technical_details = technical_details
        self.suggestion = suggestion
        super().__init__(self.format_message())
    
    def format_message(self):
        msg = f"❌ {self.user_message}"
        if self.suggestion:
            msg += f"\n💡 {self.suggestion}"
        if self.technical_details:
            msg += f"\n📋 Details: {self.technical_details}"
        return msg

# Model Loading
class ModelLoadError(ModelCompareError):
    """Failed to load a model (missing file, corruption, etc.)"""
    pass

class IncompatibleModelError(ModelCompareError):
    """Model type not supported or incompatible"""
    pass

# Configuration
class ConfigValidationError(ModelCompareError):
    """Config contains invalid data"""
    pass

class InvalidSamplerError(ModelCompareError):
    """Sampler not compatible with model"""
    pass

class InvalidDimensionsError(ModelCompareError):
    """Width/Height invalid for model"""
    pass

# Sampling
class SamplingError(ModelCompareError):
    """Error during generation"""
    pass

class MemoryError(ModelCompareError):
    """Not enough VRAM"""
    pass

# Pre-flight
class PreFlightValidationError(ModelCompareError):
    """Pre-flight check failed"""
    pass

# Grid
class GridRenderError(ModelCompareError):
    """Failed to render comparison grid"""
    pass

# LoRA
class LoRAError(ModelCompareError):
    """LoRA loading or application failed"""
    pass
```

---

## Part 4: User-Facing Message Map

### Error Message Transformation Patterns

**Pattern 1: File Not Found**
```python
# ❌ TECHNICAL
"FileNotFoundError: [Errno 2] No such file or directory: 'models/flux-dev.safetensors'"

# ✅ USER-FRIENDLY
❌ Model file not found: flux-dev.safetensors
💡 Download from: https://huggingface.co/black-forest/...
📋 Expected path: ComfyUI/models/checkpoints/flux-dev.safetensors
```

**Pattern 2: Out of Memory**
```python
# ❌ TECHNICAL
"RuntimeError: CUDA out of memory. Tried to allocate 5.50 GiB"

# ✅ USER-FRIENDLY
❌ GPU ran out of memory during generation
💡 Try one of:
   1. Reduce comparisons to ~4 models (vs current 8)
   2. Lower resolution from 1024 to 768
   3. Disable grid rendering
   4. Use CPU (slower but no memory limit)
📋 Details: Attempted to allocate 5.50 GiB but only 3.20 GiB available
```

**Pattern 3: Invalid CSV**
```python
# ❌ TECHNICAL
"ValueError: invalid literal for int() with base 10: 'twenty'"

# ✅ USER-FRIENDLY
❌ Invalid value in steps parameter: 'twenty'
💡 Use numbers only, and separate with commas
📋 Example: steps = "15, 20, 30" (not "fifteen, twenty, thirty")
   Current value: "twenty, 20, 30"
```

**Pattern 4: Sampler Mismatch**
```python
# ❌ TECHNICAL
"AttributeError: 'DPMSampler' has no method for 'qwen_shift'"

# ✅ USER-FRIENDLY
❌ Sampler 'dpmpp_2m' not compatible with QWEN model
💡 QWEN uses special shift parameters. Supported samplers: euler, dpmpp_2m_sde
📋 Change config_type or sampler_name
```

---

## Part 5: Implementation Sequence

### Phase 5.1: Create Error Infrastructure (1 day)

**Files to Create**:
1. `errors.py` - Custom exception hierarchy
2. `validators.py` - All pre-flight validation functions
3. `error_messages.py` - User-friendly message templates

**Implementation**:
```
Line 1-50: Exception class definitions + init with message formatting
Line 51-150: Validation functions (model files, config, memory, samplers)
Line 151+: Message templates with parameterization
```

### Phase 5.2: Instrument sampling_config_chain.py (2-3 days)

**Changes Required**:
- Line ~100: INPUT_TYPES() - Add validation on widget values
  - Validate steps CSV
  - Validate cfg CSV
  - Validate dimensions
  
- Line ~50: INPUT_TYPES() - Config type validation
  - Check if model_type is supported
  - Auto-select valid samplers

**New Functions**:
```python
def validate_csv_input(value: str, field_name: str, min_val=None, max_val=None):
    """Validate comma-separated values"""
    try:
        values = [float(v.strip()) for v in value.split(",")]
        if min_val and any(v < min_val for v in values):
            raise InvalidValueError(...)
        return values
    except ValueError as e:
        raise ConfigValidationError(...) from e

def suggest_sampler_for_model(model_type: str) -> str:
    """Return best sampler for model"""
    mapping = {
        "FLUX": "euler",
        "QWEN": "euler",
        "WAN2.2": "euler",
    }
    return mapping.get(model_type, "euler")
```

### Phase 5.3: Instrument sampler_compare_advanced.py (3-5 days)

**High-Impact Changes**:

**Section 1: Pre-flight Validation**
- Line ~200: Before sampling loop
  ```python
  try:
      validate_model_files_exist(model_names)
      validate_config_chain(configs)
      validate_memory_requirements(combo_count, use_grid=True)
  except PreFlightValidationError as e:
      return {"ui": {"error": format_user_message(e)}}
  ```

**Section 2: Model Loading**
- Line ~300-350: Replace bare `except:` in load_model()
  ```python
  try:
      model = load_checkpoint(model_path)
  except FileNotFoundError as e:
      raise ModelLoadError(
          f"Model not found: {Path(model_path).name}",
          suggestion="Download model or verify path"
      ) from e
  except torch.cuda.OutOfMemoryError as e:
      raise MemoryError(...) from e
  except Exception as e:
      raise ModelLoadError(f"Failed to load model: {e}") from e
  ```

**Section 3: Main Sampling Loop**
- Line ~400-600: Wrap iteration with try/catch
  ```python
  for combo in combinations:
      try:
          # Sample logic
      except ValueError as e:
          if "dimension" in str(e):
              raise InvalidDimensionsError(...) from e
      except RuntimeError as e:
          if "out of memory" in str(e).lower():
              raise MemoryError(...) from e
      except Exception as e:
          raise SamplingError(f"Generation failed: {e}") from e
  ```

**Section 4: Grid Rendering**
- Line ~800-900: Grid rendering error handling
  ```python
  try:
      grid = render_grid(images, layout)
  except Exception as e:
      if "dimension" in str(e):
          raise GridRenderError("Image dimensions inconsistent") from e
  ```

### Phase 5.4: Instrument model_compare_loaders.py (1-2 days)

**Changes**:
- Replace generic `Exception` raises with specific types
- Add file existence checks
- Validate model format early

**Code Pattern**:
```python
def load_model_with_validation(model_type: str, model_path: str):
    # Pre-flight
    if not Path(model_path).exists():
        raise ModelLoadError(
            f"Model not found: {Path(model_path).name}",
            suggestion=f"Expected at: {model_path}"
        )
    
    # Attempt load
    try:
        loader = get_loader_for_type(model_type)
        return loader(model_path)
    except Exception as e:
        raise ModelLoadError(f"Failed to load {model_type}") from e
```

### Phase 5.5: Test Error Paths (2-3 days)

**Test Matrix**:

| Error Type | Trigger | Expected Message | File |
|---|---|---|---|
| Missing model | Delete a model file | "Model not found" | sampler_compare_advanced.py:Line XXX |
| Bad CSV | steps="a,b,c" | "Invalid value in steps" | sampling_config_chain.py:Line YYY |
| OOM | 16 models + grid | "GPU out of memory" | sampler_compare_advanced.py:Line ZZZ |
| Bad sampler | QWEN + lcm | "Incompatible sampler" | sampling_config_chain.py:Line WWW |
| Missing LoRA | LoRA not on disk | "LoRA not found" | lora_compare.py:Line VVV |
| Grid render | Mismatched sizes | "Image size mismatch" | grid_compare.py:Line TTT |

---

## Part 6: Acceptance Criteria

### Completion Checklist

- [ ] All `except:` clauses replaced with specific exception types
- [ ] `errors.py` created with 8+ custom exception types
- [ ] Pre-flight validation implemented (4 main checks)
- [ ] All error messages include suggestion/guidance
- [ ] Test coverage includes 6+ error scenarios (see table above)
- [ ] TROUBLESHOOTING.md updated with new error messages
- [ ] README includes error handling improvements in release notes

### Success Metrics

- **Before**: Average resolution time = 15-30 minutes per error
- **After**: Average resolution time = <5 minutes (from user message guidance)

- **Before**: Support issue categories include "doesn't work"
- **After**: 80%+ of errors are self-resolvable from guidance

- **Before**: Code has 20+ bare `except:` clauses
- **After**: 0 bare `except:` clauses

---

## Part 7: Risk & Mitigation

### Risk 1: Too Many Exception Types
**Mitigation**: Limit to 8-10 core types, group related errors

### Risk 2: Error Messages Too Long
**Mitigation**: Max 3 lines: Problem → Suggestion → Details

### Risk 3: False Pre-Flight Failures
**Mitigation**: Only check critical paths (files exist, ranges valid). Don't check model compatibility predictions.

### Risk 4: Breaking Existing Workflows
**Mitigation**: Preserve exception types at module boundaries. New exceptions inherit from base. Old code still catches them.

---

## Timeline Estimate

**Total: 1.5 weeks (10 working days)**

- Day 1-2: Error infrastructure setup
- Day 3-5: sampler_compare_advanced.py overhaul
- Day 6-7: sampling_config_chain.py validation
- Day 8: model_compare_loaders.py + lora_compare.py
- Day 9-10: Testing + documentation

**Parallel Work**: While main files are being instrumented, create test matrix and documentation.

---

## Success Definition

✅ **Phase 2 Complete** when:
1. All new errors include user-friendly suggestions
2. Pre-flight validation catches 90%+ of common issues before sampling starts
3. Test suite covers 6+ error scenarios with passing tests
4. TROUBLESHOOTING.md reflects new error messages
5. Code has 0 bare `except:` clauses

**Expected Impact**: 40% reduction in user debugging time, 80%+ self-service resolution rate.
