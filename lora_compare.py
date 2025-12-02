"""LoRA Compare node for per-model-variation LoRA configuration.

This node allows configuring LoRAs that are associated with specific model variations.
Each LoRA can have:
- A mode: SINGLE (one LoRA) or HIGH_LOW_PAIR (two LoRAs for WAN 2.2 style sampling)
- Multiple strength values (comma-separated) for comparison
- Custom label for display
- A combinator (+/space) for AND/OR logic between LoRAs

LoRA Compare nodes can be chained together and connected to specific model variations
via the lora_variation_{0-4} inputs on the ModelCompareLoaders node.
"""

import folder_paths


class LoraCompare:
    """Configure LoRAs for specific model variations with support for comparison."""
    
    CATEGORY = "Model Compare/Loaders"
    
    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for the LoRA Compare node."""
        loras = cls._get_cached_loras()
        
        inputs = {
            "required": {
                "num_loras": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 10,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of LoRAs to configure"
                }),
                "lora_mode": (["SINGLE", "HIGH_LOW_PAIR"], {
                    "default": "SINGLE",
                    "tooltip": "SINGLE: One LoRA per entry. HIGH_LOW_PAIR: High/Low noise LoRA pairs (for WAN 2.2)"
                }),
            },
            "optional": {
                "lora_config_in": ("LORA_COMPARE_CONFIG", {
                    "tooltip": "Optional: Chain from another LoRA Compare node to combine configurations"
                }),
            },
        }
        
        # Add LoRA fields for each slot (0-9)
        for i in range(10):
            # Primary LoRA (or High Noise LoRA in HIGH_LOW_PAIR mode)
            inputs["optional"][f"lora_{i}"] = (
                ["NONE"] + loras,
                {"default": "NONE",
                 "tooltip": f"LoRA {i+1} (or High Noise LoRA in HIGH_LOW_PAIR mode)"},
            )
            inputs["optional"][f"lora_{i}_strengths"] = (
                "STRING",
                {
                    "default": "1.0",
                    "multiline": False,
                    "tooltip": f"LoRA {i+1}: Comma-separated strength values for comparison (e.g., '0.5,0.75,1.0')"
                },
            )
            inputs["optional"][f"lora_{i}_label"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"LoRA {i+1}: Custom display label (leave empty to use filename)"
                },
            )
            
            # Low Noise LoRA (only visible in HIGH_LOW_PAIR mode)
            inputs["optional"][f"lora_{i}_low"] = (
                ["NONE"] + loras,
                {"default": "NONE",
                 "tooltip": f"LoRA {i+1} Low Noise (only used in HIGH_LOW_PAIR mode)"},
            )
            inputs["optional"][f"lora_{i}_low_strengths"] = (
                "STRING",
                {
                    "default": "1.0",
                    "multiline": False,
                    "tooltip": f"LoRA {i+1} Low: Comma-separated strength values"
                },
            )
            inputs["optional"][f"lora_{i}_low_label"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": False,
                    "tooltip": f"LoRA {i+1} Low: Custom display label"
                },
            )
            
            # Combinator for this LoRA (how it combines with next LoRA)
            if i < 9:  # No combinator needed for last LoRA
                inputs["optional"][f"lora_{i}_combinator"] = (
                    ["+", " "],
                    {"default": "+",
                     "tooltip": f"How LoRA {i+1} combines with LoRA {i+2}: + for AND, space for OR"}
                )
        
        return inputs
    
    RETURN_TYPES = ("LORA_COMPARE_CONFIG",)
    RETURN_NAMES = ("lora_config",)
    FUNCTION = "configure_loras"
    
    @classmethod
    def _get_cached_loras(cls):
        """Get list of available LoRA models."""
        try:
            return folder_paths.get_filename_list("loras")
        except:
            return []
    
    def configure_loras(self, num_loras, lora_mode, lora_config_in=None, **kwargs):
        """Configure LoRAs and return a config object.
        
        Args:
            num_loras: Number of LoRA slots to use
            lora_mode: SINGLE or HIGH_LOW_PAIR
            lora_config_in: Optional chained config from another LoRA Compare node
            **kwargs: LoRA fields (lora_0, lora_0_strengths, etc.)
        
        Returns:
            LORA_COMPARE_CONFIG dict containing all LoRA configurations
        """
        # Start with incoming config or create new one
        if lora_config_in is not None:
            config = dict(lora_config_in)
            loras = list(config.get("loras", []))
        else:
            config = {
                "loras": [],
            }
            loras = []
        
        # Process each LoRA slot
        for i in range(num_loras):
            lora_name = kwargs.get(f"lora_{i}", "NONE")
            if lora_name == "NONE":
                continue
                
            # Get LoRA path
            lora_path = folder_paths.get_full_path("loras", lora_name)
            if lora_path is None:
                print(f"[LoraCompare] Warning: Could not find LoRA: {lora_name}")
                continue
            
            # Parse strengths
            strengths_str = kwargs.get(f"lora_{i}_strengths", "1.0")
            strengths = self._parse_strengths(strengths_str)
            
            # Get label
            label = kwargs.get(f"lora_{i}_label", "")
            if not label:
                label = lora_name
            
            # Create LoRA entry
            lora_entry = {
                "name": lora_name,
                "path": lora_path,
                "strengths": strengths,
                "label": label,
                "mode": lora_mode,
            }
            
            # Handle HIGH_LOW_PAIR mode
            if lora_mode == "HIGH_LOW_PAIR":
                lora_low_name = kwargs.get(f"lora_{i}_low", "NONE")
                if lora_low_name != "NONE":
                    lora_low_path = folder_paths.get_full_path("loras", lora_low_name)
                    if lora_low_path:
                        low_strengths_str = kwargs.get(f"lora_{i}_low_strengths", "1.0")
                        low_strengths = self._parse_strengths(low_strengths_str)
                        low_label = kwargs.get(f"lora_{i}_low_label", "")
                        if not low_label:
                            low_label = lora_low_name
                        
                        lora_entry["low_name"] = lora_low_name
                        lora_entry["low_path"] = lora_low_path
                        lora_entry["low_strengths"] = low_strengths
                        lora_entry["low_label"] = low_label
            
            # Get combinator (how this LoRA combines with next)
            if i < 9:
                combinator = kwargs.get(f"lora_{i}_combinator", "+")
                lora_entry["combinator"] = combinator
            else:
                lora_entry["combinator"] = "+"  # Default for last LoRA
            
            loras.append(lora_entry)
        
        config["loras"] = loras
        config["mode"] = lora_mode
        
        return (config,)
    
    def _parse_strengths(self, strengths_str):
        """Parse comma-separated strength values.
        
        Args:
            strengths_str: String like "0.5,0.75,1.0"
        
        Returns:
            List of float values
        """
        if not strengths_str:
            return [1.0]
        
        try:
            values = [float(s.strip()) for s in strengths_str.split(",") if s.strip()]
            return values if values else [1.0]
        except ValueError:
            print(f"[LoraCompare] Warning: Could not parse strengths '{strengths_str}', using 1.0")
            return [1.0]
    
    @classmethod
    def IS_CHANGED(cls, num_loras, lora_mode, lora_config_in=None, **kwargs):
        """Check if node inputs have changed."""
        import hashlib
        
        # Build hash of all relevant inputs
        hash_parts = [str(num_loras), lora_mode]
        
        for i in range(num_loras):
            hash_parts.append(kwargs.get(f"lora_{i}", "NONE"))
            hash_parts.append(kwargs.get(f"lora_{i}_strengths", "1.0"))
            hash_parts.append(kwargs.get(f"lora_{i}_label", ""))
            if lora_mode == "HIGH_LOW_PAIR":
                hash_parts.append(kwargs.get(f"lora_{i}_low", "NONE"))
                hash_parts.append(kwargs.get(f"lora_{i}_low_strengths", "1.0"))
                hash_parts.append(kwargs.get(f"lora_{i}_low_label", ""))
            if i < 9:
                hash_parts.append(kwargs.get(f"lora_{i}_combinator", "+"))
        
        hash_input = "|".join(hash_parts)
        return hashlib.md5(hash_input.encode()).hexdigest()


# Export for __init__.py
NODE_CLASS_MAPPINGS = {
    "LoraCompare": LoraCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LoraCompare": "Ⓜ️ Model Compare - LoRA Config",
}
