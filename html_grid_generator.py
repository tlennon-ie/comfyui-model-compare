"""
HTML Grid Generator Module

Generates interactive, self-contained HTML comparison grids with:
- Filtering by any varying dimension (sampler, scheduler, steps, etc.)
- Sorting controls
- Lightbox for full-size image viewing
- Detailed metadata display on hover
- Dark/light theme support
- Shareable via URL hash parameters
"""

import os
import base64
import json
import html
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from PIL import Image
import io


def image_to_base64(image: Image.Image, format: str = "PNG", quality: int = 85) -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    if format.upper() == "JPEG":
        # Convert RGBA to RGB for JPEG
        if image.mode == "RGBA":
            image = image.convert("RGB")
        image.save(buffer, format="JPEG", quality=quality)
    else:
        image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def get_varying_dimensions(combinations: List[Dict], config: Dict = None) -> Dict[str, List[Any]]:
    """
    Analyze combinations to find dimensions with multiple unique values.
    Properly extracts nested data from lora_config, model_variations, etc.
    Returns dict of dimension_name -> sorted list of unique values.
    """
    if not combinations:
        return {}
    
    # Initialize field value sets
    field_values = {
        'model': set(),
        'vae': set(),
        'clip': set(),
        'lora_name': set(),
        'lora_strength': set(),
        'lora_display': set(),
        'sampler_name': set(),
        'scheduler': set(),
        'steps': set(),
        'cfg': set(),
        'denoise': set(),
        'seed': set(),
        'width': set(),
        'height': set(),
        'lumina_shift': set(),
        'qwen_shift': set(),
        'wan_shift': set(),
        'wan22_shift': set(),
        'hunyuan_shift': set(),
        'flux_guidance': set(),
        'prompt_positive': set(),
        'prompt_negative': set(),
    }
    
    # Get model variations for name lookup
    model_variations = config.get('model_variations', []) if config else []
    
    for combo in combinations:
        # Check _sampling_override first (for expanded variations)
        override = combo.get('_sampling_override', {})
        
        # Extract model name from model_index
        model_idx = combo.get('model_index', 0)
        if model_idx < len(model_variations):
            model_entry = model_variations[model_idx]
            model_name = model_entry.get('display_name', model_entry.get('name', f'Model {model_idx}'))
            # Clean up model name
            if model_name and model_name.endswith('.safetensors'):
                model_name = model_name[:-12]
            field_values['model'].add(model_name)
        
        # Extract VAE name
        vae_name = combo.get('vae_name', '')
        if vae_name:
            if vae_name.endswith('.safetensors'):
                vae_name = vae_name[:-12]
            field_values['vae'].add(vae_name)
        
        # Extract CLIP info from clip_variation structure
        clip_var = combo.get('clip_variation')
        if clip_var:
            if clip_var.get('type') == 'pair':
                clip_name = f"{clip_var.get('a', '')}+{clip_var.get('b', '')}"
            else:
                clip_name = clip_var.get('model', clip_var.get('clip_type', ''))
            if clip_name:
                field_values['clip'].add(clip_name)
        
        # Extract LoRA info from lora_config structure
        lora_config = combo.get('lora_config', {})
        loras = lora_config.get('loras', [])
        if loras:
            for lora in loras:
                name = lora.get('label', lora.get('name', ''))
                if name:
                    if name.endswith('.safetensors'):
                        name = name[:-12]
                    field_values['lora_name'].add(name)
                strength = lora.get('strength')
                if strength is not None:
                    field_values['lora_strength'].add(strength)
        
        # Get display string for lora config
        lora_display = lora_config.get('display', '')
        if lora_display and lora_display != 'No LoRA':
            field_values['lora_display'].add(lora_display)
        
        # Standard sampling parameters (check override first)
        for field in ['sampler_name', 'scheduler', 'steps', 'cfg', 'denoise', 'seed', 'width', 'height']:
            value = override.get(field, combo.get(field))
            if value is not None:
                field_values[field].add(value)
        
        # Shift parameters
        for shift_field in ['lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift', 'hunyuan_shift', 'flux_guidance']:
            value = override.get(shift_field, combo.get(shift_field))
            if value is not None:
                field_values[shift_field].add(value)
        
        # Prompt variations
        for prompt_field in ['prompt_positive', 'prompt_negative']:
            value = combo.get(prompt_field, '')
            if value:
                # Store full prompts - truncation happens in display only
                field_values[prompt_field].add(value)
    
    # Return only fields with >1 unique value (varying dimensions)
    varying = {}
    for field, values in field_values.items():
        if len(values) > 1:
            try:
                sorted_values = sorted(values)
            except TypeError:
                sorted_values = list(values)
            varying[field] = sorted_values
    
    return varying


def format_field_name(field: str) -> str:
    """Format field name for display."""
    labels = {
        'sampler_name': 'Sampler',
        'scheduler': 'Scheduler',
        'steps': 'Steps',
        'cfg': 'CFG',
        'denoise': 'Denoise',
        'width': 'Width',
        'height': 'Height',
        'seed': 'Seed',
        'model': 'Model',
        'vae': 'VAE',
        'clip': 'CLIP',
        'lora_name': 'LoRA',
        'lora_strength': 'LoRA Strength',
        'lora_display': 'LoRA Config',
        'lora_names': 'LoRAs',
        'lora_strengths': 'LoRA Strengths',
        'lumina_shift': 'Lumina Shift',
        'qwen_shift': 'Qwen Shift',
        'wan_shift': 'WAN Shift',
        'wan22_shift': 'WAN 2.2 Shift',
        'hunyuan_shift': 'Hunyuan Shift',
        'flux_guidance': 'FLUX Guidance',
        'prompt_positive': 'Positive Prompt',
        'prompt_negative': 'Negative Prompt',
    }
    return labels.get(field, field.replace('_', ' ').title())


def format_value(value: Any) -> str:
    """Format a value for display."""
    if value is None:
        return ""
    if isinstance(value, float):
        formatted = f"{value:.4f}".rstrip('0').rstrip('.')
        return formatted
    if isinstance(value, str):
        # Truncate long strings
        if len(value) > 50:
            return value[:47] + "..."
        # Remove .safetensors extension
        if value.endswith('.safetensors'):
            return value[:-12]
    return str(value)


def get_combo_params(combo: Dict) -> Dict[str, Any]:
    """Extract all relevant parameters from a combination."""
    override = combo.get('_sampling_override', {})
    
    params = {}
    
    # Priority: override > combo direct
    fields = [
        'sampler_name', 'scheduler', 'steps', 'cfg', 'denoise',
        'width', 'height', 'seed', 'model', 'vae', 'clip',
        'model_index', 'vae_name', 'prompt_positive', 'prompt_negative',
        'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift',
        'hunyuan_shift', 'flux_guidance', 'num_frames', 'config_type'
    ]
    
    for field in fields:
        value = override.get(field, combo.get(field))
        if value is not None:
            params[field] = value
    
    # Add variation label if present
    if '_variation_label' in combo:
        params['variation_label'] = combo['_variation_label']
    
    # Extract model name from model_variations if available
    if 'model_index' in combo:
        params['model_index'] = combo['model_index']
    
    # Extract LoRA info from nested lora_config structure
    lora_config = combo.get('lora_config', {})
    loras = lora_config.get('loras', [])
    if loras:
        # Extract names and strengths
        lora_names = []
        lora_strengths = []
        for lora in loras:
            name = lora.get('label', lora.get('name', ''))
            if name:
                if name.endswith('.safetensors'):
                    name = name[:-12]
                lora_names.append(name)
            strength = lora.get('strength')
            if strength is not None:
                lora_strengths.append(strength)
        
        if len(lora_names) == 1:
            params['lora_name'] = lora_names[0]
            if lora_strengths:
                params['lora_strength'] = lora_strengths[0]
        elif len(lora_names) > 1:
            params['lora_names'] = ', '.join(lora_names)
            if lora_strengths:
                params['lora_strengths'] = ', '.join(str(s) for s in lora_strengths)
    
    # Also add lora_display for filtering
    lora_display = lora_config.get('display', '')
    if lora_display and lora_display != 'No LoRA':
        params['lora_display'] = lora_display
    
    return params


