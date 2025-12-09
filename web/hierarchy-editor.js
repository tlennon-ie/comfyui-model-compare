/**
 * Hierarchy Editor UI
 * 
 * Interactive interface for configuring row/column hierarchies
 * with drag-drop support and real-time preview.
 */

class HierarchyEditor {
    constructor(containerId, gridPath) {
        this.container = document.getElementById(containerId);
        this.gridPath = gridPath;
        this.gridConfig = null;
        this.rowHierarchy = [];
        this.colHierarchy = [];
        this.selectedFields = new Set();
        
        this.init();
    }
    
    async init() {
        try {
            // Load grid configuration
            const response = await fetch('/api/grid/load', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ grid_path: this.gridPath })
            });
            
            if (!response.ok) throw new Error('Failed to load grid');
            
            const result = await response.json();
            this.gridConfig = result.grid;
            this.rowHierarchy = this.gridConfig.hierarchy.row_hierarchy;
            this.colHierarchy = this.gridConfig.hierarchy.col_hierarchy;
            
            this.render();
            this.attachEventListeners();
            
        } catch (error) {
            console.error('Failed to initialize hierarchy editor:', error);
            this.showError(error.message);
        }
    }
    
    render() {
        if (!this.container) return;
        
        const html = `
            <div class="hierarchy-editor">
                <div class="editor-header">
                    <h2>Grid Hierarchy Configuration</h2>
                    <p class="info">Drag fields to organize rows and columns</p>
                </div>
                
                <div class="editor-content">
                    <div class="field-selection">
                        <h3>Available Fields</h3>
                        <div class="available-fields" id="availableFields">
                            ${this.renderAvailableFields()}
                        </div>
                    </div>
                    
                    <div class="hierarchy-zones">
                        <div class="hierarchy-zone">
                            <h3>Row Hierarchy (↓ Outer → Inner)</h3>
                            <div class="hierarchy-list row-hierarchy" id="rowHierarchy">
                                ${this.renderHierarchyList(this.rowHierarchy)}
                            </div>
                            <p class="zone-hint">Drag fields here for row nesting</p>
                        </div>
                        
                        <div class="hierarchy-zone">
                            <h3>Column Hierarchy (← Outer → Inner)</h3>
                            <div class="hierarchy-list col-hierarchy" id="colHierarchy">
                                ${this.renderHierarchyList(this.colHierarchy)}
                            </div>
                            <p class="zone-hint">Drag fields here for column nesting</p>
                        </div>
                    </div>
                </div>
                
                <div class="editor-preview">
                    <h3>Preview</h3>
                    <div id="previewInfo" class="preview-info">
                        Loading preview...
                    </div>
                </div>
                
                <div class="editor-actions">
                    <button class="btn btn-primary" id="applyButton">Apply Changes</button>
                    <button class="btn btn-secondary" id="previewButton">Update Preview</button>
                    <button class="btn btn-danger" id="resetButton">Reset to Original</button>
                </div>
                
                <div id="errorMessage" class="error-message" style="display:none;"></div>
            </div>
        `;
        
        this.container.innerHTML = html;
    }
    
    renderAvailableFields() {
        const varying = this.gridConfig.varying_dimensions;
        const used = new Set([...this.rowHierarchy, ...this.colHierarchy]);
        
        return Object.keys(varying)
            .filter(field => !used.has(field))
            .map(field => {
                const count = varying[field].length;
                return `
                    <div class="field-item available" draggable="true" data-field="${field}">
                        <span class="field-name">${field}</span>
                        <span class="field-count">${count} values</span>
                    </div>
                `;
            })
            .join('');
    }
    
    renderHierarchyList(hierarchy) {
        if (hierarchy.length === 0) {
            return '<div class="hierarchy-empty">No fields assigned</div>';
        }
        
        return hierarchy.map((field, idx) => `
            <div class="hierarchy-item" data-field="${field}" draggable="true">
                <span class="hierarchy-level">${idx + 1}</span>
                <span class="hierarchy-field">${field}</span>
                <button class="remove-btn" data-field="${field}">×</button>
            </div>
        `).join('');
    }
    
    attachEventListeners() {
        // Drag and drop for fields
        document.addEventListener('dragstart', (e) => this.onDragStart(e));
        document.addEventListener('dragover', (e) => this.onDragOver(e));
        document.addEventListener('drop', (e) => this.onDrop(e));
        document.addEventListener('dragend', (e) => this.onDragEnd(e));
        
        // Remove buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('remove-btn')) {
                const field = e.target.dataset.field;
                this.removeField(field);
            }
        });
        
        // Action buttons
        document.getElementById('applyButton')?.addEventListener('click', () => {
            this.applyChanges();
        });
        
        document.getElementById('previewButton')?.addEventListener('click', () => {
            this.updatePreview();
        });
        
        document.getElementById('resetButton')?.addEventListener('click', () => {
            this.reset();
        });
    }
    
    onDragStart(e) {
        if (!e.target.classList.contains('field-item') && 
            !e.target.classList.contains('hierarchy-item')) {
            return;
        }
        
        const field = e.target.dataset.field;
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('field', field);
        e.dataTransfer.setData('source', e.target.parentElement.id);
        
        e.target.classList.add('dragging');
    }
    
    onDragOver(e) {
        if (e.dataTransfer.types.includes('field')) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
        }
    }
    
    onDrop(e) {
        e.preventDefault();
        
        const field = e.dataTransfer.getData('field');
        const source = e.dataTransfer.getData('source');
        const target = e.target.closest('.hierarchy-zone')?.querySelector('.hierarchy-list');
        
        if (!target) return;
        
        const targetType = target.id === 'rowHierarchy' ? 'row' : 'col';
        const targetList = targetType === 'row' ? this.rowHierarchy : this.colHierarchy;
        
        // Remove from current location
        const sourceIdx = this.rowHierarchy.indexOf(field);
        const colIdx = this.colHierarchy.indexOf(field);
        
        if (sourceIdx !== -1) this.rowHierarchy.splice(sourceIdx, 1);
        if (colIdx !== -1) this.colHierarchy.splice(colIdx, 1);
        
        // Add to target
        if (!targetList.includes(field)) {
            targetList.push(field);
        }
        
        this.render();
        this.attachEventListeners();
    }
    
    onDragEnd(e) {
        document.querySelectorAll('.dragging').forEach(el => {
            el.classList.remove('dragging');
        });
    }
    
    removeField(field) {
        this.rowHierarchy = this.rowHierarchy.filter(f => f !== field);
        this.colHierarchy = this.colHierarchy.filter(f => f !== field);
        this.render();
        this.attachEventListeners();
    }
    
    async updatePreview() {
        try {
            const response = await fetch('/api/grid/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    grid_path: this.gridPath,
                    row_hierarchy: this.rowHierarchy,
                    col_hierarchy: this.colHierarchy,
                    title: this.gridConfig.metadata.title
                })
            });
            
            if (!response.ok) throw new Error('Preview generation failed');
            
            const result = await response.json();
            const preview = result.preview;
            
            const previewHtml = `
                <div class="preview-stats">
                    <div class="stat">
                        <span class="stat-label">Dimensions:</span>
                        <span class="stat-value">${preview.dimensions.width}×${preview.dimensions.height}px</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Grid Layout:</span>
                        <span class="stat-value">${preview.cells.cols} cols × ${preview.cells.rows} rows</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Cells with Images:</span>
                        <span class="stat-value">${preview.cells.total} / ${preview.cells.rows * preview.cells.cols}</span>
                    </div>
                    <div class="stat">
                        <span class="stat-label">Hierarchy Depth:</span>
                        <span class="stat-value">${preview.hierarchy.depth} levels</span>
                    </div>
                </div>
            `;
            
            document.getElementById('previewInfo').innerHTML = previewHtml;
            
        } catch (error) {
            this.showError('Failed to update preview: ' + error.message);
        }
    }
    
    async applyChanges() {
        try {
            const outputName = prompt('Enter name for new grid:', 'reconfigured_grid');
            if (!outputName) return;
            
            const response = await fetch('/api/grid/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    grid_path: this.gridPath,
                    row_hierarchy: this.rowHierarchy,
                    col_hierarchy: this.colHierarchy,
                    title: this.gridConfig.metadata.title,
                    format: 'html',
                    output_name: outputName
                })
            });
            
            if (!response.ok) throw new Error('Export failed');
            
            const result = await response.json();
            
            // Show success and offer to view
            if (confirm('Grid exported successfully! Open the new grid?')) {
                // Encode the full path as base64 for the view route
                const fullPath = result.export.path;
                const encoded = btoa(fullPath).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
                window.location.href = `/model-compare/view/${encoded}`;
            }
            
        } catch (error) {
            this.showError('Failed to apply changes: ' + error.message);
        }
    }
    
    reset() {
        if (confirm('Reset to original hierarchy?')) {
            this.rowHierarchy = [...this.gridConfig.hierarchy.row_hierarchy];
            this.colHierarchy = [...this.gridConfig.hierarchy.col_hierarchy];
            this.render();
            this.attachEventListeners();
        }
    }
    
    showError(message) {
        const errorDiv = document.getElementById('errorMessage');
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = 'block';
            setTimeout(() => {
                errorDiv.style.display = 'none';
            }, 5000);
        }
    }
}


