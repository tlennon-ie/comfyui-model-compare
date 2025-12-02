"""
Prompt Compare Node - Generate multiple prompt variations for comparison

Features:
- Separate sliders for positive and negative prompt counts (1-20 each)
- File loading from txt or json files
- Cross-product or paired prompt modes
- Integration with Compare Tracker for progress display
"""

import os
import json
import time
from typing import Dict, List, Any, Tuple, Optional


class PromptCompare:
    """
    Node for creating multiple prompt variations to compare.
    
    Supports:
    - Manual entry: Up to 20 positive × 20 negative prompts
    - File loading: Load prompts from .txt or .json files
    - Prompt modes: Cross-product (all combinations) or Paired (1:1 matching)
    """
    
    # Version with timestamp to force UI refresh
    _version = int(time.time() % 10000)

    @classmethod
    def INPUT_TYPES(cls):
        """Define input widgets for prompt variations."""
        inputs = {
            "required": {
                "prompt_source": (["manual", "file"], {
                    "default": "manual",
                    "tooltip": "Source for prompts: manual entry or load from file"
                }),
                "prompt_mode": (["cross_product", "paired"], {
                    "default": "cross_product",
                    "tooltip": "Cross-product: all positive×negative combinations. Paired: match 1:1 (cycling shorter list)"
                }),
                "num_positive_prompts": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 20,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of positive prompt variations (1-20)"
                }),
                "num_negative_prompts": ("INT", {
                    "default": 1,
                    "min": 1,
                    "max": 20,
                    "step": 1,
                    "display": "slider",
                    "tooltip": "Number of negative prompt variations (1-20)"
                }),
                # Required first prompts
                "positive_prompt_1": ("STRING", {
                    "default": "a beautiful landscape",
                    "multiline": True,
                    "tooltip": "Primary positive prompt",
                    "dynamicPrompts": True
                }),
                "negative_prompt_1": ("STRING", {
                    "default": "",
                    "multiline": True,
                    "tooltip": "Primary negative prompt",
                    "dynamicPrompts": True
                }),
            },
            "optional": {
                # File loading options
                "prompt_file_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "tooltip": "Full path to .txt or .json prompt file"
                }),
                "file_load_mode": (["all", "range"], {
                    "default": "all",
                    "tooltip": "Load all prompts or a specific range"
                }),
                "file_start_index": ("INT", {
                    "default": 0,
                    "min": 0,
                    "max": 999,
                    "tooltip": "Starting index for range mode (0-based)"
                }),
                "file_end_index": ("INT", {
                    "default": -1,
                    "min": -1,
                    "max": 999,
                    "tooltip": "Ending index for range mode (-1 = to end)"
                }),
                "file_max_prompts": ("INT", {
                    "default": 20,
                    "min": 1,
                    "max": 100,
                    "tooltip": "Maximum number of prompts to load from file"
                }),
            },
        }

        # Add optional prompts 2-20 for both positive and negative
        for i in range(2, 21):
            inputs["optional"][f"positive_prompt_{i}"] = ("STRING", {
                "default": "",
                "multiline": True,
                "tooltip": f"Positive prompt variation {i}",
                "dynamicPrompts": True
            })
            inputs["optional"][f"negative_prompt_{i}"] = ("STRING", {
                "default": "",
                "multiline": True,
                "tooltip": f"Negative prompt variation {i}",
                "dynamicPrompts": True
            })

        return inputs

    RETURN_TYPES = ("PROMPT_COMPARE_CONFIG",)
    RETURN_NAMES = ("prompt_config",)
    FUNCTION = "execute"
    CATEGORY = "Model Compare"
    DESCRIPTION = "Create multiple prompt variations for comparison. Supports manual entry or file loading."

    def execute(self, **kwargs) -> Tuple[Dict[str, Any]]:
        """
        Generate prompt comparison configuration.
        
        Returns a PROMPT_COMPARE_CONFIG with:
        - prompt_variations: List of {index, positive, negative} dicts
        - num_variations: Total number of prompt combinations
        - mode: "cross_product" or "paired"
        """
        prompt_source = kwargs.get("prompt_source", "manual")
        prompt_mode = kwargs.get("prompt_mode", "cross_product")
        
        if prompt_source == "file":
            return self._load_from_file(kwargs, prompt_mode)
        else:
            return self._load_manual(kwargs, prompt_mode)

    def _load_manual(self, kwargs: Dict, prompt_mode: str) -> Tuple[Dict[str, Any]]:
        """Load prompts from manual widget entries."""
        num_positive = kwargs.get("num_positive_prompts", 1)
        num_negative = kwargs.get("num_negative_prompts", 1)
        
        # Collect positive prompts
        positive_prompts = []
        for i in range(1, num_positive + 1):
            prompt = kwargs.get(f"positive_prompt_{i}", "")
            if prompt or i == 1:  # Always include first prompt even if empty
                positive_prompts.append(prompt)
        
        # Collect negative prompts
        negative_prompts = []
        for i in range(1, num_negative + 1):
            prompt = kwargs.get(f"negative_prompt_{i}", "")
            negative_prompts.append(prompt)  # Include all negatives, even empty
        
        # Generate combinations based on mode
        prompts = self._generate_combinations(positive_prompts, negative_prompts, prompt_mode)
        
        print(f"[PromptCompare] Generated {len(prompts)} prompt variation(s) from manual entry")
        for i, p in enumerate(prompts[:3]):  # Show first 3
            pos_preview = p['positive'][:50] + '...' if len(p['positive']) > 50 else p['positive']
            neg_preview = p['negative'][:30] + '...' if len(p['negative']) > 30 else p['negative']
            print(f"  Variation {i+1}: pos='{pos_preview}' neg='{neg_preview or '(empty)'}'")
        if len(prompts) > 3:
            print(f"  ... and {len(prompts) - 3} more")
        
        config = {
            "prompt_variations": prompts,
            "num_variations": len(prompts),
            "mode": prompt_mode,
            "source": "manual",
        }
        
        return (config,)

    def _load_from_file(self, kwargs: Dict, prompt_mode: str) -> Tuple[Dict[str, Any]]:
        """Load prompts from a text or JSON file."""
        file_path = kwargs.get("prompt_file_path", "")
        load_mode = kwargs.get("file_load_mode", "all")
        start_idx = kwargs.get("file_start_index", 0)
        end_idx = kwargs.get("file_end_index", -1)
        max_prompts = kwargs.get("file_max_prompts", 20)
        
        if not file_path:
            print("[PromptCompare] Warning: No file path specified, using manual prompts")
            return self._load_manual(kwargs, prompt_mode)
        
        if not os.path.exists(file_path):
            print(f"[PromptCompare] Error: File not found: {file_path}")
            return self._load_manual(kwargs, prompt_mode)
        
        # Determine file type and parse
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext == ".json":
                positive_prompts, negative_prompts = self._parse_json_file(file_path)
            elif ext == ".txt":
                positive_prompts, negative_prompts = self._parse_txt_file(file_path)
            else:
                print(f"[PromptCompare] Error: Unsupported file type: {ext}")
                return self._load_manual(kwargs, prompt_mode)
        except Exception as e:
            print(f"[PromptCompare] Error parsing file: {e}")
            return self._load_manual(kwargs, prompt_mode)
        
        # Apply range filtering
        if load_mode == "range":
            if end_idx == -1:
                end_idx = len(positive_prompts)
            positive_prompts = positive_prompts[start_idx:end_idx]
            if negative_prompts:
                negative_prompts = negative_prompts[start_idx:min(end_idx, len(negative_prompts))]
        
        # Apply max limit
        positive_prompts = positive_prompts[:max_prompts]
        if negative_prompts:
            negative_prompts = negative_prompts[:max_prompts]
        
        # Ensure at least one negative prompt
        if not negative_prompts:
            negative_prompts = [""]
        
        # Generate combinations
        prompts = self._generate_combinations(positive_prompts, negative_prompts, prompt_mode)
        
        print(f"[PromptCompare] Loaded {len(prompts)} prompt variation(s) from file: {file_path}")
        
        config = {
            "prompt_variations": prompts,
            "num_variations": len(prompts),
            "mode": prompt_mode,
            "source": "file",
            "file_path": file_path,
        }
        
        return (config,)

    def _parse_json_file(self, file_path: str) -> Tuple[List[str], List[str]]:
        """
        Parse a JSON prompt file.
        
        Supported formats:
        1. Separate arrays:
           {"positive": ["prompt1", "prompt2"], "negative": ["neg1", "neg2"]}
        
        2. Paired prompts:
           {"prompts": [{"positive": "p1", "negative": "n1"}, ...]}
        
        3. Simple array (positive only):
           ["prompt1", "prompt2", "prompt3"]
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        positive_prompts = []
        negative_prompts = []
        
        if isinstance(data, list):
            # Simple array - treat as positive prompts only
            positive_prompts = [str(p) for p in data]
            negative_prompts = [""]
        elif isinstance(data, dict):
            if "prompts" in data:
                # Paired format
                for item in data["prompts"]:
                    if isinstance(item, dict):
                        positive_prompts.append(item.get("positive", ""))
                        negative_prompts.append(item.get("negative", ""))
                    elif isinstance(item, str):
                        positive_prompts.append(item)
            elif "positive" in data:
                # Separate arrays format
                positive_prompts = data.get("positive", [])
                if isinstance(positive_prompts, str):
                    positive_prompts = [positive_prompts]
                negative_prompts = data.get("negative", [""])
                if isinstance(negative_prompts, str):
                    negative_prompts = [negative_prompts]
        
        return positive_prompts, negative_prompts

    def _parse_txt_file(self, file_path: str) -> Tuple[List[str], List[str]]:
        """
        Parse a text prompt file.
        
        Format:
        - One prompt per line
        - Lines starting with # are comments (ignored)
        - Use ---NEGATIVE--- marker to separate positive from negative prompts
        - Empty lines are ignored
        
        Example:
        ```
        # Positive prompts
        a beautiful mountain landscape at sunset
        a portrait of a young woman smiling
        ---NEGATIVE---
        # Negative prompts
        blurry, low quality, watermark
        text, logo, signature
        ```
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        positive_prompts = []
        negative_prompts = []
        current_section = "positive"
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            
            # Check for section separator
            if line.upper() == "---NEGATIVE---" or line.upper() == "[NEGATIVE]":
                current_section = "negative"
                continue
            
            if current_section == "positive":
                positive_prompts.append(line)
            else:
                negative_prompts.append(line)
        
        return positive_prompts, negative_prompts

    def _generate_combinations(
        self, 
        positive_prompts: List[str], 
        negative_prompts: List[str], 
        mode: str
    ) -> List[Dict[str, Any]]:
        """
        Generate prompt combinations based on mode.
        
        Args:
            positive_prompts: List of positive prompts
            negative_prompts: List of negative prompts
            mode: "cross_product" or "paired"
        
        Returns:
            List of prompt variation dicts with index, positive, negative
        """
        prompts = []
        index = 1
        
        if mode == "cross_product":
            # All combinations: positive × negative
            for pos in positive_prompts:
                for neg in negative_prompts:
                    prompts.append({
                        "index": index,
                        "positive": pos,
                        "negative": neg,
                    })
                    index += 1
        else:  # paired
            # 1:1 matching, cycling shorter list
            max_len = max(len(positive_prompts), len(negative_prompts))
            for i in range(max_len):
                pos_idx = i % len(positive_prompts)
                neg_idx = i % len(negative_prompts)
                prompts.append({
                    "index": index,
                    "positive": positive_prompts[pos_idx],
                    "negative": negative_prompts[neg_idx],
                })
                index += 1
        
        return prompts

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """Always re-execute to pick up file changes."""
        return float("nan")


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "PromptCompare": PromptCompare,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "PromptCompare": "Ⓜ️ Model Compare - Prompts",
}
