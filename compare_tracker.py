"""
Compare Tracker Node

A monitoring node that displays progress and status information for model comparison operations.
Shows:
- Warnings (high combination counts, etc.)
- Progress (X/Y combinations completed)
- Current chain/model being processed
- Estimated time remaining

This node uses websocket communication to receive live updates from the sampler node.
"""

import time
from typing import Dict, Any, Optional, List, Tuple
import json


# Global state for tracking progress across nodes
# This allows the sampler to update progress that the tracker can display
_tracker_state = {
    "total_combinations": 0,
    "completed_combinations": 0,
    "current_model": "",
    "current_model_index": 0,
    "total_models": 0,
    "current_chain": 0,
    "total_chains": 0,
    "warnings": [],
    "start_time": None,
    "last_update": None,
    "status": "idle",  # idle, preparing, sampling, complete, error
    "current_label": "",
}


def reset_tracker_state():
    """Reset tracker state for a new run."""
    global _tracker_state
    _tracker_state = {
        "total_combinations": 0,
        "completed_combinations": 0,
        "current_model": "",
        "current_model_index": 0,
        "total_models": 0,
        "current_chain": 0,
        "total_chains": 0,
        "warnings": [],
        "start_time": None,
        "last_update": None,
        "status": "idle",
        "current_label": "",
    }


def update_tracker_state(**kwargs):
    """Update tracker state with new values."""
    global _tracker_state
    for key, value in kwargs.items():
        if key in _tracker_state:
            _tracker_state[key] = value
    _tracker_state["last_update"] = time.time()
    
    # Broadcast update via websocket if server available
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync("model_compare_progress", _tracker_state)
    except Exception:
        pass  # Server not available


def get_tracker_state() -> Dict[str, Any]:
    """Get current tracker state."""
    return dict(_tracker_state)


def add_tracker_warning(warning: str):
    """Add a warning message to the tracker."""
    global _tracker_state
    if warning not in _tracker_state["warnings"]:
        _tracker_state["warnings"].append(warning)
        update_tracker_state()


def clear_tracker_warnings():
    """Clear all warnings."""
    global _tracker_state
    _tracker_state["warnings"] = []


class CompareTracker:
    """
    Compare Tracker Node
    
    Displays real-time progress and status information for model comparison operations.
    Can be used standalone or connected to config for pre-run analysis.
    
    Features:
    - Shows total combinations and progress with visual progress bar
    - Displays warnings (high combination counts)
    - Shows current model/chain being processed
    - Estimates remaining time
    - Live updates via websocket during sampling
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "config": ("MODEL_COMPARE_CONFIG", {
                    "tooltip": "Optional: Connect to get pre-run analysis of combinations"
                }),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }
    
    CATEGORY = "Model Compare"
    RETURN_TYPES = ()  # No outputs - this is a display-only node
    OUTPUT_NODE = True
    FUNCTION = "track_progress"
    
    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds into human readable time."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            mins = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{mins}m {secs}s"
        else:
            hours = int(seconds // 3600)
            mins = int((seconds % 3600) // 60)
            return f"{hours}h {mins}m"
    
    def track_progress(
        self,
        config: Dict[str, Any] = None,
        unique_id: str = None,
    ):
        """
        Analyze config (if provided) and display tracking information.
        
        This method is called when the workflow runs. It initializes tracking
        state and returns UI data for display.
        """
        warnings = []
        total_combinations = 0
        total_models = 0
        total_chains = 1
        
        # If config provided, analyze it
        if config:
            combinations = config.get("combinations", [])
            model_variations = config.get("model_variations", [])
            sampling_configs = config.get("sampling_configs", {})
            
            total_combinations = len(combinations)
            total_models = len(model_variations)
            
            # Count unique chains (variation indices)
            chain_indices = set()
            for idx, combo in enumerate(combinations):
                chain_cfg = sampling_configs.get(idx, {})
                chain_idx = chain_cfg.get("variation_index", 1)
                chain_indices.add(chain_idx)
            total_chains = len(chain_indices) if chain_indices else 1
            
            # Calculate estimated variation count from sampling configs
            estimated_variations = total_combinations
            
            for idx, chain_cfg in sampling_configs.items():
                variation_count = chain_cfg.get("_variation_count", 1)
                if variation_count > 1:
                    estimated_variations = max(estimated_variations, total_combinations * variation_count)
                
                # Check for high variation warning
                if variation_count > 20:
                    chain_idx = chain_cfg.get("variation_index", idx + 1)
                    warnings.append(f"Chain {chain_idx}: {variation_count} variations")
            
            total_combinations = estimated_variations
            
            # Collect warnings
            if total_combinations > 20:
                warnings.insert(0, f"High count: {total_combinations} combinations")
            
            if total_models > 1:
                warnings.append(f"{total_models} models to load sequentially")
            
            # Initialize global tracker state
            reset_tracker_state()
            update_tracker_state(
                total_combinations=total_combinations,
                completed_combinations=0,
                total_models=total_models,
                total_chains=total_chains,
                warnings=warnings,
                start_time=time.time(),
                status="preparing",
            )
        else:
            # No config - just get current state
            state = get_tracker_state()
            total_combinations = state.get("total_combinations", 0)
            total_models = state.get("total_models", 0)
            total_chains = state.get("total_chains", 1)
            warnings = state.get("warnings", [])
        
        # Return UI data for the node to display
        # The actual display is handled by JavaScript
        return {
            "ui": {
                "total": total_combinations,
                "models": total_models,
                "chains": total_chains,
                "warnings": warnings,
                "status": "preparing" if config else "idle",
            }
        }


# Node mappings - single consolidated node
NODE_CLASS_MAPPINGS = {
    "CompareTracker": CompareTracker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CompareTracker": "Compare Tracker",
}