# CSS Template for the HTML grid
CSS_TEMPLATE = """
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #0f3460;
    --text-primary: #eaeaea;
    --text-secondary: #a0a0a0;
    --accent: #e94560;
    --accent-hover: #ff6b6b;
    --border: #2a2a4a;
    --shadow: rgba(0, 0, 0, 0.3);
}

[data-theme="light"] {
    --bg-primary: #f5f5f5;
    --bg-secondary: #ffffff;
    --bg-card: #ffffff;
    --text-primary: #333333;
    --text-secondary: #666666;
    --accent: #e94560;
    --accent-hover: #d63050;
    --border: #dddddd;
    --shadow: rgba(0, 0, 0, 0.1);
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
}

.container {
    max-width: 1800px;
    margin: 0 auto;
    padding: 20px;
}

/* Header */
.header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    background: var(--bg-secondary);
    border-radius: 12px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px var(--shadow);
}

.header h1 {
    font-size: 1.5rem;
    font-weight: 600;
}

.header-tagline {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 0.85rem;
    color: var(--text-secondary);
    margin-top: 4px;
}

.header-tagline a {
    color: var(--accent);
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: color 0.2s;
}

.header-tagline a:hover {
    color: var(--accent-hover);
    text-decoration: underline;
}

.github-icon {
    width: 16px;
    height: 16px;
    fill: currentColor;
}

.header-controls {
    display: flex;
    gap: 10px;
    align-items: center;
}

.theme-toggle {
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-primary);
    padding: 8px 16px;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
}

.theme-toggle:hover {
    background: var(--accent);
    color: white;
}

/* Stats */
.stats {
    display: flex;
    gap: 20px;
    font-size: 0.9rem;
    color: var(--text-secondary);
}

.stat {
    display: flex;
    align-items: center;
    gap: 5px;
}

/* Filters */
.filters {
    display: flex;
    flex-wrap: wrap;
    gap: 15px;
    padding: 20px;
    background: var(--bg-secondary);
    border-radius: 12px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px var(--shadow);
}

.filter-group {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.filter-group label {
    font-size: 0.8rem;
    color: var(--text-secondary);
    font-weight: 500;
}

.filter-group select {
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-card);
    color: var(--text-primary);
    font-size: 0.9rem;
    min-width: 150px;
    cursor: pointer;
}

.filter-group select:focus {
    outline: none;
    border-color: var(--accent);
}

.filter-actions {
    display: flex;
    align-items: flex-end;
    gap: 10px;
}

.btn {
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s;
}

.btn-primary {
    background: var(--accent);
    color: white;
}

.btn-primary:hover {
    background: var(--accent-hover);
}

.btn-secondary {
    background: var(--bg-card);
    color: var(--text-primary);
    border: 1px solid var(--border);
}

.btn-secondary:hover {
    background: var(--border);
}

/* Grid */
.grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 20px;
}

.grid-item {
    background: var(--bg-card);
    border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 4px 6px var(--shadow);
    transition: transform 0.2s, box-shadow 0.2s;
    cursor: pointer;
    position: relative;
}

/* Compare checkbox in corner of each grid item */
.compare-checkbox {
    position: absolute;
    top: 8px;
    left: 8px;
    width: 24px;
    height: 24px;
    background: rgba(0, 0, 0, 0.6);
    border: 2px solid #fff;
    border-radius: 4px;
    cursor: pointer;
    z-index: 10;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.compare-checkbox:hover {
    background: rgba(0, 0, 0, 0.8);
    transform: scale(1.1);
}

.compare-checkbox.checked {
    background: var(--accent);
    border-color: var(--accent);
}

.compare-checkbox.checked::after {
    content: '✓';
    color: white;
    font-size: 14px;
    font-weight: bold;
}

.compare-checkbox .check-number {
    color: white;
    font-size: 12px;
    font-weight: bold;
}

.grid-item:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 25px var(--shadow);
}

.grid-item.hidden {
    display: none;
}

.grid-item img {
    width: 100%;
    aspect-ratio: 1;
    object-fit: contain;
    display: block;
    background: var(--bg-secondary);
    padding: 4px;
    box-sizing: border-box;
}

/* Image loading container */
.grid-item-image-container {
    position: relative;
    width: 100%;
    aspect-ratio: 1;
    background: var(--bg-secondary);
}

.grid-item-image-container.loading .image-loading-spinner {
    display: flex;
}

.grid-item-image-container:not(.loading) .image-loading-spinner {
    display: none;
}

.image-loading-spinner {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: var(--text-secondary);
    display: none;
    align-items: center;
    justify-content: center;
}

.grid-item-image-container.error {
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(255, 0, 0, 0.1);
}

.grid-item-image-container.error .image-loading-spinner {
    display: flex;
    font-size: 32px;
    color: #ff4444;
}

.grid-item-info {
    padding: 12px;
}

.grid-item-label {
    font-size: 0.85rem;
    color: var(--text-primary);
    margin-bottom: 8px;
    font-weight: 500;
    line-height: 1.4;
    /* Allow multi-line wrapping with more generous height */
    word-wrap: break-word;
    overflow-wrap: break-word;
    white-space: normal;
    max-height: 6em;
    overflow: hidden;
}

.grid-item-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}

.meta-tag {
    font-size: 0.7rem;
    padding: 3px 8px;
    background: var(--bg-secondary);
    border-radius: 4px;
    color: var(--text-secondary);
    display: flex;
    align-items: center;
    gap: 4px;
}

.meta-tag-label {
    font-weight: 600;
    opacity: 0.7;
}

/* Color-coded meta tags by field type */
.meta-tag-sampler {
    background: rgba(233, 69, 96, 0.2);
    border: 1px solid rgba(233, 69, 96, 0.4);
    color: #e94560;
}

.meta-tag-scheduler {
    background: rgba(129, 140, 248, 0.2);
    border: 1px solid rgba(129, 140, 248, 0.4);
    color: #818cf8;
}

.meta-tag-steps {
    background: rgba(52, 211, 153, 0.2);
    border: 1px solid rgba(52, 211, 153, 0.4);
    color: #34d399;
}

.meta-tag-cfg {
    background: rgba(251, 191, 36, 0.2);
    border: 1px solid rgba(251, 191, 36, 0.4);
    color: #fbbf24;
}

.meta-tag-denoise {
    background: rgba(236, 72, 153, 0.2);
    border: 1px solid rgba(236, 72, 153, 0.4);
    color: #ec4899;
}

.meta-tag-seed {
    background: rgba(14, 165, 233, 0.2);
    border: 1px solid rgba(14, 165, 233, 0.4);
    color: #0ea5e9;
}

.meta-tag-model {
    background: rgba(168, 85, 247, 0.2);
    border: 1px solid rgba(168, 85, 247, 0.4);
    color: #a855f7;
}

.meta-tag-lora {
    background: rgba(249, 115, 22, 0.2);
    border: 1px solid rgba(249, 115, 22, 0.4);
    color: #f97316;
}

.meta-tag-default {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
}

/* Light theme adjustments for tags */
[data-theme="light"] .meta-tag-sampler { color: #be123c; }
[data-theme="light"] .meta-tag-scheduler { color: #4f46e5; }
[data-theme="light"] .meta-tag-steps { color: #059669; }
[data-theme="light"] .meta-tag-cfg { color: #d97706; }
[data-theme="light"] .meta-tag-denoise { color: #be185d; }
[data-theme="light"] .meta-tag-seed { color: #0284c7; }
[data-theme="light"] .meta-tag-model { color: #7c3aed; }
[data-theme="light"] .meta-tag-lora { color: #c2410c; }

/* Lightbox */
.lightbox {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.95);
    display: none;
    z-index: 1000;
    overflow: auto;
}

.lightbox.active {
    display: flex;
}

.lightbox-content {
    display: flex;
    width: 100%;
    height: 100%;
    padding: 20px;
}

.lightbox-image-container {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 20px;
}

.lightbox-image {
    max-width: 100%;
    max-height: 90vh;
    object-fit: contain;
    border-radius: 8px;
}

.lightbox-details {
    width: 350px;
    background: var(--bg-secondary);
    border-radius: 12px;
    padding: 20px;
    overflow-y: auto;
    max-height: 90vh;
}

.lightbox-close {
    position: fixed;
    top: 20px;
    right: 20px;
    background: var(--accent);
    color: white;
    border: none;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    font-size: 1.5rem;
    cursor: pointer;
    z-index: 1001;
    display: flex;
    align-items: center;
    justify-content: center;
}

.lightbox-close:hover {
    background: var(--accent-hover);
}

.detail-section {
    margin-bottom: 20px;
}

.detail-section h3 {
    font-size: 0.9rem;
    color: var(--text-secondary);
    margin-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.detail-row {
    display: flex;
    justify-content: space-between;
    padding: 8px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.85rem;
}

.detail-row:last-child {
    border-bottom: none;
}

.detail-label {
    color: var(--text-secondary);
}

.detail-value {
    color: var(--text-primary);
    font-weight: 500;
    text-align: right;
    max-width: 200px;
    word-break: break-word;
}

.prompt-section {
    margin-top: 15px;
}

.prompt-text {
    background: var(--bg-card);
    padding: 12px;
    border-radius: 8px;
    font-size: 0.8rem;
    line-height: 1.5;
    color: var(--text-primary);
    max-height: 150px;
    overflow-y: auto;
}

/* Navigation arrows */
.lightbox-nav {
    position: fixed;
    top: 50%;
    transform: translateY(-50%);
    background: var(--bg-card);
    color: var(--text-primary);
    border: none;
    width: 50px;
    height: 50px;
    border-radius: 50%;
    font-size: 1.5rem;
    cursor: pointer;
    z-index: 1001;
    display: flex;
    align-items: center;
    justify-content: center;
    opacity: 0.8;
    transition: opacity 0.2s;
}

.lightbox-nav:hover {
    opacity: 1;
    background: var(--accent);
    color: white;
}

.lightbox-prev {
    left: 20px;
}

.lightbox-next {
    right: 380px;
}

/* No results */
.no-results {
    grid-column: 1 / -1;
    text-align: center;
    padding: 60px 20px;
    color: var(--text-secondary);
}

.no-results h2 {
    margin-bottom: 10px;
}

/* Footer */
.footer {
    margin-top: 40px;
    padding: 20px;
    text-align: center;
    color: var(--text-secondary);
    font-size: 0.8rem;
}

/* Responsive */
@media (max-width: 768px) {
    .header {
        flex-direction: column;
        gap: 15px;
        text-align: center;
    }
    
    .filters {
        flex-direction: column;
    }
    
    .filter-group select {
        width: 100%;
    }
    
    .lightbox-content {
        flex-direction: column;
    }
    
    .lightbox-details {
        width: 100%;
        max-height: none;
    }
    
    .lightbox-next {
        right: 20px;
    }
}

/* Image Comparison Selection Mode */
.grid-item.selected-for-compare {
    outline: 3px solid var(--accent);
    outline-offset: 2px;
}

.compare-toolbar {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--bg-secondary);
    padding: 12px 24px;
    border-radius: 12px;
    box-shadow: 0 4px 20px var(--shadow);
    display: flex;
    gap: 12px;
    align-items: center;
    z-index: 100;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.3s, visibility 0.3s, transform 0.3s;
}

.compare-toolbar.visible {
    opacity: 1;
    visibility: visible;
}

.compare-toolbar .selection-count {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.compare-toolbar .btn {
    padding: 10px 20px;
    border: none;
    border-radius: 8px;
    cursor: pointer;
    font-size: 0.9rem;
    font-weight: 500;
    transition: background 0.2s;
}

.compare-toolbar .btn-compare {
    background: var(--accent);
    color: white;
}

.compare-toolbar .btn-compare:hover {
    background: var(--accent-hover);
}

.compare-toolbar .btn-cancel {
    background: var(--bg-card);
    color: var(--text-primary);
}

/* Comparison Slider Modal */
.compare-modal {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.95);
    z-index: 2000;
    flex-direction: column;
}

.compare-modal.visible {
    display: flex;
}

.compare-modal-header {
    padding: 15px 20px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: var(--bg-secondary);
}

.compare-modal-header h2 {
    font-size: 1.1rem;
    color: var(--text-primary);
}

.compare-modal-close {
    background: none;
    border: none;
    color: var(--text-primary);
    font-size: 1.5rem;
    cursor: pointer;
    padding: 5px 10px;
}

.compare-container {
    flex: 1;
    position: relative;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: hidden;
    padding: 20px;
}

.compare-wrapper {
    position: relative;
    max-width: 100%;
    max-height: 100%;
}

.compare-image-container {
    position: relative;
    overflow: hidden;
}

.compare-image {
    display: block;
    max-width: 100%;
    max-height: calc(100vh - 150px);
    object-fit: contain;
}

.compare-image-overlay {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    overflow: hidden;
}

.compare-image-overlay img {
    height: 100%;
    object-fit: cover;
    object-position: left;
}

.compare-slider {
    position: absolute;
    top: 0;
    width: 4px;
    height: 100%;
    background: var(--accent);
    cursor: ew-resize;
    z-index: 10;
}

.compare-slider::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 40px;
    height: 40px;
    background: var(--accent);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
}

.compare-slider::after {
    content: '⟷';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    color: white;
    font-size: 1.2rem;
    font-weight: bold;
}

.compare-labels {
    position: absolute;
    bottom: 10px;
    left: 0;
    right: 0;
    display: flex;
    justify-content: space-between;
    padding: 0 20px;
    pointer-events: none;
}

.compare-label {
    background: var(--bg-secondary);
    padding: 8px 16px;
    border-radius: 6px;
    font-size: 0.85rem;
    color: var(--text-primary);
    max-width: 45%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}
"""

