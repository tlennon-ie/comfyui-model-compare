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
    "html_grid_path": None,  # Path to generated HTML grid file
    "html_grid_url": None,   # URL to open HTML grid in browser
    # Timing/speed tracking
    "iteration_start_time": None,  # When current combination started
    "iteration_times": [],  # List of (combo_idx, duration_seconds) tuples
    "current_step": 0,  # Current step within combination
    "total_steps": 0,  # Total steps for current combination
    "step_start_time": None,  # When current step started
    "step_times": [],  # Recent step times for speed calculation (last N)
    "speed": None,  # Current speed: positive = it/s, negative = s/it (for display)
    "avg_speed": None,  # Average speed across all combinations
    "elapsed_seconds": 0,  # Total elapsed time
    "eta_seconds": None,  # Estimated time remaining
}


def reset_tracker_state():
    """Reset tracker state for a new run.
    
    NOTE: Only resets if not in 'complete' status, to preserve completed state
    until a new workflow actually starts. Call force_reset_tracker_state() to
    forcefully reset regardless of status.
    """
    global _tracker_state
    # Don't reset if we're showing completed results - user wants to see them
    if _tracker_state.get("status") == "complete":
        return
    
    _force_reset_tracker_state()


def _force_reset_tracker_state():
    """Forcefully reset tracker state regardless of current status."""
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
        "html_grid_path": None,
        "html_grid_url": None,
        # Timing/speed tracking
        "iteration_start_time": None,
        "iteration_times": [],
        "current_step": 0,
        "total_steps": 0,
        "step_start_time": None,
        "step_times": [],
        "speed": None,
        "avg_speed": None,
        "elapsed_seconds": 0,
        "eta_seconds": None,
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


def set_html_grid_available(html_path: str, relative_url: str = None):
    """Set HTML grid as available for the tracker to display.
    
    Args:
        html_path: Full filesystem path to the HTML file
        relative_url: URL path to serve the file (e.g., "/view?filename=...")
    """
    global _tracker_state
    _tracker_state["html_grid_path"] = html_path
    _tracker_state["html_grid_url"] = relative_url
    
    # Broadcast update
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync("model_compare_progress", _tracker_state)
    except Exception:
        pass


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


def start_iteration(combo_idx: int, total_steps: int):
    """Mark the start of processing a combination.
    
    Args:
        combo_idx: The 0-indexed combination number
        total_steps: Number of sampling steps for this combination
    """
    global _tracker_state
    now = time.time()
    _tracker_state["iteration_start_time"] = now
    _tracker_state["current_step"] = 0
    _tracker_state["total_steps"] = total_steps
    _tracker_state["step_start_time"] = now
    _tracker_state["step_times"] = []  # Reset step times for new combo
    
    # Calculate elapsed time
    if _tracker_state["start_time"]:
        _tracker_state["elapsed_seconds"] = now - _tracker_state["start_time"]
    
    # Broadcast update
    _broadcast_state()


def record_step_complete(step: int):
    """Record completion of a sampling step for speed calculation.
    
    Args:
        step: The step number that just completed (1-indexed)
    """
    global _tracker_state
    now = time.time()
    
    if _tracker_state["step_start_time"]:
        step_duration = now - _tracker_state["step_start_time"]
        # Keep last 10 step times for rolling average
        _tracker_state["step_times"].append(step_duration)
        if len(_tracker_state["step_times"]) > 10:
            _tracker_state["step_times"].pop(0)
        
        # Calculate speed (it/s or s/it like tqdm)
        if _tracker_state["step_times"]:
            avg_step_time = sum(_tracker_state["step_times"]) / len(_tracker_state["step_times"])
            if avg_step_time > 0:
                its = 1.0 / avg_step_time
                if its >= 1.0:
                    _tracker_state["speed"] = its  # it/s (positive)
                else:
                    _tracker_state["speed"] = -avg_step_time  # s/it (negative for display)
    
    _tracker_state["current_step"] = step
    _tracker_state["step_start_time"] = now
    
    # Update elapsed time
    if _tracker_state["start_time"]:
        _tracker_state["elapsed_seconds"] = now - _tracker_state["start_time"]
    
    # Broadcast update (but not too frequently - only every 2nd step or last step)
    if step % 2 == 0 or step == _tracker_state["total_steps"]:
        _broadcast_state()


def complete_iteration(combo_idx: int):
    """Mark completion of a combination and calculate timing stats.
    
    Args:
        combo_idx: The 0-indexed combination number that completed
    """
    global _tracker_state
    now = time.time()
    
    if _tracker_state["iteration_start_time"]:
        duration = now - _tracker_state["iteration_start_time"]
        _tracker_state["iteration_times"].append((combo_idx, duration))
        
        # Calculate average speed across all completed combinations
        total_duration = sum(t[1] for t in _tracker_state["iteration_times"])
        total_combos = len(_tracker_state["iteration_times"])
        if total_combos > 0:
            avg_combo_time = total_duration / total_combos
            _tracker_state["avg_speed"] = avg_combo_time
            
            # Calculate ETA based on remaining combinations
            remaining = _tracker_state["total_combinations"] - _tracker_state["completed_combinations"] - 1
            if remaining > 0:
                _tracker_state["eta_seconds"] = remaining * avg_combo_time
            else:
                _tracker_state["eta_seconds"] = 0
    
    # Update elapsed time
    if _tracker_state["start_time"]:
        _tracker_state["elapsed_seconds"] = now - _tracker_state["start_time"]
    
    _tracker_state["iteration_start_time"] = None
    _tracker_state["step_start_time"] = None
    
    _broadcast_state()


def _broadcast_state():
    """Broadcast current tracker state via websocket."""
    try:
        from server import PromptServer
        if PromptServer.instance is not None:
            PromptServer.instance.send_sync("model_compare_progress", _tracker_state)
    except Exception:
        pass  # Server not available


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
        
        Behavior:
        - If config provided: Force reset and start new tracking session
        - If no config: Return current state (preserving completed state)
        """
        warnings = []
        total_combinations = 0
        total_models = 0
        total_chains = 1
        
        # If config provided, this is a NEW workflow run - force reset and initialize
        if config:
            # Force reset for new job
            _force_reset_tracker_state()
            
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
            
            # Initialize global tracker state (already force reset above)
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
            # No config - just get current state (preserves completed state)
            state = get_tracker_state()
            total_combinations = state.get("total_combinations", 0)
            total_models = state.get("total_models", 0)
            total_chains = state.get("total_chains", 1)
            warnings = state.get("warnings", [])
        
        # Determine status to return
        # If config provided, we're starting fresh -> "preparing"
        # If no config, use current state status (could be "complete", "idle", etc.)
        if config:
            return_status = "preparing"
        else:
            return_status = get_tracker_state().get("status", "idle")
        
        # Return UI data for the node to display
        # The actual display is handled by JavaScript
        # NOTE: UI values must be lists for ComfyUI to merge them correctly
        return {
            "ui": {
                "total": [total_combinations],
                "models": [total_models],
                "chains": [total_chains],
                "warnings": [warnings],
                "status": [return_status],
            }
        }


# Node mappings - single consolidated node
NODE_CLASS_MAPPINGS = {
    "CompareTracker": CompareTracker,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CompareTracker": "Compare Tracker",
}
