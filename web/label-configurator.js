/**
 * Label Configurator
 * 
 * Interactive UI for editing grid titles, headers, and cell labels.
 * Supports variable interpolation using {field_name} syntax.
 */

class LabelConfigurator {
    constructor(containerId, gridConfig, onUpdate) {
        this.containerId = containerId;
        this.gridConfig = gridConfig;
        this.onUpdate = onUpdate;
        this.labels = this.extractLabels(gridConfig);
        
        this.render();
    }
    
    /**
     * Extract all editable labels from grid configuration
     */
    extractLabels(config) {
        return {
            mainTitle: config.title || "Grid Comparison",
            rowHeaders: config.row_hierarchy || [],
            colHeaders: config.col_hierarchy || [],
            cellPrefix: config.cell_label_prefix || "",
            cellSuffix: config.cell_label_suffix || "",
            showFieldNames: config.show_field_names !== false
        };
    }
    
    /**
     * Get available fields for variable interpolation
     */
    getAvailableFields() {
        const fields = new Set();
        
        // Collect from row and column hierarchies
        [...this.labels.rowHeaders, ...this.labels.colHeaders].forEach(field => {
            if (field) fields.add(field);
        });
        
        // Collect from image params
        if (this.gridConfig.images) {
            this.gridConfig.images.forEach(img => {
                Object.keys(img.params || {}).forEach(key => fields.add(key));
            });
        }
        
        return Array.from(fields).sort();
    }
    