# JavaScript Template for interactivity
JS_TEMPLATE = """
(function() {
    // Data passed from Python
    const gridData = __GRID_DATA__;
    const varyingDimensions = __VARYING_DIMS__;
    
    let currentIndex = 0;
    let visibleItems = [];
    
    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        initFilters();
        initGrid();
        initLightbox();
        initTheme();
        updateStats();
        
        // Parse URL hash for initial state
        loadFromHash();
    });
    
    // Theme toggle
    function initTheme() {
        const saved = localStorage.getItem('gridTheme') || 'dark';
        document.documentElement.setAttribute('data-theme', saved);
        
        document.getElementById('themeToggle').addEventListener('click', function() {
            const current = document.documentElement.getAttribute('data-theme');
            const next = current === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', next);
            localStorage.setItem('gridTheme', next);
            this.textContent = next === 'dark' ? '☀️ Light' : '🌙 Dark';
        });
        
        document.getElementById('themeToggle').textContent = saved === 'dark' ? '☀️ Light' : '🌙 Dark';
    }
    
    // Initialize filter dropdowns
    function initFilters() {
        const filtersContainer = document.getElementById('filters');
        
        Object.entries(varyingDimensions).forEach(([field, values]) => {
            const group = document.createElement('div');
            group.className = 'filter-group';
            
            const label = document.createElement('label');
            label.textContent = formatFieldName(field);
            label.setAttribute('for', 'filter-' + field);
            
            const select = document.createElement('select');
            select.id = 'filter-' + field;
            select.dataset.field = field;
            
            // Add "All" option
            const allOption = document.createElement('option');
            allOption.value = '';
            allOption.textContent = 'All';
            select.appendChild(allOption);
            
            // Add value options
            values.forEach(value => {
                const option = document.createElement('option');
                option.value = String(value);
                option.textContent = formatValue(value);
                select.appendChild(option);
            });
            
            select.addEventListener('change', applyFilters);
            
            group.appendChild(label);
            group.appendChild(select);
            filtersContainer.insertBefore(group, document.querySelector('.filter-actions'));
        });
    }
    
    // Initialize grid items
    function initGrid() {
        const grid = document.getElementById('grid');
        
        gridData.forEach((item, index) => {
            const div = document.createElement('div');
            div.className = 'grid-item';
            div.dataset.index = index;
            
            // Set data attributes for filtering
            Object.entries(item.params).forEach(([key, value]) => {
                div.dataset[key] = String(value);
            });
            
            // Compare checkbox (always visible in corner)
            const checkbox = document.createElement('div');
            checkbox.className = 'compare-checkbox';
            checkbox.title = 'Select for comparison';
            checkbox.addEventListener('click', (e) => {
                e.stopPropagation();
                toggleCompareSelection(index, checkbox, div);
            });
            
            // Image with loading animation
            const imgContainer = document.createElement('div');
            imgContainer.className = 'grid-item-image-container loading';
            
            const loadingSpinner = document.createElement('div');
            loadingSpinner.className = 'image-loading-spinner';
            loadingSpinner.innerHTML = `
                <svg width="40" height="40" viewBox="0 0 40 40">
                    <circle cx="20" cy="20" r="18" stroke="currentColor" stroke-width="3" fill="none" opacity="0.25"/>
                    <circle cx="20" cy="20" r="18" stroke="currentColor" stroke-width="3" fill="none" stroke-dasharray="90" stroke-dashoffset="0" opacity="0.75">
                        <animateTransform attributeName="transform" type="rotate" from="0 20 20" to="360 20 20" dur="1s" repeatCount="indefinite"/>
                    </circle>
                </svg>
            `;
            
            const img = document.createElement('img');
            img.src = item.image;
            img.alt = item.label || 'Image ' + (index + 1);
            img.loading = 'lazy';
            img.style.opacity = '0';
            img.style.transition = 'opacity 0.3s ease-in-out';
            
            img.addEventListener('load', () => {
                imgContainer.classList.remove('loading');
                img.style.opacity = '1';
            });
            
            img.addEventListener('error', () => {
                imgContainer.classList.remove('loading');
                imgContainer.classList.add('error');
                loadingSpinner.innerHTML = '⚠️';
            });
            
            imgContainer.appendChild(loadingSpinner);
            imgContainer.appendChild(img);
            
            // Info section
            const info = document.createElement('div');
            info.className = 'grid-item-info';
            
            const label = document.createElement('div');
            label.className = 'grid-item-label';
            label.textContent = item.label || buildLabel(item.params);
            
            const meta = document.createElement('div');
            meta.className = 'grid-item-meta';
            
            // Add key parameter tags with labels and color coding
            const keyParams = ['sampler_name', 'scheduler', 'steps', 'cfg', 'denoise', 'seed'];
            keyParams.forEach(param => {
                if (item.params[param] !== undefined) {
                    const tag = document.createElement('span');
                    tag.className = 'meta-tag ' + getTagClass(param);
                    
                    const labelSpan = document.createElement('span');
                    labelSpan.className = 'meta-tag-label';
                    labelSpan.textContent = getTagLabel(param);
                    
                    tag.appendChild(labelSpan);
                    tag.appendChild(document.createTextNode(formatValue(item.params[param])));
                    meta.appendChild(tag);
                }
            });
            
            info.appendChild(label);
            info.appendChild(meta);
            div.appendChild(checkbox);  // Add checkbox first (will be positioned absolute)
            div.appendChild(imgContainer);
            div.appendChild(info);
            
            div.addEventListener('click', () => openLightbox(index));
            
            grid.appendChild(div);
        });
        
        visibleItems = Array.from(document.querySelectorAll('.grid-item'));
    }
    
    // Apply filters
    function applyFilters() {
        const filters = {};
        document.querySelectorAll('#filters select').forEach(select => {
            if (select.value) {
                filters[select.dataset.field] = select.value;
            }
        });
        
        const items = document.querySelectorAll('.grid-item');
        visibleItems = [];
        
        items.forEach(item => {
            let visible = true;
            
            Object.entries(filters).forEach(([field, value]) => {
                if (String(item.dataset[field]) !== value) {
                    visible = false;
                }
            });
            
            item.classList.toggle('hidden', !visible);
            if (visible) visibleItems.push(item);
        });
        
        updateStats();
        saveToHash();
        
        // Show no results message if needed
        const noResults = document.getElementById('noResults');
        if (visibleItems.length === 0) {
            if (!noResults) {
                const msg = document.createElement('div');
                msg.id = 'noResults';
                msg.className = 'no-results';
                msg.innerHTML = '<h2>No Results</h2><p>Try adjusting your filters.</p>';
                document.getElementById('grid').appendChild(msg);
            }
        } else if (noResults) {
            noResults.remove();
        }
    }
    
    // Reset filters
    window.resetFilters = function() {
        document.querySelectorAll('#filters select').forEach(select => {
            select.value = '';
        });
        applyFilters();
    };
    
    // Update stats display
    function updateStats() {
        const total = gridData.length;
        const visible = visibleItems.length;
        document.getElementById('statsTotal').textContent = total;
        document.getElementById('statsVisible').textContent = visible;
    }
    
    // Lightbox
    function initLightbox() {
        const lightbox = document.getElementById('lightbox');
        
        document.getElementById('lightboxClose').addEventListener('click', closeLightbox);
        document.getElementById('lightboxPrev').addEventListener('click', () => navigateLightbox(-1));
        document.getElementById('lightboxNext').addEventListener('click', () => navigateLightbox(1));
        
        lightbox.addEventListener('click', function(e) {
            if (e.target === lightbox || e.target.classList.contains('lightbox-content')) {
                closeLightbox();
            }
        });
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (!lightbox.classList.contains('active')) return;
            
            if (e.key === 'Escape') closeLightbox();
            if (e.key === 'ArrowLeft') navigateLightbox(-1);
            if (e.key === 'ArrowRight') navigateLightbox(1);
        });
    }
    
    function openLightbox(index) {
        currentIndex = visibleItems.findIndex(item => parseInt(item.dataset.index) === index);
        if (currentIndex === -1) currentIndex = 0;
        
        updateLightboxContent();
        document.getElementById('lightbox').classList.add('active');
        document.body.style.overflow = 'hidden';
    }
    
    function closeLightbox() {
        document.getElementById('lightbox').classList.remove('active');
        document.body.style.overflow = '';
    }
    
    function navigateLightbox(direction) {
        currentIndex = (currentIndex + direction + visibleItems.length) % visibleItems.length;
        updateLightboxContent();
    }
    
    function updateLightboxContent() {
        const item = visibleItems[currentIndex];
        const index = parseInt(item.dataset.index);
        const data = gridData[index];
        
        document.getElementById('lightboxImage').src = data.image;
        
        // Build details
        const details = document.getElementById('lightboxDetails');
        details.innerHTML = '';
        
        // Sampling section
        const samplingSection = createDetailSection('Sampling Parameters');
        const samplingFields = ['sampler_name', 'scheduler', 'steps', 'cfg', 'denoise', 'seed'];
        samplingFields.forEach(field => {
            if (data.params[field] !== undefined) {
                addDetailRow(samplingSection, formatFieldName(field), formatValue(data.params[field]));
            }
        });
        if (samplingSection.querySelectorAll('.detail-row').length > 0) {
            details.appendChild(samplingSection);
        }
        
        // Dimensions section
        const dimsSection = createDetailSection('Dimensions');
        const dimsFields = ['width', 'height', 'num_frames'];
        dimsFields.forEach(field => {
            if (data.params[field] !== undefined) {
                addDetailRow(dimsSection, formatFieldName(field), formatValue(data.params[field]));
            }
        });
        if (dimsSection.querySelectorAll('.detail-row').length > 0) {
            details.appendChild(dimsSection);
        }
        
        // Model section
        const modelSection = createDetailSection('Model Configuration');
        const modelFields = ['model', 'vae', 'clip', 'config_type'];
        modelFields.forEach(field => {
            if (data.params[field] !== undefined) {
                addDetailRow(modelSection, formatFieldName(field), formatValue(data.params[field]));
            }
        });
        if (modelSection.querySelectorAll('.detail-row').length > 0) {
            details.appendChild(modelSection);
        }
        
        // LoRA section - show if any LoRA-related fields exist
        if (data.params.lora_name || data.params.lora_names || data.params.lora_display || data.params.lora_strength !== undefined) {
            const loraSection = createDetailSection('LoRA');
            // Show display string first (combined info)
            if (data.params.lora_display) {
                addDetailRow(loraSection, 'Config', data.params.lora_display);
            }
            if (data.params.lora_name) {
                addDetailRow(loraSection, 'Name', formatValue(data.params.lora_name));
            }
            if (data.params.lora_strength !== undefined) {
                addDetailRow(loraSection, 'Strength', formatValue(data.params.lora_strength));
            }
            if (data.params.lora_names) {
                addDetailRow(loraSection, 'Names', data.params.lora_names);
            }
            if (data.params.lora_strengths) {
                addDetailRow(loraSection, 'Strengths', data.params.lora_strengths);
            }
            details.appendChild(loraSection);
        }
        
        // Shift parameters
        const shiftSection = createDetailSection('Shift Parameters');
        const shiftFields = ['lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift', 'hunyuan_shift', 'flux_guidance'];
        shiftFields.forEach(field => {
            if (data.params[field] !== undefined) {
                addDetailRow(shiftSection, formatFieldName(field), formatValue(data.params[field]));
            }
        });
        if (shiftSection.querySelectorAll('.detail-row').length > 0) {
            details.appendChild(shiftSection);
        }
        
        // Prompts
        if (data.params.prompt_positive) {
            const promptSection = document.createElement('div');
            promptSection.className = 'detail-section prompt-section';
            promptSection.innerHTML = '<h3>Positive Prompt</h3>';
            const promptText = document.createElement('div');
            promptText.className = 'prompt-text';
            promptText.textContent = data.params.prompt_positive;
            promptSection.appendChild(promptText);
            details.appendChild(promptSection);
        }
        
        if (data.params.prompt_negative) {
            const negPromptSection = document.createElement('div');
            negPromptSection.className = 'detail-section prompt-section';
            negPromptSection.innerHTML = '<h3>Negative Prompt</h3>';
            const negPromptText = document.createElement('div');
            negPromptText.className = 'prompt-text';
            negPromptText.textContent = data.params.prompt_negative;
            negPromptSection.appendChild(negPromptText);
            details.appendChild(negPromptSection);
        }
        
        // Counter
        const counter = document.createElement('div');
        counter.style.cssText = 'text-align: center; margin-top: 20px; color: var(--text-secondary); font-size: 0.85rem;';
        counter.textContent = (currentIndex + 1) + ' / ' + visibleItems.length;
        details.appendChild(counter);
    }
    
    function createDetailSection(title) {
        const section = document.createElement('div');
        section.className = 'detail-section';
        section.innerHTML = '<h3>' + title + '</h3>';
        return section;
    }
    
    function addDetailRow(section, label, value) {
        const row = document.createElement('div');
        row.className = 'detail-row';
        row.innerHTML = '<span class="detail-label">' + label + '</span><span class="detail-value">' + escapeHtml(value) + '</span>';
        section.appendChild(row);
    }
    
    // URL hash for shareable state
    function saveToHash() {
        const filters = {};
        document.querySelectorAll('#filters select').forEach(select => {
            if (select.value) {
                filters[select.dataset.field] = select.value;
            }
        });
        
        if (Object.keys(filters).length > 0) {
            window.location.hash = encodeURIComponent(JSON.stringify(filters));
        } else {
            window.location.hash = '';
        }
    }
    
    function loadFromHash() {
        if (!window.location.hash) return;
        
        try {
            const filters = JSON.parse(decodeURIComponent(window.location.hash.slice(1)));
            Object.entries(filters).forEach(([field, value]) => {
                const select = document.querySelector('#filter-' + field);
                if (select) select.value = value;
            });
            applyFilters();
        } catch (e) {
            console.warn('Invalid hash state');
        }
    }
    
    // Utilities
    function formatFieldName(field) {
        const labels = {
            'sampler_name': 'Sampler',
            'scheduler': 'Scheduler',
            'steps': 'Steps',
            'cfg': 'CFG',
            'denoise': 'Denoise',
            'width': 'Width',
            'height': 'Height',
            'seed': 'Seed',
            'model': 'Model',
            'vae': 'VAE',
            'clip': 'CLIP',
            'lora_name': 'LoRA',
            'lora_strength': 'LoRA Strength',
            'lora_names': 'LoRAs',
            'lora_strengths': 'LoRA Strengths',
            'lumina_shift': 'Lumina Shift',
            'qwen_shift': 'Qwen Shift',
            'wan_shift': 'WAN Shift',
            'wan22_shift': 'WAN 2.2 Shift',
            'hunyuan_shift': 'Hunyuan Shift',
            'flux_guidance': 'FLUX Guidance',
            'prompt_positive': 'Positive Prompt',
            'prompt_negative': 'Negative Prompt',
            'num_frames': 'Frames',
            'config_type': 'Config Type'
        };
        return labels[field] || field.replace(/_/g, ' ').replace(/\\b\\w/g, c => c.toUpperCase());
    }
    
    function formatValue(value) {
        if (value === null || value === undefined) return '';
        if (typeof value === 'number') {
            if (Number.isInteger(value)) return String(value);
            return value.toFixed(4).replace(/\\.?0+$/, '');
        }
        if (typeof value === 'string') {
            if (value.endsWith('.safetensors')) return value.slice(0, -12);
            if (value.length > 30) return value.slice(0, 27) + '...';
        }
        return String(value);
    }
    
    // Get CSS class for tag based on field type
    function getTagClass(field) {
        const classes = {
            'sampler_name': 'meta-tag-sampler',
            'scheduler': 'meta-tag-scheduler',
            'steps': 'meta-tag-steps',
            'cfg': 'meta-tag-cfg',
            'denoise': 'meta-tag-denoise',
            'seed': 'meta-tag-seed',
            'model': 'meta-tag-model',
            'lora_name': 'meta-tag-lora',
            'lora_names': 'meta-tag-lora',
            'lora_strength': 'meta-tag-lora',
            'lora_strengths': 'meta-tag-lora'
        };
        return classes[field] || 'meta-tag-default';
    }
    
    // Get label prefix for tag
    function getTagLabel(field) {
        const labels = {
            'sampler_name': 'Sampler: ',
            'scheduler': 'Scheduler: ',
            'steps': 'Steps: ',
            'cfg': 'CFG: ',
            'denoise': 'Denoise: ',
            'seed': 'Seed: ',
            'model': 'Model: ',
            'lora_name': 'LoRA: ',
            'lora_names': 'LoRAs: ',
            'lora_strength': 'Strength: ',
            'lora_strengths': 'Strengths: ',
            'width': 'W: ',
            'height': 'H: '
        };
        return labels[field] || '';
    }
    
    function buildLabel(params) {
        const parts = [];
        if (params.sampler_name) parts.push(params.sampler_name);
        if (params.scheduler) parts.push(params.scheduler);
        if (params.steps) parts.push(params.steps + 'st');
        if (params.cfg) parts.push('cfg' + formatValue(params.cfg));
        return parts.join(' | ') || 'Image';
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // ============ Image Comparison Selection ============
    let selectedForCompare = [];
    
    // Add compare toolbar (hidden initially, shown when selections made)
    document.addEventListener('DOMContentLoaded', function() {
        const toolbar = document.createElement('div');
        toolbar.id = 'compareToolbar';
        toolbar.className = 'compare-toolbar';
        toolbar.innerHTML = `
            <span class="selection-count">0 of 2 selected</span>
            <button class="btn btn-compare" id="startCompare" disabled>Compare Selected</button>
            <button class="btn btn-cancel" id="clearCompare">Clear Selection</button>
        `;
        document.body.appendChild(toolbar);
        
        document.getElementById('startCompare').addEventListener('click', openCompareModal);
        document.getElementById('clearCompare').addEventListener('click', clearCompareSelection);
        
        // Add compare modal
        const modal = document.createElement('div');
        modal.id = 'compareModal';
        modal.className = 'compare-modal';
        modal.innerHTML = `
            <div class="compare-modal-header">
                <h2>Image Comparison</h2>
                <button class="compare-modal-close" onclick="closeCompareModal()">&times;</button>
            </div>
            <div class="compare-container">
                <div class="compare-wrapper">
                    <div class="compare-image-container" id="compareContainer">
                        <img class="compare-image" id="compareImageBase" src="" alt="Image 1">
                        <div class="compare-image-overlay" id="compareOverlay">
                            <img id="compareImageOverlay" src="" alt="Image 2">
                        </div>
                        <div class="compare-slider" id="compareSlider"></div>
                    </div>
                    <div class="compare-labels">
                        <span class="compare-label" id="compareLabel1"></span>
                        <span class="compare-label" id="compareLabel2"></span>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        initCompareSlider();
    });
    
    // Toggle selection when checkbox is clicked
    function toggleCompareSelection(index, checkbox, gridItem) {
        const isSelected = selectedForCompare.includes(index);
        
        if (isSelected) {
            // Deselect
            selectedForCompare = selectedForCompare.filter(i => i !== index);
            checkbox.classList.remove('checked');
            checkbox.innerHTML = '';
            gridItem.classList.remove('selected-for-compare');
        } else if (selectedForCompare.length < 2) {
            // Select (max 2)
            selectedForCompare.push(index);
            checkbox.classList.add('checked');
            gridItem.classList.add('selected-for-compare');
        }
        
        // Update all checkbox numbers
        updateCheckboxNumbers();
        updateCompareToolbar();
    }
    
    function updateCheckboxNumbers() {
        // Clear all numbers first
        document.querySelectorAll('.compare-checkbox').forEach(cb => {
            if (!cb.classList.contains('checked')) {
                cb.innerHTML = '';
            }
        });
        
        // Add numbers to selected checkboxes
        selectedForCompare.forEach((idx, i) => {
            const item = document.querySelector(`.grid-item[data-index="${idx}"]`);
            if (item) {
                const cb = item.querySelector('.compare-checkbox');
                if (cb) {
                    cb.innerHTML = `<span class="check-number">${i + 1}</span>`;
                }
            }
        });
    }
    
    function updateCompareToolbar() {
        const toolbar = document.getElementById('compareToolbar');
        const btn = document.getElementById('startCompare');
        const countSpan = toolbar.querySelector('.selection-count');
        
        countSpan.textContent = `${selectedForCompare.length} of 2 selected`;
        btn.disabled = selectedForCompare.length !== 2;
        
        // Show/hide toolbar based on selection
        if (selectedForCompare.length > 0) {
            toolbar.classList.add('visible');
        } else {
            toolbar.classList.remove('visible');
        }
    }
    
    function clearCompareSelection() {
        selectedForCompare.forEach(idx => {
            const item = document.querySelector(`.grid-item[data-index="${idx}"]`);
            if (item) {
                item.classList.remove('selected-for-compare');
                const cb = item.querySelector('.compare-checkbox');
                if (cb) {
                    cb.classList.remove('checked');
                    cb.innerHTML = '';
                }
            }
        });
        selectedForCompare = [];
        updateCompareToolbar();
    }
    
    function openCompareModal() {
        if (selectedForCompare.length !== 2) return;
        
        const [idx1, idx2] = selectedForCompare;
        const data1 = gridData[idx1];
        const data2 = gridData[idx2];
        
        document.getElementById('compareImageBase').src = data1.image;
        document.getElementById('compareImageOverlay').src = data2.image;
        document.getElementById('compareLabel1').textContent = data1.label || 'Image 1';
        document.getElementById('compareLabel2').textContent = data2.label || 'Image 2';
        
        // Reset slider position
        const container = document.getElementById('compareContainer');
        const overlay = document.getElementById('compareOverlay');
        const slider = document.getElementById('compareSlider');
        
        // Wait for images to load
        const img1 = document.getElementById('compareImageBase');
        img1.onload = function() {
            const width = this.offsetWidth;
            overlay.style.width = (width / 2) + 'px';
            slider.style.left = (width / 2) + 'px';
        };
        
        document.getElementById('compareModal').classList.add('visible');
        document.body.style.overflow = 'hidden';
    }
    
    function closeCompareModal() {
        document.getElementById('compareModal').classList.remove('visible');
        document.body.style.overflow = '';
    }
    
    function initCompareSlider() {
        const slider = document.getElementById('compareSlider');
        const container = document.getElementById('compareContainer');
        const overlay = document.getElementById('compareOverlay');
        
        let isDragging = false;
        
        slider.addEventListener('mousedown', startDrag);
        slider.addEventListener('touchstart', startDrag, { passive: true });
        
        document.addEventListener('mousemove', drag);
        document.addEventListener('touchmove', drag, { passive: true });
        
        document.addEventListener('mouseup', stopDrag);
        document.addEventListener('touchend', stopDrag);
        
        function startDrag(e) {
            isDragging = true;
            e.preventDefault();
        }
        
        function drag(e) {
            if (!isDragging) return;
            
            const rect = container.getBoundingClientRect();
            let x = (e.touches ? e.touches[0].clientX : e.clientX) - rect.left;
            x = Math.max(0, Math.min(x, rect.width));
            
            slider.style.left = x + 'px';
            overlay.style.width = x + 'px';
        }
        
        function stopDrag() {
            isDragging = false;
        }
        
        // Also handle click on container to move slider
        container.addEventListener('click', function(e) {
            if (e.target === slider) return;
            const rect = container.getBoundingClientRect();
            let x = e.clientX - rect.left;
            x = Math.max(0, Math.min(x, rect.width));
            slider.style.left = x + 'px';
            overlay.style.width = x + 'px';
        });
    }
    
    // Close compare modal on Escape
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && document.getElementById('compareModal').classList.contains('visible')) {
            closeCompareModal();
        }
    });
    
    // Make closeCompareModal available globally
    window.closeCompareModal = closeCompareModal;
    window.toggleCompareMode = toggleCompareMode;
})();
"""


