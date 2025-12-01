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


def get_varying_dimensions(combinations: List[Dict]) -> Dict[str, List[Any]]:
    """
    Analyze combinations to find dimensions with multiple unique values.
    Returns dict of dimension_name -> sorted list of unique values.
    """
    if not combinations:
        return {}
    
    # Fields to check for variations
    check_fields = [
        'sampler_name', 'scheduler', 'steps', 'cfg', 'denoise',
        'width', 'height', 'seed', 'model', 'vae', 'clip',
        'lora_name', 'lora_strength', 'lora_names', 'lora_strengths',
        'lumina_shift', 'qwen_shift', 'wan_shift', 'wan22_shift',
        'hunyuan_shift', 'flux_guidance', 'prompt_positive', 'prompt_negative'
    ]
    
    field_values = {f: set() for f in check_fields}
    
    for combo in combinations:
        # Check _sampling_override first, then combo itself
        override = combo.get('_sampling_override', {})
        
        for field in check_fields:
            value = override.get(field, combo.get(field))
            if value is not None:
                # Normalize to hashable
                if isinstance(value, (list, tuple)):
                    value = str(value)
                field_values[field].add(value)
    
    # Return only fields with >1 unique value
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
        'lora_name', 'lora_strength', 'lora_names', 'lora_strengths',
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
    object-fit: cover;
    display: block;
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
}

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
            
            // Image
            const img = document.createElement('img');
            img.src = item.image;
            img.alt = item.label || 'Image ' + (index + 1);
            img.loading = 'lazy';
            
            // Info section
            const info = document.createElement('div');
            info.className = 'grid-item-info';
            
            const label = document.createElement('div');
            label.className = 'grid-item-label';
            label.textContent = item.label || buildLabel(item.params);
            
            const meta = document.createElement('div');
            meta.className = 'grid-item-meta';
            
            // Add key parameter tags
            const keyParams = ['sampler_name', 'scheduler', 'steps', 'cfg'];
            keyParams.forEach(param => {
                if (item.params[param] !== undefined) {
                    const tag = document.createElement('span');
                    tag.className = 'meta-tag';
                    tag.textContent = formatValue(item.params[param]);
                    meta.appendChild(tag);
                }
            });
            
            info.appendChild(label);
            info.appendChild(meta);
            div.appendChild(img);
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
        
        // LoRA section
        if (data.params.lora_name || data.params.lora_names) {
            const loraSection = createDetailSection('LoRA');
            if (data.params.lora_name) {
                addDetailRow(loraSection, 'Name', formatValue(data.params.lora_name));
            }
            if (data.params.lora_strength) {
                addDetailRow(loraSection, 'Strength', formatValue(data.params.lora_strength));
            }
            if (data.params.lora_names) {
                addDetailRow(loraSection, 'Names', formatValue(data.params.lora_names));
            }
            if (data.params.lora_strengths) {
                addDetailRow(loraSection, 'Strengths', formatValue(data.params.lora_strengths));
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
    
    Returns:
        Complete HTML string
    """
    if not images:
        return "<html><body><h1>No images to display</h1></body></html>"
    
    # Detect varying dimensions
    varying_dims = get_varying_dimensions(combinations)
    
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
            params["model"] = model_entry.get("display_name", model_entry.get("name", f"Model {model_idx + 1}"))
        
        # Add VAE name
        if "vae_name" in combo:
            params["vae"] = combo["vae_name"]
        
        # Add prompts from config
        prompt_variations = config.get("prompt_variations", [])
        if prompt_variations:
            params["prompt_positive"] = prompt_variations[0].get("positive", "")
            params["prompt_negative"] = prompt_variations[0].get("negative", "")
        
        grid_data.append({
            "image": img_data,
            "label": label,
            "params": params
        })
    
    # Generate HTML
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>
{CSS_TEMPLATE}
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div>
                <h1>{html.escape(title)}</h1>
                <div class="stats">
                    <span class="stat">📊 Total: <strong id="statsTotal">{len(images)}</strong></span>
                    <span class="stat">👁️ Visible: <strong id="statsVisible">{len(images)}</strong></span>
                    <span class="stat">🕐 Generated: {timestamp}</span>
                </div>
            </div>
            <div class="header-controls">
                <button id="themeToggle" class="theme-toggle">☀️ Light</button>
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
    
    <footer class="footer">
        Generated by ComfyUI Model Compare
    </footer>
    
    <script>
{JS_TEMPLATE.replace('__GRID_DATA__', json.dumps(grid_data, ensure_ascii=False)).replace('__VARYING_DIMS__', json.dumps(varying_dims, ensure_ascii=False))}
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
