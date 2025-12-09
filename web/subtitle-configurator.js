/**
 * Subtitle Configurator
 * 
 * Interactive UI for configuring which parameters display in cell subtitles,
 * their order, and formatting options.
 */

class SubtitleConfigurator {
    constructor(containerId, gridConfig, onUpdate) {
        this.containerId = containerId;
        this.gridConfig = gridConfig;
        this.onUpdate = onUpdate;
        this.config = this.extractConfig(gridConfig);
        
        this.render();
    }
    
    /**
     * Extract subtitle configuration from grid config
     */
    extractConfig(config) {
        return {
            enabled: config.show_subtitles !== false,
            fields: config.subtitle_fields || this.getDefaultFields(),
            showFieldNames: config.subtitle_show_names !== false,
            separator: config.subtitle_separator || ' | ',
            maxFields: config.subtitle_max_fields || 5
        };
    }
    
    /**
     * Get default subtitle fields from grid
     */
    getDefaultFields() {
        if (!this.gridConfig.images || this.gridConfig.images.length === 0) {
            return [];
        }
        
        // Get all unique fields from images
        const allFields = new Set();
        this.gridConfig.images.forEach(img => {
            Object.keys(img.params || {}).forEach(key => allFields.add(key));
        });
        
        // Filter out fields used in hierarchy
        const hierarchyFields = new Set([
            ...(this.gridConfig.row_hierarchy || []),
            ...(this.gridConfig.col_hierarchy || [])
        ]);
        
        return Array.from(allFields)
            .filter(field => !hierarchyFields.has(field))
            .slice(0, 5); // Default to first 5 non-hierarchy fields
    }
    
    /**
     * Get all available fields
     */
    getAvailableFields() {
        if (!this.gridConfig.images || this.gridConfig.images.length === 0) {
            return [];
        }
        
        const fields = new Set();
        this.gridConfig.images.forEach(img => {
            Object.keys(img.params || {}).forEach(key => fields.add(key));
        });
        
        return Array.from(fields).sort();
    }
    