    /**
     * Render the label configurator UI
     */
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('Label configurator container not found:', this.containerId);
            return;
        }
        
        const availableFields = this.getAvailableFields();
        
        container.innerHTML = `
            <div class="label-configurator">
                <div class="config-header">
                    <h3>📝 Labels & Titles</h3>
                    <p class="help-text">Customize grid titles, headers, and labels. Use {field_name} for variables.</p>
                </div>
                
                <div class="config-sections">
                    <!-- Main Title -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">🏷️</span>
                            Grid Title
                        </label>
                        <input 
                            type="text" 
                            id="mainTitle" 
                            value="${this.escapeHtml(this.labels.mainTitle)}"
                            class="input-text"
                            placeholder="Grid Comparison"
                        >
                        <div class="field-hint">
                            Example: {model} vs {sampler} Comparison
                        </div>
                    </div>
                    
                    <!-- Row Headers -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">📊</span>
                            Row Headers
                            <span class="badge">${this.labels.rowHeaders.length} fields</span>
                        </label>
                        <div id="rowHeadersList" class="header-list">
                            ${this.renderHeaderList(this.labels.rowHeaders, 'row')}
                        </div>
                    </div>
                    
                    <!-- Column Headers -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">📊</span>
                            Column Headers
                            <span class="badge">${this.labels.colHeaders.length} fields</span>
                        </label>
                        <div id="colHeadersList" class="header-list">
                            ${this.renderHeaderList(this.labels.colHeaders, 'col')}
                        </div>
                    </div>
                    
                    <!-- Cell Labels -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">🔤</span>
                            Cell Labels
                        </label>
                        
                        <div class="cell-label-config">
                            <div class="input-group">
                                <label class="input-label">Prefix</label>
                                <input 
                                    type="text" 
                                    id="cellPrefix" 
                                    value="${this.escapeHtml(this.labels.cellPrefix)}"
                                    class="input-text"
                                    placeholder="(optional)"
                                >
                            </div>
                            
                            <div class="input-group">
                                <label class="input-label">Suffix</label>
                                <input 
                                    type="text" 
                                    id="cellSuffix" 
                                    value="${this.escapeHtml(this.labels.cellSuffix)}"
                                    class="input-text"
                                    placeholder="(optional)"
                                >
                            </div>
                            
                            <label class="checkbox-label">
                                <input 
                                    type="checkbox" 
                                    id="showFieldNames"
                                    ${this.labels.showFieldNames ? 'checked' : ''}
                                >
                                <span>Show parameter names in cell labels</span>
                            </label>
                        </div>
                        
                        <div class="field-hint">
                            Preview: ${this.getCellLabelPreview()}
                        </div>
                    </div>
                    
                    <!-- Available Fields Reference -->
                    <div class="config-section collapsible">
                        <button class="section-toggle" onclick="this.parentElement.classList.toggle('expanded')">
                            <span class="label-icon">💡</span>
                            Available Variables
                            <span class="toggle-icon">▼</span>
                        </button>
                        <div class="section-content">
                            <div class="variable-chips">
                                ${availableFields.map(field => `
                                    <button class="variable-chip" onclick="labelConfigurator.insertVariable('${field}')">
                                        {${field}}
                                    </button>
                                `).join('')}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="config-actions">
                    <button class="btn btn-secondary" onclick="labelConfigurator.reset()">
                        Reset to Defaults
                    </button>
                    <button class="btn btn-primary" onclick="labelConfigurator.apply()">
                        Apply Changes
                    </button>
                </div>
            </div>
        `;
        
        this.attachEventListeners();
    }
    
    /**
     * Render list of header fields with edit capability
     */
    renderHeaderList(headers, type) {
        if (!headers || headers.length === 0) {
            return '<div class="empty-list">No headers configured</div>';
        }
        
        return headers.map((field, index) => `
            <div class="header-item" data-index="${index}" data-type="${type}">
                <span class="header-order">${index + 1}</span>
                <input 
                    type="text" 
                    value="${this.escapeHtml(field)}"
                    class="header-input"
                    data-original="${this.escapeHtml(field)}"
                    placeholder="Field name or {variable}"
                >
                <div class="header-actions">
                    <button class="btn-icon-small" title="Use original field name" onclick="labelConfigurator.resetHeaderField(${index}, '${type}')">
                        ↻
                    </button>
                </div>
            </div>
        `).join('');
    }
    
    /**
     * Get preview of how cell labels will appear
     */
    getCellLabelPreview() {
        const prefix = document.getElementById('cellPrefix')?.value || this.labels.cellPrefix;
        const suffix = document.getElementById('cellSuffix')?.value || this.labels.cellSuffix;
        const showNames = document.getElementById('showFieldNames')?.checked ?? this.labels.showFieldNames;
        
        let preview = prefix;
        if (showNames) {
            preview += '{field_name}: {value}';
        } else {
            preview += '{value}';
        }
        preview += suffix;
        
        return preview || '(no customization)';
    }
    
    /**
     * Attach event listeners for live updates
     */
    attachEventListeners() {
        // Live preview updates
        ['mainTitle', 'cellPrefix', 'cellSuffix', 'showFieldNames'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.updatePreview());
                element.addEventListener('change', () => this.updatePreview());
            }
        });
        
        // Header field updates
        document.querySelectorAll('.header-input').forEach(input => {
            input.addEventListener('input', () => {
                input.classList.add('modified');
            });
        });
    }
    
    /**
     * Update live preview
     */
    updatePreview() {
        const previewEl = document.querySelector('.config-section:nth-child(4) .field-hint');
        if (previewEl) {
            previewEl.textContent = 'Preview: ' + this.getCellLabelPreview();
        }
    }
    
    /**
     * Insert variable at cursor position in focused input
     */
    insertVariable(fieldName) {
        const focused = document.activeElement;
        if (focused && (focused.tagName === 'INPUT' || focused.tagName === 'TEXTAREA')) {
            const start = focused.selectionStart;
            const end = focused.selectionEnd;
            const text = focused.value;
            const variable = `{${fieldName}}`;
            
            focused.value = text.substring(0, start) + variable + text.substring(end);
            focused.selectionStart = focused.selectionEnd = start + variable.length;
            focused.focus();
            
            // Trigger update
            focused.dispatchEvent(new Event('input'));
        }
    }
    
    /**
     * Reset a single header field to original value
     */
    resetHeaderField(index, type) {
        const input = document.querySelector(`.header-item[data-index="${index}"][data-type="${type}"] .header-input`);
        if (input) {
            input.value = input.dataset.original;
            input.classList.remove('modified');
        }
    }
    
    /**
     * Reset all labels to defaults
     */
    reset() {
        if (!confirm('Reset all label customizations to defaults?')) {
            return;
        }
        
        this.labels = this.extractLabels(this.gridConfig);
        this.render();
    }
    
    /**
     * Apply label changes
     */
    apply() {
        // Collect all label changes
        const updates = {
            title: document.getElementById('mainTitle')?.value || this.labels.mainTitle,
            cell_label_prefix: document.getElementById('cellPrefix')?.value || '',
            cell_label_suffix: document.getElementById('cellSuffix')?.value || '',
            show_field_names: document.getElementById('showFieldNames')?.checked ?? true,
            row_header_labels: this.collectHeaderLabels('row'),
            col_header_labels: this.collectHeaderLabels('col')
        };
        
        // Validate
        if (!updates.title.trim()) {
            alert('Grid title cannot be empty');
            return;
        }
        
        // Apply callback
        if (this.onUpdate) {
            this.onUpdate(updates);
        }
        
        console.log('Label configuration applied:', updates);
    }
    
    /**
     * Collect header labels from inputs
     */
    collectHeaderLabels(type) {
        const labels = [];
        document.querySelectorAll(`.header-item[data-type="${type}"] .header-input`).forEach(input => {
            labels.push(input.value.trim());
        });
        return labels;
    }
    
    /**
     * Escape HTML entities
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
}

/**
 * CSS Styles for Label Configurator
 */