def generate_html_grid(
    images: List[Image.Image],
    labels: List[str],
    combinations: List[Dict],
    config: Dict[str, Any],
    title: str = "Model Comparison Grid",
    use_base64: bool = True,
    image_format: str = "JPEG",
    image_quality: int = 85,
    grid_image: Optional[Image.Image] = None,
) -> str:
    """
    Generate a self-contained HTML grid file.
    
    Args:
        images: List of PIL Images
        labels: List of string labels for each image
        combinations: List of combination dicts with parameters
        config: Config dict from the pipeline
        title: Title for the HTML page
        use_base64: If True, embed images as base64. If False, use relative paths.
        image_format: "PNG" or "JPEG"
        image_quality: JPEG quality (1-100)
        grid_image: Optional composed grid image (used for gallery thumbnail)
    
    Returns:
        Complete HTML string
    """
    if not images:
        return "<html><body><h1>No images to display</h1></body></html>"
    
    # Detect varying dimensions
    varying_dims = get_varying_dimensions(combinations, config)
    
    # Build grid data
    grid_data = []
    for idx, (img, label) in enumerate(zip(images, labels)):
        combo = combinations[idx] if idx < len(combinations) else {}
        
        # Convert image to base64
        if use_base64:
            img_data = f"data:image/{image_format.lower()};base64,{image_to_base64(img, image_format, image_quality)}"
        else:
            img_data = f"images/img_{idx:04d}.{image_format.lower()}"
        
        # Get parameters
        params = get_combo_params(combo)
        
        # Add model name if available
        model_idx = combo.get("model_index", 0)
        model_variations = config.get("model_variations", [])
        if model_idx < len(model_variations):
            model_entry = model_variations[model_idx]
            model_name = model_entry.get("display_name", model_entry.get("name", f"Model {model_idx + 1}"))
            # Clean up model name (remove .safetensors extension) to match filter options
            if model_name and model_name.endswith('.safetensors'):
                model_name = model_name[:-12]
            params["model"] = model_name
        
        # Add VAE name
        if "vae_name" in combo:
            vae_name = combo["vae_name"]
            # Clean up VAE name (remove .safetensors extension) to match filter options
            if vae_name and vae_name.endswith('.safetensors'):
                vae_name = vae_name[:-12]
            params["vae"] = vae_name
        
        # Add prompts - use per-image prompts from combo, not global first prompt
        # Each combo has its own prompt_positive and prompt_negative from the combination
        if "prompt_positive" in params and params["prompt_positive"]:
            # Already extracted from combo via get_combo_params
            pass
        elif combo.get("prompt_positive"):
            params["prompt_positive"] = combo.get("prompt_positive", "")
        
        if "prompt_negative" in params and params["prompt_negative"]:
            pass
        elif combo.get("prompt_negative"):
            params["prompt_negative"] = combo.get("prompt_negative", "")
        
        # Add prompt_index for filtering if available
        if combo.get("prompt_index"):
            params["prompt_index"] = combo.get("prompt_index")
        
        grid_data.append({
            "image": img_data,
            "label": label,
            "params": params
        })
    
    # Generate thumbnail for gallery (use the composed grid image if available)
    thumbnail_data = ""
    try:
        if grid_image is not None:
            # Use the actual composed grid as thumbnail - shows full comparison
            thumb_img = grid_image.copy()
            # Convert to RGB if needed (RGBA can cause JPEG issues)
            if thumb_img.mode == "RGBA":
                thumb_img = thumb_img.convert("RGB")
            # Scale to max 400px while maintaining aspect ratio
            thumb_img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            thumbnail_data = f"data:image/jpeg;base64,{image_to_base64(thumb_img, 'JPEG', 75)}"
            print(f"[HTMLGrid] Generated thumbnail from grid image: {len(thumbnail_data)} chars")
        elif images:
            # Fallback: use first image if no grid provided
            thumb_img = images[0].copy()
            if thumb_img.mode == "RGBA":
                thumb_img = thumb_img.convert("RGB")
            thumb_img.thumbnail((300, 300), Image.Resampling.LANCZOS)
            thumbnail_data = f"data:image/jpeg;base64,{image_to_base64(thumb_img, 'JPEG', 60)}"
            print(f"[HTMLGrid] Generated thumbnail from first image: {len(thumbnail_data)} chars")
    except Exception as e:
        print(f"[HTMLGrid] Error generating thumbnail: {e}")
        import traceback
        traceback.print_exc()
        # Try one more time with a simple approach
        try:
            if images:
                thumb_img = images[0].copy()
                if thumb_img.mode != "RGB":
                    thumb_img = thumb_img.convert("RGB")
                thumb_img.thumbnail((200, 200), Image.Resampling.LANCZOS)
                thumbnail_data = f"data:image/jpeg;base64,{image_to_base64(thumb_img, 'JPEG', 50)}"
                print(f"[HTMLGrid] Generated fallback thumbnail: {len(thumbnail_data)} chars")
        except Exception as e2:
            print(f"[HTMLGrid] Fallback thumbnail also failed: {e2}")
    
    # Metadata for gallery discovery
    grid_metadata = {
        "title": title,
        "created": datetime.now().isoformat(),
        "image_count": len(images),
        "thumbnail": thumbnail_data,
        "varying_dims": list(varying_dims.keys()),
    }
    
    # Generate HTML
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Signature for gallery discovery
    GRID_SIGNATURE = "comfyui-model-compare-grid"
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="generator" content="{GRID_SIGNATURE}">
    <title>{html.escape(title)}</title>
    <link rel="icon" type="image/svg+xml" href="/model-compare/static/images/logo.svg">
    <script type="application/json" id="model-compare-metadata">
{json.dumps(grid_metadata, ensure_ascii=False, indent=2)}
    </script>
    <style>
{CSS_TEMPLATE}
    </style>
