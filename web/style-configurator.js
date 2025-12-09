/**
 * Style Configurator
 * 
 * Interactive UI for customizing grid colors, borders, padding, and fonts.
 * Supports field-specific color mappings and CSS customization.
 */

class StyleConfigurator {
    constructor(containerId, gridConfig, onUpdate) {
        this.containerId = containerId;
        this.gridConfig = gridConfig;
        this.onUpdate = onUpdate;
        this.config = this.extractConfig(gridConfig);
        
        this.render();
    }
    
    /**
     * Extract style configuration from grid config
     */
    extractConfig(config) {
        return {
            // Global colors
            backgroundColor: config.style_bg_color || '#ffffff',
            borderColor: config.style_border_color || '#dddddd',
            headerBgColor: config.style_header_bg || '#f5f5f5',
            headerTextColor: config.style_header_text || '#333333',
            cellBgColor: config.style_cell_bg || '#ffffff',
            cellTextColor: config.style_cell_text || '#333333',
            
            // Typography
            fontFamily: config.style_font_family || 'Arial, sans-serif',
            fontSize: config.style_font_size || '14',
            titleSize: config.style_title_size || '24',
            
            // Spacing
            cellPadding: config.style_cell_padding || '12',
            borderWidth: config.style_border_width || '1',
            borderRadius: config.style_border_radius || '0',
            
            // Field-specific colors
            fieldColors: config.style_field_colors || {},
            
            // Advanced
            customCSS: config.style_custom_css || ''
        };
    }
    
    /**
     * Get all unique field values for color mapping
     */
    getFieldValues() {
        const fieldValues = {};
        
        if (!this.gridConfig.images) return fieldValues;
        
        // Collect unique values for each field
        this.gridConfig.images.forEach(img => {
            Object.entries(img.params || {}).forEach(([field, value]) => {
                if (!fieldValues[field]) {
                    fieldValues[field] = new Set();
                }
                fieldValues[field].add(String(value));
            });
        });
        
        // Convert Sets to sorted arrays
        Object.keys(fieldValues).forEach(field => {
            fieldValues[field] = Array.from(fieldValues[field]).sort();
        });
        
        return fieldValues;
    }
    