const LABEL_CONFIGURATOR_CSS = `
.label-configurator {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.config-header {
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 2px solid #e0e0e0;
}

.config-header h3 {
    font-size: 24px;
    margin-bottom: 8px;
    color: #222;
}

.help-text {
    font-size: 14px;
    color: #666;
    margin: 0;
}

.config-sections {
    display: flex;
    flex-direction: column;
    gap: 24px;
}

.config-section {
    padding: 20px;
    background: #f8f9fa;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
}

.section-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 16px;
    font-weight: 600;
    color: #333;
    margin-bottom: 12px;
}

.label-icon {
    font-size: 20px;
}

.badge {
    display: inline-block;
    padding: 2px 8px;
    background: #e3f2fd;
    color: #1976d2;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 500;
    margin-left: auto;
}

.input-text {
    width: 100%;
    padding: 10px 12px;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
    font-family: inherit;
    transition: border-color 0.2s;
}

.input-text:focus {
    outline: none;
    border-color: #4a9eff;
}

.field-hint {
    margin-top: 8px;
    font-size: 13px;
    color: #666;
    font-style: italic;
}

.header-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.header-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px;
    background: white;
    border-radius: 6px;
    border: 1px solid #e0e0e0;
}

.header-order {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    background: #e3f2fd;
    color: #1976d2;
    border-radius: 50%;
    font-size: 13px;
    font-weight: 600;
    flex-shrink: 0;
}

.header-input {
    flex: 1;
    padding: 8px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
    font-family: 'Consolas', 'Monaco', monospace;
}

.header-input.modified {
    border-color: #ff9800;
    background: #fff3e0;
}

.header-input:focus {
    outline: none;
    border-color: #4a9eff;
}

.header-actions {
    display: flex;
    gap: 4px;
}

.btn-icon-small {
    width: 28px;
    height: 28px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #f5f5f5;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-icon-small:hover {
    background: #e0e0e0;
    border-color: #bbb;
}

.empty-list {
    padding: 16px;
    text-align: center;
    color: #999;
    font-style: italic;
}

.cell-label-config {
    display: flex;
    flex-direction: column;
    gap: 16px;
}

.input-group {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.input-label {
    font-size: 13px;
    font-weight: 600;
    color: #555;
}

.checkbox-label {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    color: #333;
    cursor: pointer;
    user-select: none;
}

.checkbox-label input[type="checkbox"] {
    width: 18px;
    height: 18px;
    cursor: pointer;
}

.config-section.collapsible {
    padding: 0;
    background: transparent;
    border: none;
}

.section-toggle {
    width: 100%;
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 16px 20px;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    font-size: 16px;
    font-weight: 600;
    color: #333;
    cursor: pointer;
    transition: all 0.2s;
}

.section-toggle:hover {
    background: #e8e9ea;
}

.toggle-icon {
    margin-left: auto;
    transition: transform 0.3s;
}

.collapsible.expanded .toggle-icon {
    transform: rotate(180deg);
}

.section-content {
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.3s ease-out;
}

.collapsible.expanded .section-content {
    max-height: 500px;
    padding: 16px 20px;
    background: #f8f9fa;
    border: 1px solid #e0e0e0;
    border-top: none;
    border-radius: 0 0 8px 8px;
}

.variable-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.variable-chip {
    padding: 6px 12px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 16px;
    font-size: 13px;
    font-family: 'Consolas', 'Monaco', monospace;
    color: #1976d2;
    cursor: pointer;
    transition: all 0.2s;
}

.variable-chip:hover {
    background: #e3f2fd;
    border-color: #1976d2;
}

.config-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
    padding-top: 20px;
    border-top: 2px solid #e0e0e0;
}

.btn {
    padding: 10px 24px;
    border: none;
    border-radius: 6px;
    font-size: 15px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-primary {
    background: #4a9eff;
    color: white;
}

.btn-primary:hover {
    background: #3a8eef;
}

.btn-secondary {
    background: #f5f5f5;
    color: #333;
    border: 1px solid #ddd;
}

.btn-secondary:hover {
    background: #e5e5e5;
}
`;

// Global reference for onclick handlers
let labelConfigurator = null;
