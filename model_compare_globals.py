"""Model Compare Globals node for setting global sampling parameters.

This node allows users to configure global sampling parameters that apply
to all model variations unless overridden by SamplingConfigChain nodes.

Dynamic field selection: Users choose parameter type from dropdown,
and the value field dynamically adapts to the expected type.
"""

import comfy.samplers


class ModelCompareGlobals:
    """Configure global sampling parameters for Model Compare workflow."""
    
    CATEGORY = "loaders"
    
    # Define available parameter types and their value configurations
    PARAM_TYPES = [
        "NONE",
        "seed",
        "seed_control",
        "steps",
        "cfg",
        "denoise",
        "sampler_name",
        "scheduler",
    ]
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets with dynamic field pairs."""
        
        inputs = {
            "required": {
                "num_fields": ("INT", {
                    "default": 2,
                    "min": 1,
                    "max": 8,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of global parameter fields to configure"
                }),
            },
            "optional": {},
        }
        
        # Add field pairs (type selector + value for each type)
        for i in range(8):
            # Parameter type selector
            inputs["optional"][f"param_type_{i}"] = (cls.PARAM_TYPES, {
                "default": "NONE",
                "tooltip": f"Parameter {i+1}: Select which parameter to set globally"
            })
            
            # Value fields for each possible type (JS will show/hide based on param_type)
            # Integer value (for seed, steps)
            inputs["optional"][f"value_int_{i}"] = ("INT", {
                "default": 0,
                "min": 0,
                "max": 0xffffffffffffffff,
                "tooltip": f"Parameter {i+1}: Integer value (seed, steps)"
            })
            
            # Float value (for cfg, denoise)
            inputs["optional"][f"value_float_{i}"] = ("FLOAT", {
                "default": 1.0,
                "min": 0.0,
                "max": 100.0,
                "step": 0.01,
                "tooltip": f"Parameter {i+1}: Float value (cfg, denoise)"
            })
            
            # Seed control selector
            inputs["optional"][f"value_seed_control_{i}"] = (
                ["fixed", "increment", "decrement", "randomize"], {
                "default": "fixed",
                "tooltip": f"Parameter {i+1}: Seed control mode"
            })
            
            # Sampler selector
            inputs["optional"][f"value_sampler_{i}"] = (comfy.samplers.KSampler.SAMPLERS, {
                "default": comfy.samplers.KSampler.SAMPLERS[0],
                "tooltip": f"Parameter {i+1}: Sampler name"
            })
            
            # Scheduler selector
            inputs["optional"][f"value_scheduler_{i}"] = (comfy.samplers.KSampler.SCHEDULERS, {
                "default": comfy.samplers.KSampler.SCHEDULERS[0],
                "tooltip": f"Parameter {i+1}: Scheduler name"
            })
        
        return inputs
    
    RETURN_TYPES = ("GLOBAL_COMPARE_CONFIG",)
    RETURN_NAMES = ("global_config",)
    FUNCTION = "configure_globals"
    
    def configure_globals(self, num_fields, **kwargs):
        """Build global configuration from selected parameters.
        
        Args:
            num_fields: Number of parameter fields to process
            **kwargs: Dynamic field values (param_type_N, value_*_N)
        
        Returns:
            GLOBAL_COMPARE_CONFIG dict with parameter values
        """
        config = {
            "seed": None,
            "seed_control": None,
            "steps": None,
            "cfg": None,
            "denoise": None,
            "sampler_name": None,
            "scheduler": None,
        }
        
        for i in range(num_fields):
            param_type = kwargs.get(f"param_type_{i}", "NONE")
            
            if param_type == "NONE":
                continue
            
            # Get the appropriate value based on parameter type
            if param_type == "seed":
                value = kwargs.get(f"value_int_{i}", 0)
                config["seed"] = value
                print(f"[ModelCompareGlobals] Set seed = {value}")
                
            elif param_type == "seed_control":
                value = kwargs.get(f"value_seed_control_{i}", "fixed")
                config["seed_control"] = value
                print(f"[ModelCompareGlobals] Set seed_control = {value}")
                
            elif param_type == "steps":
                value = kwargs.get(f"value_int_{i}", 20)
                config["steps"] = value
                print(f"[ModelCompareGlobals] Set steps = {value}")
                
            elif param_type == "cfg":
                value = kwargs.get(f"value_float_{i}", 7.0)
                config["cfg"] = value
                print(f"[ModelCompareGlobals] Set cfg = {value}")
                
            elif param_type == "denoise":
                value = kwargs.get(f"value_float_{i}", 1.0)
                config["denoise"] = value
                print(f"[ModelCompareGlobals] Set denoise = {value}")
                
            elif param_type == "sampler_name":
                value = kwargs.get(f"value_sampler_{i}", "euler")
                config["sampler_name"] = value
                print(f"[ModelCompareGlobals] Set sampler_name = {value}")
                
            elif param_type == "scheduler":
                value = kwargs.get(f"value_scheduler_{i}", "normal")
                config["scheduler"] = value
                print(f"[ModelCompareGlobals] Set scheduler = {value}")
        
        # Count configured parameters
        configured = sum(1 for v in config.values() if v is not None)
        print(f"[ModelCompareGlobals] Configured {configured} global parameter(s)")
        
        return (config,)
    
    @classmethod
    def IS_CHANGED(cls, num_fields, **kwargs):
        """Check if node inputs have changed."""
        import hashlib
        
        hash_parts = [str(num_fields)]
        
        for i in range(num_fields):
            param_type = kwargs.get(f"param_type_{i}", "NONE")
            hash_parts.append(param_type)
            
            if param_type == "seed" or param_type == "steps":
                hash_parts.append(str(kwargs.get(f"value_int_{i}", 0)))
            elif param_type == "cfg" or param_type == "denoise":
                hash_parts.append(str(kwargs.get(f"value_float_{i}", 1.0)))
            elif param_type == "seed_control":
                hash_parts.append(kwargs.get(f"value_seed_control_{i}", "fixed"))
            elif param_type == "sampler_name":
                hash_parts.append(kwargs.get(f"value_sampler_{i}", ""))
            elif param_type == "scheduler":
                hash_parts.append(kwargs.get(f"value_scheduler_{i}", ""))
        
        hash_input = "|".join(hash_parts)
        return hashlib.md5(hash_input.encode()).hexdigest()


# Export for __init__.py
NODE_CLASS_MAPPINGS = {
    "ModelCompareGlobals": ModelCompareGlobals,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModelCompareGlobals": "Model Compare Globals",
}
