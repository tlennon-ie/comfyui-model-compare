"""
Prompt Compare Node - Generate multiple prompt variations for comparison
"""

import time


class PromptCompare:
    """
    Node for creating multiple prompt variations to compare.
    Outputs a configuration dictionary with prompt variations.
    Supports dynamic UI with 1-10 variations controlled by slider.
    """
    
    # Version with timestamp to force UI refresh
    _version = int(time.time() % 10000)

    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for prompt variations."""
        inputs = {
            "required": {
                "num_prompt_variations": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 10,
                        "step": 1,
                        "display": "slider",
                        "tooltip": "Number of prompt variations to compare (1-10)"
                    }
                ),
                "positive_prompt_1": (
                    "STRING",
                    {
                        "default": "a beautiful landscape",
                        "multiline": True,
                        "tooltip": "Primary positive prompt",
                        "dynamicPrompts": True
                    }
                ),
                "negative_prompt_1": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "tooltip": "Primary negative prompt",
                        "dynamicPrompts": True
                    }
                ),
            },
            "optional": {},
        }

        # Add all optional fields for prompts 2-10
        # Web extension will show/hide based on num_prompt_variations slider
        for i in range(2, 11):
            inputs["optional"][f"positive_prompt_{i}"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "tooltip": f"Positive prompt variation {i}",
                    "dynamicPrompts": True
                }
            )
            inputs["optional"][f"negative_prompt_{i}"] = (
                "STRING",
                {
                    "default": "",
                    "multiline": True,
                    "tooltip": f"Negative prompt variation {i}",
                    "dynamicPrompts": True
                }
            )

        return inputs

    def execute(self, **kwargs) -> tuple:
        """
        Generate prompt comparison configuration.
        Returns a PROMPT_COMPARE_CONFIG that can be fed to the loader.
        """
        num_variations = kwargs.get("num_prompt_variations", 1)
        
        prompts = []
        for i in range(1, num_variations + 1):
            pos_key = f"positive_prompt_{i}"
            neg_key = f"negative_prompt_{i}"
            
            pos_prompt = kwargs.get(pos_key, "")
            neg_prompt = kwargs.get(neg_key, "")
            
            prompts.append({
                "index": i,
                "positive": pos_prompt,
                "negative": neg_prompt,
            })
        
        config = {
            "prompt_variations": prompts,
            "num_variations": len(prompts),
        }
        
        return (config,)

    RETURN_TYPES = ("PROMPT_COMPARE_CONFIG",)
    RETURN_NAMES = ("prompt_config",)
    FUNCTION = "execute"
    CATEGORY = "Model Compare"
    DESCRIPTION = "Create multiple prompt variations for comparison"

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "PromptCompare": PromptCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptCompare": "Prompt Compare",
}