    /**
     * Render the subtitle configurator UI
     */
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('Subtitle configurator container not found:', this.containerId);
            return;
        }
        
        const availableFields = this.getAvailableFields();
        const selectedFields = this.config.fields;
        const unselectedFields = availableFields.filter(f => !selectedFields.includes(f));
        
        container.innerHTML = `
            <div class="subtitle-configurator">
                <div class="config-header">
                    <h3>🔤 Cell Subtitles</h3>
                    <p class="help-text">Choose which parameters appear in cell subtitles and configure their display.</p>
                </div>
                
                <div class="config-sections">
                    <!-- Enable/Disable -->
                    <div class="config-section">
                        <label class="checkbox-label large">
                            <input 
                                type="checkbox" 
                                id="subtitlesEnabled"
                                ${this.config.enabled ? 'checked' : ''}
                                onchange="subtitleConfigurator.toggleSubtitles(this.checked)"
                            >
                            <span>
                                <strong>Show parameter subtitles in cells</strong>
                                <small>Display additional parameters below each image</small>
                            </span>
                        </label>
                    </div>
                    
                    <div id="subtitleOptions" ${!this.config.enabled ? 'style="display:none;"' : ''}>
                        <!-- Field Selection -->
                        <div class="config-section">
                            <label class="section-label">
                                <span class="label-icon">📋</span>
                                Selected Fields
                                <span class="badge">${selectedFields.length} of ${this.config.maxFields}</span>
                            </label>
                            <p class="section-desc">Drag to reorder. Fields display in this order.</p>
                            
                            <div id="selectedFieldsList" class="field-list sortable">
                                ${this.renderSelectedFields(selectedFields)}
                            </div>
                            
                            ${selectedFields.length === 0 ? '<div class="empty-message">No fields selected. Add fields from available list below.</div>' : ''}
                        </div>
                        
                        <!-- Available Fields -->
                        <div class="config-section">
                            <label class="section-label">
                                <span class="label-icon">➕</span>
                                Available Fields
                                <span class="badge">${unselectedFields.length} available</span>
                            </label>
                            
                            <div id="availableFieldsList" class="field-list">
                                ${this.renderAvailableFields(unselectedFields)}
                            </div>
                            
                            ${unselectedFields.length === 0 ? '<div class="empty-message">All fields are selected or in use by hierarchy.</div>' : ''}
                        </div>
                        
                        <!-- Display Options -->
                        <div class="config-section">
                            <label class="section-label">
                                <span class="label-icon">⚙️</span>
                                Display Options
                            </label>
                            
                            <div class="options-grid">
                                <div class="option-item">
                                    <label class="checkbox-label">
                                        <input 
                                            type="checkbox" 
                                            id="showFieldNames"
                                            ${this.config.showFieldNames ? 'checked' : ''}
                                        >
                                        <span>Show field names (e.g., "Steps: 20")</span>
                                    </label>
                                </div>
                                
                                <div class="option-item">
                                    <label class="input-label">Separator</label>
                                    <select id="separatorSelect" class="select-input">
                                        <option value=" | " ${this.config.separator === ' | ' ? 'selected' : ''}>Pipe ( | )</option>
                                        <option value=" • " ${this.config.separator === ' • ' ? 'selected' : ''}>Bullet ( • )</option>
                                        <option value=", " ${this.config.separator === ', ' ? 'selected' : ''}>Comma ( , )</option>
                                        <option value=" · " ${this.config.separator === ' · ' ? 'selected' : ''}>Middle Dot ( · )</option>
                                        <option value=" / " ${this.config.separator === ' / ' ? 'selected' : ''}>Slash ( / )</option>
                                        <option value="\\n" ${this.config.separator === '\\n' ? 'selected' : ''}>New Line</option>
                                    </select>
                                </div>
                                
                                <div class="option-item">
                                    <label class="input-label">Max Fields</label>
                                    <input 
                                        type="number" 
                                        id="maxFields" 
                                        value="${this.config.maxFields}"
                                        min="1"
                                        max="20"
                                        class="input-number"
                                    >
                                </div>
                            </div>
                        </div>
                        
                        <!-- Preview -->
                        <div class="config-section preview-section">
                            <label class="section-label">
                                <span class="label-icon">👁️</span>
                                Preview
                            </label>
                            <div class="subtitle-preview">
                                ${this.generatePreview()}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="config-actions">
                    <button class="btn btn-secondary" onclick="subtitleConfigurator.reset()">
                        Reset to Defaults
                    </button>
                    <button class="btn btn-primary" onclick="subtitleConfigurator.apply()">
                        Apply Changes
                    </button>
                </div>
            </div>
        `;
        
        this.attachEventListeners();
        this.setupDragAndDrop();
    }
    
    /**
     * Render selected fields list
     */
    renderSelectedFields(fields) {
        return fields.map((field, index) => `
            <div class="field-item selected" draggable="true" data-field="${this.escapeAttr(field)}" data-index="${index}">
                <span class="drag-handle">⋮⋮</span>
                <span class="field-name">${this.escapeHtml(field)}</span>
                <span class="field-badge">${index + 1}</span>
                <button class="btn-remove" onclick="subtitleConfigurator.removeField('${this.escapeAttr(field)}')" title="Remove">
                    ✕
                </button>
            </div>
        `).join('');
    }
    
    /**
     * Render available fields list
     */
    renderAvailableFields(fields) {
        return fields.map(field => `
            <div class="field-item available" data-field="${this.escapeAttr(field)}">
                <span class="field-name">${this.escapeHtml(field)}</span>
                <button class="btn-add" onclick="subtitleConfigurator.addField('${this.escapeAttr(field)}')" title="Add">
                    ➕
                </button>
            </div>
        `).join('');
    }
    
    /**
     * Generate subtitle preview
     */
    generatePreview() {
        if (!this.config.enabled || this.config.fields.length === 0) {
            return '<div class="preview-empty">No subtitles will be displayed</div>';
        }
        
        const showNames = document.getElementById('showFieldNames')?.checked ?? this.config.showFieldNames;
        const separator = document.getElementById('separatorSelect')?.value || this.config.separator;
        const displaySeparator = separator === '\\n' ? '<br>' : separator;
        
        // Generate sample values
        const parts = this.config.fields.map(field => {
            const sampleValue = this.getSampleValue(field);
            return showNames ? `${field}: ${sampleValue}` : sampleValue;
        });
        
        return `<div class="preview-text">${parts.join(displaySeparator)}</div>`;
    }
    
    /**
     * Get sample value for a field
     */
    getSampleValue(field) {
        if (!this.gridConfig.images || this.gridConfig.images.length === 0) {
            return 'value';
        }
        
        // Get first non-null value for this field
        for (const img of this.gridConfig.images) {
            const value = img.params?.[field];
            if (value !== null && value !== undefined) {
                return String(value);
            }
        }
        
        return 'value';
    }
    
    /**
     * Toggle subtitles on/off
     */
    toggleSubtitles(enabled) {
        this.config.enabled = enabled;
        const options = document.getElementById('subtitleOptions');
        if (options) {
            options.style.display = enabled ? 'block' : 'none';
        }
    }
    
    /**
     * Add field to selected list
     */
    addField(field) {
        if (this.config.fields.length >= this.config.maxFields) {
            alert(`Maximum ${this.config.maxFields} fields allowed. Remove a field first or increase the max.`);
            return;
        }
        
        if (!this.config.fields.includes(field)) {
            this.config.fields.push(field);
            this.render();
        }
    }
    
    /**
     * Remove field from selected list
     */
    removeField(field) {
        this.config.fields = this.config.fields.filter(f => f !== field);
        this.render();
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Live preview updates
        ['showFieldNames', 'separatorSelect', 'maxFields'].forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('change', () => this.updatePreview());
            }
        });
    }
    
    /**
     * Setup drag and drop for field reordering
     */
    setupDragAndDrop() {
        let draggedElement = null;
        
        const selectedList = document.getElementById('selectedFieldsList');
        if (!selectedList) return;
        
        selectedList.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('field-item')) {
                draggedElement = e.target;
                e.target.classList.add('dragging');
            }
        });
        
        selectedList.addEventListener('dragend', (e) => {
            if (e.target.classList.contains('field-item')) {
                e.target.classList.remove('dragging');
            }
        });
        
        selectedList.addEventListener('dragover', (e) => {
            e.preventDefault();
            const afterElement = this.getDragAfterElement(selectedList, e.clientY);
            if (afterElement == null) {
                selectedList.appendChild(draggedElement);
            } else {
                selectedList.insertBefore(draggedElement, afterElement);
            }
        });
        
        selectedList.addEventListener('drop', (e) => {
            e.preventDefault();
            this.updateFieldOrder();
        });
    }
    
    /**
     * Get element after drag position
     */
    getDragAfterElement(container, y) {
        const draggableElements = [...container.querySelectorAll('.field-item:not(.dragging)')];
        
        return draggableElements.reduce((closest, child) => {
            const box = child.getBoundingClientRect();
            const offset = y - box.top - box.height / 2;
            
            if (offset < 0 && offset > closest.offset) {
                return { offset: offset, element: child };
            } else {
                return closest;
            }
        }, { offset: Number.NEGATIVE_INFINITY }).element;
    }
    
    /**
     * Update field order based on DOM
     */
    updateFieldOrder() {
        const fieldElements = document.querySelectorAll('#selectedFieldsList .field-item');
        this.config.fields = Array.from(fieldElements).map(el => el.dataset.field);
        this.render();
    }
    
    /**
     * Update preview
     */
    updatePreview() {
        const previewEl = document.querySelector('.subtitle-preview');
        if (previewEl) {
            previewEl.innerHTML = this.generatePreview();
        }
        
        // Update max fields config
        const maxFieldsInput = document.getElementById('maxFields');
        if (maxFieldsInput) {
            this.config.maxFields = parseInt(maxFieldsInput.value) || 5;
        }
    }
    
    /**
     * Reset to defaults
     */
    reset() {
        if (!confirm('Reset subtitle configuration to defaults?')) {
            return;
        }
        
        this.config = this.extractConfig(this.gridConfig);
        this.render();
    }
    
    /**
     * Apply configuration
     */
    apply() {
        const updates = {
            show_subtitles: this.config.enabled,
            subtitle_fields: this.config.fields,
            subtitle_show_names: document.getElementById('showFieldNames')?.checked ?? true,
            subtitle_separator: document.getElementById('separatorSelect')?.value || ' | ',
            subtitle_max_fields: parseInt(document.getElementById('maxFields')?.value) || 5
        };
        
        if (this.onUpdate) {
            this.onUpdate(updates);
        }
        
        console.log('Subtitle configuration applied:', updates);
    }
    
    /**
     * Escape HTML
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text || '';
        return div.innerHTML;
    }
    
    /**
     * Escape attribute
     */
    escapeAttr(text) {
        return (text || '').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }
}