// CSS for Hierarchy Editor (Theme-aware)
const HIERARCHY_EDITOR_CSS = `
.hierarchy-editor {
    max-width: 1200px;
    margin: 0 auto;
    padding: 20px;
}

.editor-header {
    text-align: center;
    margin-bottom: 30px;
}

.editor-header h2 {
    margin: 0 0 10px 0;
    font-size: 28px;
    color: var(--text-primary);
}

.editor-header .info {
    color: var(--text-secondary);
    margin: 0;
    font-size: 14px;
}

.editor-content {
    display: grid;
    grid-template-columns: 1fr 2fr;
    gap: 30px;
    margin-bottom: 40px;
}

.field-selection {
    background: var(--bg-secondary);
    padding: 20px;
    border-radius: 8px;
    border: 1px solid var(--border);
}

.field-selection h3 {
    margin-top: 0;
    margin-bottom: 15px;
    color: var(--text-primary);
}

.available-fields {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.field-item {
    background: var(--bg-card);
    border: 1px solid var(--border);
    padding: 10px 15px;
    border-radius: 4px;
    cursor: move;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: all 0.2s;
    color: var(--text-primary);
}

.field-item:hover {
    border-color: var(--accent);
    box-shadow: 0 2px 8px var(--shadow);
    background: var(--bg-card-hover);
}

.field-item.dragging {
    opacity: 0.5;
    transform: scale(0.95);
}

.field-name {
    font-weight: 500;
}

.field-count {
    background: var(--accent);
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 12px;
    margin-left: 10px;
}

.hierarchy-zones {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 20px;
}

.hierarchy-zone {
    background: var(--bg-secondary);
    border: 2px dashed var(--border);
    border-radius: 8px;
    padding: 20px;
    min-height: 300px;
}

.hierarchy-zone h3 {
    margin-top: 0;
    margin-bottom: 15px;
    font-size: 16px;
    color: var(--text-primary);
}

.hierarchy-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 200px;
}

.hierarchy-empty {
    text-align: center;
    color: var(--text-secondary);
    padding: 40px 20px;
    font-style: italic;
}

.hierarchy-item {
    background: var(--bg-card);
    border: 1px solid var(--accent);
    border-left: 4px solid var(--accent);
    padding: 10px 15px;
    border-radius: 4px;
    cursor: move;
    display: flex;
    align-items: center;
    gap: 10px;
    transition: all 0.2s;
    color: var(--text-primary);
}

.hierarchy-item:hover {
    box-shadow: 0 2px 8px var(--shadow);
    background: var(--bg-card-hover);
}

.hierarchy-item.dragging {
    opacity: 0.5;
}

.hierarchy-level {
    background: var(--accent);
    color: white;
    width: 24px;
    height: 24px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: bold;
    flex-shrink: 0;
}

.hierarchy-field {
    flex: 1;
    font-weight: 500;
}

.remove-btn {
    background: #ff4444;
    color: white;
    border: none;
    width: 24px;
    height: 24px;
    border-radius: 4px;
    cursor: pointer;
    font-size: 18px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
}

.remove-btn:hover {
    background: #ff0000;
}

.zone-hint {
    font-size: 12px;
    color: var(--text-secondary);
    margin-top: 10px;
    margin-bottom: 0;
    font-style: italic;
}

.editor-preview {
    background: var(--bg-secondary);
    padding: 20px;
    border-radius: 8px;
    margin-bottom: 30px;
    border: 1px solid var(--border);
}

.editor-preview h3 {
    margin-top: 0;
    color: var(--text-primary);
}

.preview-info {
    background: var(--bg-card);
    padding: 20px;
    border-radius: 4px;
    border-left: 4px solid var(--accent);
}

.preview-stats {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 15px;
}

.stat {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.stat-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    font-weight: 600;
}

.stat-value {
    font-size: 18px;
    font-weight: bold;
    color: var(--accent);
}

.editor-actions {
    display: flex;
    gap: 10px;
    justify-content: center;
    margin-bottom: 20px;
}

.btn {
    padding: 12px 24px;
    border: none;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
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
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
}

.btn-secondary:hover {
    background: var(--bg-card-hover);
}

.btn-danger {
    background: #ff6b6b;
    color: white;
}

.btn-danger:hover {
    background: #ff5252;
}

.error-message {
    background: rgba(255, 68, 68, 0.1);
    border: 1px solid #ff4444;
    color: #ff4444;
    padding: 12px 16px;
    border-radius: 4px;
    margin-top: 20px;
}

@media (max-width: 900px) {
    .editor-content {
        grid-template-columns: 1fr;
    }
    
    .hierarchy-zones {
        grid-template-columns: 1fr;
    }
}
`;