</head>
<body>
    <!-- Top Navigation Header -->
    <header class="page-header" style="background: var(--bg-secondary); border-bottom: 1px solid var(--border); padding: 1rem 2rem; position: sticky; top: 0; z-index: 100; display: flex; justify-content: space-between; align-items: center;">
        <div class="header-left">
            <div class="header-branding">
                <h1 style="font-size: 1.5rem; font-weight: 700; color: var(--accent); margin-bottom: 0.25rem;">🎨 Model Compare</h1>
                <div class="header-tagline" style="font-size: 0.875rem; color: var(--text-secondary);">
                    Grid View •
                    <a href="/model-compare/gallery" style="color: var(--accent); text-decoration: none;">
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor" style="vertical-align: middle;">
                            <path d="M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z"/>
                        </svg>
                        Back to Gallery
                    </a>
                </div>
            </div>
        </div>
        <div class="header-right" style="display: flex; gap: 10px; align-items: center;">
            <button id="editGridBtn" class="btn-edit" style="padding: 8px 16px; background: var(--accent); color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z"/>
                </svg>
                Edit Grid
            </button>
            <button id="exportGridBtn" class="btn-export" style="padding: 8px 16px; background: var(--bg-card); color: var(--text-primary); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 14px; font-weight: 600; display: flex; align-items: center; gap: 6px;">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                    <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20M12,19L8,15H10.5V12H13.5V15H16L12,19Z"/>
                </svg>
                Export
            </button>
            <button id="themeToggle" class="theme-toggle" style="padding: 8px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 18px;">☀️</button>
        </div>
    </header>
    
    <div class="container">
        <header class="header">
            <div>
                <h1>{html.escape(title)}</h1>
                <div class="header-tagline">
                    Generated with 
                    <a href="https://github.com/tlennon-ie/comfyui-model-compare" target="_blank" rel="noopener">
                        <svg class="github-icon" viewBox="0 0 16 16" xmlns="http://www.w3.org/2000/svg">
                            <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/>
                        </svg>
                        ComfyUI Model Compare
                    </a>
                </div>
                <div class="stats">
                    <span class="stat">📊 Total: <strong id="statsTotal">{len(images)}</strong></span>
                    <span class="stat">👁️ Visible: <strong id="statsVisible">{len(images)}</strong></span>
                    <span class="stat">🕐 Generated: {timestamp}</span>
                </div>
            </div>
            <div class="header-controls">
                <button id="themeToggle2" class="theme-toggle">☀️ Light</button>
            </div>
        </header>
        
        <div class="filters" id="filters">
            <div class="filter-actions">
                <button class="btn btn-secondary" onclick="resetFilters()">Reset Filters</button>
            </div>
        </div>
        
        <div class="grid" id="grid"></div>
    </div>
    
    <!-- Lightbox -->
    <div class="lightbox" id="lightbox">
        <button class="lightbox-close" id="lightboxClose">&times;</button>
        <button class="lightbox-nav lightbox-prev" id="lightboxPrev">&#10094;</button>
        <button class="lightbox-nav lightbox-next" id="lightboxNext">&#10095;</button>
        <div class="lightbox-content">
            <div class="lightbox-image-container">
                <img class="lightbox-image" id="lightboxImage" src="" alt="Full size image">
            </div>
            <div class="lightbox-details" id="lightboxDetails"></div>
        </div>
    </div>
    
    <!-- Export Dropdown Menu -->
    <div id="exportMenu" class="export-menu" style="display: none; position: fixed; top: 60px; right: 100px; background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px; box-shadow: 0 4px 12px var(--shadow); z-index: 1000; min-width: 220px;">
        <div class="export-item" onclick="exportGrid('html')" style="padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--border);">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M12,17.56L16.07,16.43L16.62,10.33H9.38L9.2,8.3H16.8L17,6.31H7L7.56,12.32H14.45L14.22,14.9L12,15.5L9.78,14.9L9.64,13.24H7.64L7.93,16.43L12,17.56M4.07,3H19.93L18.5,19.2L12,21L5.5,19.2L4.07,3Z"/>
            </svg>
            <span>Export as HTML</span>
        </div>
        <div class="export-item" onclick="exportGrid('png')" style="padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--border);">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M8.5,13.5L11,16.5L14.5,12L19,18H5M21,19V5C21,3.89 20.1,3 19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19Z"/>
            </svg>
            <span>Export as PNG (Megagrid)</span>
        </div>
        <div class="export-item" onclick="exportGrid('jpeg')" style="padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--border);">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M8.5,13.5L11,16.5L14.5,12L19,18H5M21,19V5C21,3.89 20.1,3 19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19Z"/>
            </svg>
            <span>Export as JPEG</span>
        </div>
        <div class="export-item" onclick="exportGrid('pdf')" style="padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--border);">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z"/>
            </svg>
            <span>Export as PDF</span>
        </div>
        <div class="export-item" onclick="exportGrid('csv')" style="padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px; border-bottom: 1px solid var(--border);">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20M10,19H12V18H10V19M10,15H12V14H10V15M10,11H12V10H10V11Z"/>
            </svg>
            <span>Export as CSV</span>
        </div>
        <div class="export-item" onclick="exportGrid('json')" style="padding: 12px 16px; cursor: pointer; display: flex; align-items: center; gap: 10px;">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
                <path d="M5,3H7V5H5V10A2,2 0 0,1 3,12A2,2 0 0,1 5,14V19H7V21H5C3.93,20.73 3,20.1 3,19V15A2,2 0 0,0 1,13H0V11H1A2,2 0 0,0 3,9V5A2,2 0 0,1 5,3M19,3A2,2 0 0,1 21,5V9A2,2 0 0,0 23,11H24V13H23A2,2 0 0,0 21,15V19A2,2 0 0,1 19,21H17V19H19V14A2,2 0 0,1 21,12A2,2 0 0,1 19,10V5H17V3H19M12,15A1,1 0 0,1 13,16A1,1 0 0,1 12,17A1,1 0 0,1 11,16A1,1 0 0,1 12,15M8,15A1,1 0 0,1 9,16A1,1 0 0,1 8,17A1,1 0 0,1 7,16A1,1 0 0,1 8,15M16,15A1,1 0 0,1 17,16A1,1 0 0,1 16,17A1,1 0 0,1 15,16A1,1 0 0,1 16,15Z"/>
            </svg>
            <span>Export as JSON</span>
        </div>
    </div>

    <footer class="footer">
        Generated by ComfyUI Model Compare
    </footer>
    
    <script>
{JS_TEMPLATE.replace('__GRID_DATA__', json.dumps(grid_data, ensure_ascii=False)).replace('__VARYING_DIMS__', json.dumps(varying_dims, ensure_ascii=False))}
    
    // Edit Grid Button Handler
    document.getElementById('editGridBtn').addEventListener('click', function() {{
        // Get current page path and encode it
        const currentPath = window.location.pathname;
        const encodedPath = btoa(currentPath);
        window.location.href = `/model-compare/grid-editor?grid=${{encodedPath}}`;
    }});
    
    // Export Grid Button Handler
    document.getElementById('exportGridBtn').addEventListener('click', function(e) {{
        e.stopPropagation();
        const menu = document.getElementById('exportMenu');
        menu.style.display = menu.style.display === 'none' ? 'block' : 'none';
    }});
    
    // Close export menu when clicking outside
    document.addEventListener('click', function(e) {{
        const menu = document.getElementById('exportMenu');
        const btn = document.getElementById('exportGridBtn');
        if (!menu.contains(e.target) && e.target !== btn) {{
            menu.style.display = 'none';
        }}
    }});
    
    // Export Grid Function
    function exportGrid(format) {{
        const currentPath = window.location.pathname;
        const encodedPath = btoa(currentPath);
        
        // Hide menu
        document.getElementById('exportMenu').style.display = 'none';
        
        // Trigger export
        const exportUrl = `/model-compare/grid-builder/export?grid=${{encodedPath}}&format=${{format}}`;
        
        // For HTML, redirect to view the generated grid
        if (format === 'html') {{
            window.open(exportUrl, '_blank');
        }} else {{
            // For CSV/JSON, trigger download
            const link = document.createElement('a');
            link.href = exportUrl;
            link.download = `grid_export.${{format}}`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}
    }}
    
    // Sync both theme toggle buttons
    const toggle1 = document.getElementById('themeToggle');
    const toggle2 = document.getElementById('themeToggle2');
    
    function syncThemeButtons() {{
        const theme = localStorage.getItem('theme') || 'dark';
        const icon = theme === 'dark' ? '☀️' : '🌙';
        if (toggle1) toggle1.textContent = icon;
        if (toggle2) toggle2.textContent = icon + ' ' + (theme === 'dark' ? 'Light' : 'Dark');
    }}
    
    if (toggle1) {{
        toggle1.addEventListener('click', function() {{
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            syncThemeButtons();
        }});
    }}
    
    if (toggle2) {{
        toggle2.addEventListener('click', function() {{
            const currentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            syncThemeButtons();
        }});
    }}
    
    syncThemeButtons();
    </script>
</body>
</html>"""
    
    return html_content


def save_html_grid(
    html_content: str,
    output_path: str,
    images: List[Image.Image] = None,
    use_base64: bool = True,
    image_format: str = "JPEG",
) -> str:
    """
    Save HTML grid to file, optionally with separate image folder.
    
    Args:
        html_content: Generated HTML string
        output_path: Path to save HTML file
        images: List of PIL images (only needed if use_base64=False)
        use_base64: Whether images are embedded
        image_format: Image format for separate files
    
    Returns:
        Path to saved HTML file
    """
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    # Save HTML
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Save images separately if not using base64
    if not use_base64 and images:
        img_dir = output_path.rsplit('.', 1)[0] + "_images"
        os.makedirs(img_dir, exist_ok=True)
        
        for idx, img in enumerate(images):
            img_path = os.path.join(img_dir, f"img_{idx:04d}.{image_format.lower()}")
            if image_format.upper() == "JPEG":
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                img.save(img_path, format="JPEG", quality=85)
            else:
                img.save(img_path, format="PNG")
    
    return output_path


def generate_nested_html_grid(
    images,  # Can be List[Image.Image] or List[GridImage]
    row_hierarchy: List[str],
    col_hierarchy: List[str],
    title: str = "Grid Comparison",
    styling: Dict[str, Any] = None,
) -> str:
    """
    Generate HTML grid with nested row/column hierarchies.
    
    Handles both PIL Images and GridImage objects from grid_parser.
    
    Args:
        images: List of PIL Images or GridImage objects
        row_hierarchy: List of field names for row hierarchy
        col_hierarchy: List of field names for column hierarchy
        title: Grid title
        styling: Optional styling configuration
    
    Returns:
        Complete HTML string
    """
    # Import here to avoid circular dependency
    from .grid_parser import GridImage
    
    # Check if we have GridImage objects or PIL Images
    if images and hasattr(images[0], 'image_data'):
        # We have GridImage objects - convert them
        pil_images = []
        labels = []
        combinations = []
        
        for grid_img in images:
            # Convert base64 image_data to PIL Image
            if grid_img.image_data:
                import base64
                image_bytes = base64.b64decode(grid_img.image_data.split(',')[1] if ',' in grid_img.image_data else grid_img.image_data)
                pil_img = Image.open(io.BytesIO(image_bytes))
                pil_images.append(pil_img)
            else:
                # Create placeholder image
                pil_images.append(Image.new('RGB', (256, 256), color='gray'))
            
            labels.append(grid_img.label)
            combinations.append(grid_img.params)
    else:
        # We have PIL Images already
        pil_images = images
        labels = [f"Image {i+1}" for i in range(len(images))]
        combinations = [{} for _ in images]
    
    # Build config
    config = {
        "row_hierarchy": row_hierarchy,
        "col_hierarchy": col_hierarchy,
    }
    
    # Apply styling if provided
    if styling:
        config.update(styling)
    
    # Delegate to existing function
    return generate_html_grid(
        images=pil_images,
        labels=labels,
        combinations=combinations,
        config=config,
        title=title,
        use_base64=True,
        image_format="JPEG",
        image_quality=85,
    )