/**
 * CSS Styles for Subtitle Configurator
 */
const SUBTITLE_CONFIGURATOR_CSS = `
.subtitle-configurator {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.checkbox-label.large {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 16px;
    background: #f8f9fa;
    border-radius: 8px;
    cursor: pointer;
}

.checkbox-label.large input[type="checkbox"] {
    margin-top: 2px;
}

.checkbox-label.large small {
    display: block;
    font-size: 12px;
    color: #666;
    font-weight: normal;
    margin-top: 4px;
}

.section-desc {
    font-size: 13px;
    color: #666;
    margin-bottom: 12px;
}

.field-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 60px;
    padding: 12px;
    background: white;
    border: 2px dashed #ddd;
    border-radius: 8px;
}

.field-list.sortable {
    background: #f0f7ff;
    border-color: #4a9eff;
}

.field-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
    transition: all 0.2s;
}

.field-item.selected {
    cursor: move;
    border-color: #4a9eff;
}

.field-item.selected:hover {
    background: #f0f7ff;
}

.field-item.dragging {
    opacity: 0.5;
}

.drag-handle {
    color: #999;
    cursor: move;
    user-select: none;
}

.field-name {
    flex: 1;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 14px;
    font-weight: 500;
}

.field-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 24px;
    height: 24px;
    padding: 0 6px;
    background: #e3f2fd;
    color: #1976d2;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
}

.btn-remove, .btn-add {
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

.btn-remove:hover {
    background: #ffebee;
    border-color: #ef5350;
    color: #ef5350;
}

.btn-add:hover {
    background: #e8f5e9;
    border-color: #4caf50;
    color: #4caf50;
}

.empty-message {
    padding: 20px;
    text-align: center;
    color: #999;
    font-size: 14px;
    font-style: italic;
}

.options-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.option-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
}

.select-input {
    padding: 8px 10px;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
    font-family: inherit;
    background: white;
    cursor: pointer;
}

.select-input:focus {
    outline: none;
    border-color: #4a9eff;
}

.input-number {
    padding: 8px 10px;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
    font-family: inherit;
    width: 100px;
}

.input-number:focus {
    outline: none;
    border-color: #4a9eff;
}

.preview-section {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
}

.preview-section .section-label {
    color: white;
}

.subtitle-preview {
    margin-top: 12px;
    padding: 16px;
    background: rgba(255,255,255,0.15);
    border-radius: 6px;
    backdrop-filter: blur(10px);
}

.preview-text {
    font-size: 14px;
    line-height: 1.6;
    color: white;
}

.preview-empty {
    color: rgba(255,255,255,0.7);
    font-style: italic;
    text-align: center;
}
`;

// Global reference for onclick handlers
let subtitleConfigurator = null;