    /**
     * Render the style configurator UI
     */
    render() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error('Style configurator container not found:', this.containerId);
            return;
        }
        
        const fieldValues = this.getFieldValues();
        
        container.innerHTML = `
            <div class="style-configurator">
                <div class="config-header">
                    <h3>🎨 Styles & Colors</h3>
                    <p class="help-text">Customize the visual appearance of your grid.</p>
                </div>
                
                <div class="config-sections">
                    <!-- Color Scheme -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">🎨</span>
                            Color Scheme
                        </label>
                        
                        <div class="color-grid">
                            <div class="color-item">
                                <label class="color-label">Background</label>
                                <input 
                                    type="color" 
                                    id="backgroundColor" 
                                    value="${this.config.backgroundColor}"
                                    class="color-input"
                                >
                                <input 
                                    type="text" 
                                    value="${this.config.backgroundColor}"
                                    class="color-text"
                                    readonly
                                >
                            </div>
                            
                            <div class="color-item">
                                <label class="color-label">Border</label>
                                <input 
                                    type="color" 
                                    id="borderColor" 
                                    value="${this.config.borderColor}"
                                    class="color-input"
                                >
                                <input 
                                    type="text" 
                                    value="${this.config.borderColor}"
                                    class="color-text"
                                    readonly
                                >
                            </div>
                            
                            <div class="color-item">
                                <label class="color-label">Header Background</label>
                                <input 
                                    type="color" 
                                    id="headerBgColor" 
                                    value="${this.config.headerBgColor}"
                                    class="color-input"
                                >
                                <input 
                                    type="text" 
                                    value="${this.config.headerBgColor}"
                                    class="color-text"
                                    readonly
                                >
                            </div>
                            
                            <div class="color-item">
                                <label class="color-label">Header Text</label>
                                <input 
                                    type="color" 
                                    id="headerTextColor" 
                                    value="${this.config.headerTextColor}"
                                    class="color-input"
                                >
                                <input 
                                    type="text" 
                                    value="${this.config.headerTextColor}"
                                    class="color-text"
                                    readonly
                                >
                            </div>
                            
                            <div class="color-item">
                                <label class="color-label">Cell Background</label>
                                <input 
                                    type="color" 
                                    id="cellBgColor" 
                                    value="${this.config.cellBgColor}"
                                    class="color-input"
                                >
                                <input 
                                    type="text" 
                                    value="${this.config.cellBgColor}"
                                    class="color-text"
                                    readonly
                                >
                            </div>
                            
                            <div class="color-item">
                                <label class="color-label">Cell Text</label>
                                <input 
                                    type="color" 
                                    id="cellTextColor" 
                                    value="${this.config.cellTextColor}"
                                    class="color-input"
                                >
                                <input 
                                    type="text" 
                                    value="${this.config.cellTextColor}"
                                    class="color-text"
                                    readonly
                                >
                            </div>
                        </div>
                        
                        <div class="preset-colors">
                            <button class="btn-preset" onclick="styleConfigurator.applyPreset('light')">☀️ Light</button>
                            <button class="btn-preset" onclick="styleConfigurator.applyPreset('dark')">🌙 Dark</button>
                            <button class="btn-preset" onclick="styleConfigurator.applyPreset('blue')">💙 Blue</button>
                            <button class="btn-preset" onclick="styleConfigurator.applyPreset('green')">💚 Green</button>
                            <button class="btn-preset" onclick="styleConfigurator.applyPreset('purple')">💜 Purple</button>
                        </div>
                    </div>
                    
                    <!-- Typography -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">🔤</span>
                            Typography
                        </label>
                        
                        <div class="typography-grid">
                            <div class="input-group">
                                <label class="input-label">Font Family</label>
                                <select id="fontFamily" class="select-input">
                                    <option value="Arial, sans-serif" ${this.config.fontFamily === 'Arial, sans-serif' ? 'selected' : ''}>Arial</option>
                                    <option value="'Helvetica Neue', Helvetica, sans-serif" ${this.config.fontFamily.includes('Helvetica') ? 'selected' : ''}>Helvetica</option>
                                    <option value="'Segoe UI', Tahoma, sans-serif" ${this.config.fontFamily.includes('Segoe') ? 'selected' : ''}>Segoe UI</option>
                                    <option value="'Times New Roman', Times, serif" ${this.config.fontFamily.includes('Times') ? 'selected' : ''}>Times New Roman</option>
                                    <option value="'Courier New', Courier, monospace" ${this.config.fontFamily.includes('Courier') ? 'selected' : ''}>Courier New</option>
                                    <option value="Georgia, serif" ${this.config.fontFamily === 'Georgia, serif' ? 'selected' : ''}>Georgia</option>
                                    <option value="Verdana, sans-serif" ${this.config.fontFamily === 'Verdana, sans-serif' ? 'selected' : ''}>Verdana</option>
                                </select>
                            </div>
                            
                            <div class="input-group">
                                <label class="input-label">Base Font Size (px)</label>
                                <input 
                                    type="number" 
                                    id="fontSize" 
                                    value="${this.config.fontSize}"
                                    min="10"
                                    max="24"
                                    class="input-number"
                                >
                            </div>
                            
                            <div class="input-group">
                                <label class="input-label">Title Size (px)</label>
                                <input 
                                    type="number" 
                                    id="titleSize" 
                                    value="${this.config.titleSize}"
                                    min="16"
                                    max="48"
                                    class="input-number"
                                >
                            </div>
                        </div>
                    </div>
                    
                    <!-- Spacing & Borders -->
                    <div class="config-section">
                        <label class="section-label">
                            <span class="label-icon">📐</span>
                            Spacing & Borders
                        </label>
                        
                        <div class="spacing-grid">
                            <div class="input-group">
                                <label class="input-label">Cell Padding (px)</label>
                                <input 
                                    type="range" 
                                    id="cellPadding" 
                                    value="${this.config.cellPadding}"
                                    min="0"
                                    max="32"
                                    class="range-input"
                                    oninput="this.nextElementSibling.textContent = this.value + 'px'"
                                >
                                <span class="range-value">${this.config.cellPadding}px</span>
                            </div>
                            
                            <div class="input-group">
                                <label class="input-label">Border Width (px)</label>
                                <input 
                                    type="range" 
                                    id="borderWidth" 
                                    value="${this.config.borderWidth}"
                                    min="0"
                                    max="8"
                                    class="range-input"
                                    oninput="this.nextElementSibling.textContent = this.value + 'px'"
                                >
                                <span class="range-value">${this.config.borderWidth}px</span>
                            </div>
                            
                            <div class="input-group">
                                <label class="input-label">Border Radius (px)</label>
                                <input 
                                    type="range" 
                                    id="borderRadius" 
                                    value="${this.config.borderRadius}"
                                    min="0"
                                    max="20"
                                    class="range-input"
                                    oninput="this.nextElementSibling.textContent = this.value + 'px'"
                                >
                                <span class="range-value">${this.config.borderRadius}px</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Field-Specific Colors -->
                    <div class="config-section collapsible">
                        <button class="section-toggle" onclick="this.parentElement.classList.toggle('expanded')">
                            <span class="label-icon">🎯</span>
                            Field-Specific Colors
                            <span class="badge">${Object.keys(this.config.fieldColors).length} configured</span>
                            <span class="toggle-icon">▼</span>
                        </button>
                        <div class="section-content">
                            <p class="section-desc">Assign unique colors to specific field values (e.g., different colors for each model).</p>
                            ${this.renderFieldColorMappings(fieldValues)}
                        </div>
                    </div>
                    
                    <!-- Custom CSS -->
                    <div class="config-section collapsible">
                        <button class="section-toggle" onclick="this.parentElement.classList.toggle('expanded')">
                            <span class="label-icon">⚡</span>
                            Custom CSS (Advanced)
                            <span class="toggle-icon">▼</span>
                        </button>
                        <div class="section-content">
                            <p class="section-desc">Add custom CSS rules for advanced styling.</p>
                            <textarea 
                                id="customCSS" 
                                class="css-textarea"
                                placeholder="/* Custom CSS rules */\n.grid-cell {\n  /* your styles */\n}"
                            >${this.config.customCSS}</textarea>
                        </div>
                    </div>
                    
                    <!-- Preview -->
                    <div class="config-section preview-section">
                        <label class="section-label">
                            <span class="label-icon">👁️</span>
                            Preview
                        </label>
                        <div class="style-preview">
                            ${this.generatePreview()}
                        </div>
                    </div>
                </div>
                
                <!-- Action Buttons -->
                <div class="config-actions">
                    <button class="btn btn-secondary" onclick="styleConfigurator.reset()">
                        Reset to Defaults
                    </button>
                    <button class="btn btn-primary" onclick="styleConfigurator.apply()">
                        Apply Styles
                    </button>
                </div>
            </div>
        `;
        
        this.attachEventListeners();
    }
    
    /**
     * Render field color mappings
     */
    renderFieldColorMappings(fieldValues) {
        const fields = Object.keys(fieldValues);
        
        if (fields.length === 0) {
            return '<div class="empty-message">No fields available for color mapping.</div>';
        }
        
        return `
            <div class="field-color-mappings">
                ${fields.map(field => `
                    <div class="field-color-group">
                        <div class="field-color-header">
                            <strong>${this.escapeHtml(field)}</strong>
                            <span class="value-count">${fieldValues[field].length} values</span>
                        </div>
                        <div class="field-color-values">
                            ${fieldValues[field].slice(0, 10).map(value => {
                                const colorKey = `${field}:${value}`;
                                const currentColor = this.config.fieldColors[colorKey] || this.generateAutoColor(value);
                                return `
                                    <div class="field-color-value">
                                        <span class="value-label">${this.escapeHtml(value)}</span>
                                        <input 
                                            type="color" 
                                            value="${currentColor}"
                                            class="color-input-small"
                                            data-field="${this.escapeAttr(field)}"
                                            data-value="${this.escapeAttr(value)}"
                                            onchange="styleConfigurator.updateFieldColor(this)"
                                        >
                                    </div>
                                `;
                            }).join('')}
                            ${fieldValues[field].length > 10 ? `<div class="more-values">...and ${fieldValues[field].length - 10} more</div>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `;
    }
    
    /**
     * Generate auto color based on value
     */
    generateAutoColor(value) {
        // Simple hash-based color generation
        let hash = 0;
        for (let i = 0; i < value.length; i++) {
            hash = value.charCodeAt(i) + ((hash << 5) - hash);
        }
        const hue = Math.abs(hash % 360);
        return `hsl(${hue}, 70%, 60%)`;
    }
    
    /**
     * Generate preview
     */
    generatePreview() {
        return `
            <div class="preview-grid" style="
                background: ${this.config.backgroundColor};
                border: ${this.config.borderWidth}px solid ${this.config.borderColor};
                border-radius: ${this.config.borderRadius}px;
                font-family: ${this.config.fontFamily};
                font-size: ${this.config.fontSize}px;
            ">
                <div class="preview-header" style="
                    background: ${this.config.headerBgColor};
                    color: ${this.config.headerTextColor};
                    padding: ${this.config.cellPadding}px;
                    font-weight: bold;
                ">
                    Sample Header
                </div>
                <div class="preview-cell" style="
                    background: ${this.config.cellBgColor};
                    color: ${this.config.cellTextColor};
                    padding: ${this.config.cellPadding}px;
                ">
                    Sample Cell Content
                </div>
            </div>
        `;
    }
    
    /**
     * Apply color preset
     */
    applyPreset(presetName) {
        const presets = {
            light: {
                backgroundColor: '#ffffff',
                borderColor: '#dddddd',
                headerBgColor: '#f5f5f5',
                headerTextColor: '#333333',
                cellBgColor: '#ffffff',
                cellTextColor: '#333333'
            },
            dark: {
                backgroundColor: '#1a1a1a',
                borderColor: '#444444',
                headerBgColor: '#2d2d2d',
                headerTextColor: '#eeeeee',
                cellBgColor: '#1a1a1a',
                cellTextColor: '#eeeeee'
            },
            blue: {
                backgroundColor: '#e3f2fd',
                borderColor: '#90caf9',
                headerBgColor: '#2196f3',
                headerTextColor: '#ffffff',
                cellBgColor: '#ffffff',
                cellTextColor: '#1976d2'
            },
            green: {
                backgroundColor: '#e8f5e9',
                borderColor: '#81c784',
                headerBgColor: '#4caf50',
                headerTextColor: '#ffffff',
                cellBgColor: '#ffffff',
                cellTextColor: '#2e7d32'
            },
            purple: {
                backgroundColor: '#f3e5f5',
                borderColor: '#ba68c8',
                headerBgColor: '#9c27b0',
                headerTextColor: '#ffffff',
                cellBgColor: '#ffffff',
                cellTextColor: '#6a1b9a'
            }
        };
        
        const preset = presets[presetName];
        if (preset) {
            Object.assign(this.config, preset);
            this.render();
        }
    }
    
    /**
     * Update field color mapping
     */
    updateFieldColor(input) {
        const field = input.dataset.field;
        const value = input.dataset.value;
        const color = input.value;
        const colorKey = `${field}:${value}`;
        
        this.config.fieldColors[colorKey] = color;
    }
    
    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Live preview updates for all inputs
        const inputs = ['backgroundColor', 'borderColor', 'headerBgColor', 'headerTextColor', 
                       'cellBgColor', 'cellTextColor', 'fontFamily', 'fontSize', 'titleSize',
                       'cellPadding', 'borderWidth', 'borderRadius'];
        
        inputs.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.addEventListener('input', () => this.updatePreview());
                element.addEventListener('change', () => this.updatePreview());
                
                // Update color text display
                if (element.type === 'color') {
                    element.addEventListener('input', (e) => {
                        const textInput = e.target.nextElementSibling;
                        if (textInput && textInput.classList.contains('color-text')) {
                            textInput.value = e.target.value;
                        }
                    });
                }
            }
        });
    }
    
    /**
     * Update preview
     */
    updatePreview() {
        // Update config from inputs
        this.config.backgroundColor = document.getElementById('backgroundColor')?.value || this.config.backgroundColor;
        this.config.borderColor = document.getElementById('borderColor')?.value || this.config.borderColor;
        this.config.headerBgColor = document.getElementById('headerBgColor')?.value || this.config.headerBgColor;
        this.config.headerTextColor = document.getElementById('headerTextColor')?.value || this.config.headerTextColor;
        this.config.cellBgColor = document.getElementById('cellBgColor')?.value || this.config.cellBgColor;
        this.config.cellTextColor = document.getElementById('cellTextColor')?.value || this.config.cellTextColor;
        this.config.fontFamily = document.getElementById('fontFamily')?.value || this.config.fontFamily;
        this.config.fontSize = document.getElementById('fontSize')?.value || this.config.fontSize;
        this.config.titleSize = document.getElementById('titleSize')?.value || this.config.titleSize;
        this.config.cellPadding = document.getElementById('cellPadding')?.value || this.config.cellPadding;
        this.config.borderWidth = document.getElementById('borderWidth')?.value || this.config.borderWidth;
        this.config.borderRadius = document.getElementById('borderRadius')?.value || this.config.borderRadius;
        
        // Update preview
        const previewEl = document.querySelector('.style-preview');
        if (previewEl) {
            previewEl.innerHTML = this.generatePreview();
        }
    }
    
    /**
     * Reset to defaults
     */
    reset() {
        if (!confirm('Reset all style customizations to defaults?')) {
            return;
        }
        
        this.config = this.extractConfig({});
        this.render();
    }
    
    /**
     * Apply styles
     */
    apply() {
        const updates = {
            style_bg_color: this.config.backgroundColor,
            style_border_color: this.config.borderColor,
            style_header_bg: this.config.headerBgColor,
            style_header_text: this.config.headerTextColor,
            style_cell_bg: this.config.cellBgColor,
            style_cell_text: this.config.cellTextColor,
            style_font_family: this.config.fontFamily,
            style_font_size: this.config.fontSize,
            style_title_size: this.config.titleSize,
            style_cell_padding: this.config.cellPadding,
            style_border_width: this.config.borderWidth,
            style_border_radius: this.config.borderRadius,
            style_field_colors: this.config.fieldColors,
            style_custom_css: document.getElementById('customCSS')?.value || ''
        };
        
        if (this.onUpdate) {
            this.onUpdate(updates);
        }
        
        console.log('Style configuration applied:', updates);
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
 * CSS Styles for Style Configurator
 */
const STYLE_CONFIGURATOR_CSS = `
.style-configurator {
    background: white;
    border-radius: 12px;
    padding: 24px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.color-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
}

.color-item {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.color-label {
    font-size: 13px;
    font-weight: 600;
    color: #555;
}

.color-input {
    width: 100%;
    height: 50px;
    border: 2px solid #ddd;
    border-radius: 6px;
    cursor: pointer;
}

.color-input:hover {
    border-color: #4a9eff;
}

.color-text {
    padding: 6px 10px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 12px;
    font-family: 'Consolas', 'Monaco', monospace;
    text-align: center;
    background: #f9f9f9;
}

.preset-colors {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid #e0e0e0;
}

.btn-preset {
    padding: 8px 16px;
    background: white;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
}

.btn-preset:hover {
    border-color: #4a9eff;
    background: #f0f7ff;
}

.typography-grid, .spacing-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
}

.range-input {
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: #e0e0e0;
    outline: none;
    appearance: none;
}

.range-input::-webkit-slider-thumb {
    appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #4a9eff;
    cursor: pointer;
}

.range-input::-moz-range-thumb {
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #4a9eff;
    cursor: pointer;
    border: none;
}

.range-value {
    display: block;
    text-align: center;
    font-size: 13px;
    font-weight: 600;
    color: #666;
    margin-top: 4px;
}

.field-color-mappings {
    display: flex;
    flex-direction: column;
    gap: 20px;
}

.field-color-group {
    padding: 16px;
    background: #f9f9f9;
    border-radius: 8px;
    border: 1px solid #e0e0e0;
}

.field-color-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 1px solid #ddd;
}

.value-count {
    font-size: 12px;
    color: #666;
    font-weight: normal;
}

.field-color-values {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 10px;
}

.field-color-value {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 6px 10px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 6px;
}

.value-label {
    flex: 1;
    font-size: 13px;
    font-family: 'Consolas', 'Monaco', monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.color-input-small {
    width: 32px;
    height: 32px;
    border: 1px solid #ddd;
    border-radius: 4px;
    cursor: pointer;
}

.more-values {
    grid-column: 1 / -1;
    text-align: center;
    font-size: 13px;
    color: #999;
    font-style: italic;
    padding: 8px;
}

.css-textarea {
    width: 100%;
    min-height: 200px;
    padding: 12px;
    border: 2px solid #ddd;
    border-radius: 6px;
    font-family: 'Consolas', 'Monaco', monospace;
    font-size: 13px;
    line-height: 1.5;
    resize: vertical;
}

.css-textarea:focus {
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

.style-preview {
    margin-top: 12px;
}

.preview-grid {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.preview-header, .preview-cell {
    text-align: center;
}
`;

// Global reference for onclick handlers
let styleConfigurator = null;
