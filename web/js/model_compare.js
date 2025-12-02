// Model Compare Web Extension
// Adds "Update Inputs" button to Model Compare nodes and handles dynamic visibility
// Supports multi-value input fields with autocomplete append functionality

// Valid samplers and schedulers from ComfyUI (updated dynamically if possible)
const VALID_SAMPLERS = [
    "euler", "euler_cfg_pp", "euler_ancestral", "euler_ancestral_cfg_pp",
    "heun", "heunpp2", "dpm_2", "dpm_2_ancestral", "lms", "dpm_fast", 
    "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_2s_ancestral_cfg_pp",
    "dpmpp_sde", "dpmpp_sde_gpu", "dpmpp_2m", "dpmpp_2m_cfg_pp",
    "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_3m_sde", "dpmpp_3m_sde_gpu",
    "ddpm", "lcm", "ipndm", "ipndm_v", "deis", "ddim", "uni_pc", "uni_pc_bh2"
];

const VALID_SCHEDULERS = [
    "normal", "karras", "exponential", "sgm_uniform", "simple",
    "ddim_uniform", "beta", "linear_quadratic", "kl_optimal"
];

// Global reference to app for popup callbacks
let globalAppRef = null;

/**
 * Show a multi-select popup for choosing multiple values
 * @param {Object} widget - The widget to update
 * @param {Array} options - Array of valid option strings  
 * @param {string} fieldName - Display name for the field
 * @param {Object} event - Mouse event for positioning
 */
function showMultiSelectPopup(widget, options, fieldName, event) {
    // Remove any existing popup
    const existingPopup = document.getElementById('model-compare-multiselect');
    if (existingPopup) existingPopup.remove();
    
    // Parse current values
    const currentValue = widget.value || '';
    const currentValues = currentValue.split(',').map(v => v.trim().toLowerCase()).filter(v => v);
    
    // Create popup container
    const popup = document.createElement('div');
    popup.id = 'model-compare-multiselect';
    popup.style.cssText = `
        position: fixed;
        left: ${event.clientX || 200}px;
        top: ${event.clientY || 200}px;
        background: #2a2a2a;
        border: 1px solid #555;
        border-radius: 6px;
        padding: 8px;
        z-index: 10000;
        max-height: 400px;
        overflow-y: auto;
        min-width: 200px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    `;
    
    // Header
    const header = document.createElement('div');
    header.textContent = `Select ${fieldName}s (click to toggle)`;
    header.style.cssText = `
        padding: 4px 8px 8px;
        border-bottom: 1px solid #444;
        margin-bottom: 8px;
        font-weight: bold;
        color: #aaa;
        font-size: 12px;
    `;
    popup.appendChild(header);
    
    // Checkbox items
    options.forEach(option => {
        const isSelected = currentValues.includes(option.toLowerCase());
        
        const item = document.createElement('label');
        item.style.cssText = `
            display: flex;
            align-items: center;
            padding: 4px 8px;
            cursor: pointer;
            border-radius: 3px;
            font-size: 12px;
        `;
        item.onmouseenter = () => item.style.background = '#3a3a3a';
        item.onmouseleave = () => item.style.background = 'transparent';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = isSelected;
        checkbox.style.cssText = 'margin-right: 8px;';
        checkbox.onchange = () => {
            updateWidgetValue();
        };
        
        const label = document.createElement('span');
        label.textContent = option;
        label.style.color = '#ddd';
        
        item.appendChild(checkbox);
        item.appendChild(label);
        popup.appendChild(item);
    });
    
    // Update widget value based on checkboxes
    const updateWidgetValue = () => {
        const checkboxes = popup.querySelectorAll('input[type="checkbox"]');
        const selected = [];
        checkboxes.forEach((cb, idx) => {
            if (cb.checked) selected.push(options[idx]);
        });
        widget.value = selected.join(', ');
        if (widget.callback) widget.callback(widget.value);
        if (globalAppRef && globalAppRef.graph) {
            globalAppRef.graph.setDirtyCanvas(true, true);
        }
    };
    
    // Buttons row - Select All / Clear All / Invert
    const selectRow = document.createElement('div');
    selectRow.style.cssText = `
        display: flex;
        gap: 8px;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #444;
    `;
    
    const selectAllBtn = document.createElement('button');
    selectAllBtn.textContent = 'Select All';
    selectAllBtn.style.cssText = `
        flex: 1;
        padding: 6px;
        background: #335533;
        border: 1px solid #668866;
        border-radius: 4px;
        color: #fff;
        cursor: pointer;
        font-size: 12px;
    `;
    selectAllBtn.onclick = () => {
        popup.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
        updateWidgetValue();
    };
    
    const clearBtn = document.createElement('button');
    clearBtn.textContent = 'Clear All';
    clearBtn.style.cssText = `
        flex: 1;
        padding: 6px;
        background: #553333;
        border: 1px solid #886666;
        border-radius: 4px;
        color: #fff;
        cursor: pointer;
        font-size: 12px;
    `;
    clearBtn.onclick = () => {
        popup.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
        updateWidgetValue();
    };
    
    const invertBtn = document.createElement('button');
    invertBtn.textContent = 'Invert';
    invertBtn.style.cssText = `
        flex: 1;
        padding: 6px;
        background: #444455;
        border: 1px solid #666688;
        border-radius: 4px;
        color: #fff;
        cursor: pointer;
        font-size: 12px;
    `;
    invertBtn.onclick = () => {
        popup.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = !cb.checked);
        updateWidgetValue();
    };
    
    selectRow.appendChild(selectAllBtn);
    selectRow.appendChild(clearBtn);
    selectRow.appendChild(invertBtn);
    popup.appendChild(selectRow);
    
    // Close button row
    const closeRow = document.createElement('div');
    closeRow.style.cssText = `
        display: flex;
        gap: 8px;
        margin-top: 8px;
    `;
    
    const closeBtn = document.createElement('button');
    closeBtn.textContent = 'Close';
    closeBtn.style.cssText = `
        flex: 1;
        padding: 6px;
        background: #444;
        border: 1px solid #666;
        border-radius: 4px;
        color: #fff;
        cursor: pointer;
        font-size: 12px;
    `;
    closeBtn.onclick = () => popup.remove();
    
    closeRow.appendChild(closeBtn);
    popup.appendChild(closeRow);
    
    document.body.appendChild(popup);
    
    // Close on click outside
    const closeOnClickOutside = (e) => {
        if (!popup.contains(e.target)) {
            popup.remove();
            document.removeEventListener('pointerdown', closeOnClickOutside);
        }
    };
    setTimeout(() => {
        document.addEventListener('pointerdown', closeOnClickOutside);
    }, 100);
}

function chainCallback(object, property, callback) {
    if (object == undefined) {
        return;
    }
    if (property in object) {
        const callback_orig = object[property];
        object[property] = function () {
            const r = callback_orig.apply(this, arguments);
            callback.apply(this, arguments);
            return r;
        };
    } else {
        object[property] = callback;
    }
}

/**
 * Create an autocomplete dropdown for multi-value string fields
 * @param {Object} widget - The LiteGraph widget
 * @param {Array} validOptions - Array of valid option strings
 * @param {Object} node - The node instance
 */
function addAutocompleteDropdown(widget, validOptions, node) {
    if (!widget || !widget.element) return;
    
    const container = document.createElement('div');
    container.className = 'model-compare-autocomplete';
    container.style.cssText = 'position: relative; display: inline-block;';
    
    // Create dropdown button
    const dropdownBtn = document.createElement('button');
    dropdownBtn.textContent = '▼';
    dropdownBtn.style.cssText = `
        position: absolute;
        right: 4px;
        top: 50%;
        transform: translateY(-50%);
        background: #444;
        border: 1px solid #666;
        border-radius: 3px;
        color: #fff;
        cursor: pointer;
        padding: 2px 6px;
        font-size: 10px;
    `;
    
    // Create dropdown menu
    const dropdown = document.createElement('div');
    dropdown.style.cssText = `
        position: absolute;
        top: 100%;
        right: 0;
        background: #333;
        border: 1px solid #666;
        border-radius: 4px;
        max-height: 200px;
        overflow-y: auto;
        display: none;
        z-index: 1000;
        min-width: 150px;
    `;
    
    validOptions.forEach(option => {
        const item = document.createElement('div');
        item.textContent = option;
        item.style.cssText = `
            padding: 4px 8px;
            cursor: pointer;
            font-size: 12px;
        `;
        item.onmouseenter = () => item.style.background = '#555';
        item.onmouseleave = () => item.style.background = 'transparent';
        item.onclick = () => {
            // Append to current value
            const currentValue = widget.value || '';
            const values = currentValue.split(',').map(v => v.trim()).filter(v => v);
            if (!values.includes(option)) {
                values.push(option);
                widget.value = values.join(', ');
                if (widget.callback) widget.callback(widget.value);
                if (node.onPropertyChanged) node.onPropertyChanged(widget.name, widget.value);
            }
            dropdown.style.display = 'none';
        };
        dropdown.appendChild(item);
    });
    
    dropdownBtn.onclick = (e) => {
        e.stopPropagation();
        dropdown.style.display = dropdown.style.display === 'none' ? 'block' : 'none';
    };
    
    // Close dropdown when clicking outside
    document.addEventListener('click', () => {
        dropdown.style.display = 'none';
    });
    
    container.appendChild(dropdownBtn);
    container.appendChild(dropdown);
    
    // Try to attach to widget element
    if (widget.element && widget.element.parentNode) {
        widget.element.parentNode.style.position = 'relative';
        widget.element.parentNode.appendChild(container);
    }
}

let registerAttempts = 0;
const maxAttempts = 100;

function tryRegisterExtension() {
    registerAttempts++;

    if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
        const app = window.comfyAPI.app.app;
        registerExtension(app);
        return;
    }

    if (registerAttempts < maxAttempts) {
        setTimeout(tryRegisterExtension, 50);
    }
}

function registerExtension(app) {
    app.registerExtension({
        name: "comfyui-model-compare",

        async beforeRegisterNodeDef(nodeType, nodeData, app) {
            // --- ModelCompareLoaders Logic ---
            if (nodeData.name === "ModelCompareLoaders") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 630;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;

                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                w.origComputeSize = w.computeSize;
                            }
                        });

                        const updateVisibility = () => {
                            const getVal = (name, defaultVal) => {
                                const w = self.widgets.find(w => w.name === name);
                                return w ? w.value : defaultVal;
                            };

                            const num_diffusion_models = getVal("num_diffusion_models", 1);
                            const num_vae_variations = getVal("num_vae_variations", 1);
                            const num_loras = getVal("num_loras", 0);
                            const num_clip_variations = getVal("num_clip_variations", 1);
                            const preset = getVal("preset", "STANDARD");
                            const baked_vae_clip = getVal("baked_vae_clip", false);

                            // Define preset flags
                            const isWAN22 = preset === "WAN2.2";
                            const isFLUX = preset === "FLUX";
                            const isHUNYUAN = preset === "HUNYUAN_VIDEO";

                            self.widgets.forEach((widget) => {
                                if (!widget.name) {
                                    widget.computeSize = widget.origComputeSize;
                                    return;
                                }

                                const alwaysShow = [
                                    "preset", "diffusion_model", "num_diffusion_models",
                                    "num_vae_variations", "num_clip_variations", "num_loras",
                                    "clip_type", "clip_device"
                                ];

                                if (alwaysShow.includes(widget.name) || widget.type === "button") {
                                    widget.computeSize = widget.origComputeSize;
                                    return;
                                }

                                let shouldShow = false;

                                // --- Base Model Fields ---
                                if (widget.name === "baked_vae_clip") {
                                    // Only show if model name starts with [Checkpoint]
                                    const diffModel = getVal("diffusion_model", "NONE");
                                    shouldShow = diffModel.startsWith("[Checkpoint]");
                                }
                                else if (widget.name === "diffusion_model_label") {
                                    // Always show custom label for base model when we have models
                                    shouldShow = true;
                                }
                                else if (widget.name === "diffusion_model_low") {
                                    // Show for WAN2.2 ONLY if base clip_type is wan22
                                    // DO NOT inherit from global preset - base model controls its own LOW field
                                    const baseClipType = getVal("clip_type", "default");
                                    shouldShow = baseClipType === "wan22";
                                }
                                else if (widget.name === "vae") {
                                    shouldShow = !baked_vae_clip;
                                }
                                else if (widget.name === "clip_model") {
                                    shouldShow = !baked_vae_clip;
                                }
                                else if (widget.name === "clip_model_2") {
                                    // Show second CLIP only for dual-CLIP presets/types
                                    // Dual CLIP: FLUX, Hunyuan Video, Hunyuan 1.5 (NOT WAN 2.1, NOT WAN 2.2)
                                    const baseClipType = getVal("clip_type", "default");
                                    const dualClipPresets = ["flux", "hunyuan_video", "hunyuan_video_15"];
                                    const dualClipTypes = ["flux", "hunyuan_video", "hunyuan_video_15"];
                                    const needsDualClip = dualClipPresets.includes(preset.toLowerCase()) ||
                                                          dualClipTypes.includes(baseClipType);
                                    shouldShow = needsDualClip && !baked_vae_clip;
                                }

                                // --- Model Variations ---
                                else if (widget.name.startsWith("diffusion_model_variation_")) {
                                    const parts = widget.name.split("_");
                                    const isLow = parts[parts.length - 1] === "low";
                                    const isLabel = parts[parts.length - 1] === "label";
                                    let numStr;
                                    if (isLow || isLabel) {
                                        numStr = parts[parts.length - 2];
                                    } else {
                                        numStr = parts[parts.length - 1];
                                    }
                                    const num = parseInt(numStr);

                                    if (num < num_diffusion_models) {
                                        if (isLow) {
                                            // Show _low field ONLY if this variation's own clip_type is wan22
                                            // DO NOT inherit from global preset - each variation controls its own LOW field
                                            const varClipTypeWidget = self.widgets.find(w => w.name === `clip_type_variation_${num}`);
                                            const varClipType = varClipTypeWidget ? varClipTypeWidget.value : "default";
                                            shouldShow = varClipType === "wan22";
                                        } else if (isLabel) {
                                            shouldShow = true; // Always show label for visible variations
                                        } else {
                                            shouldShow = true;
                                        }
                                    }
                                }
                                else if (widget.name.startsWith("baked_vae_clip_variation_")) {
                                    const num = parseInt(widget.name.split("_").pop());
                                    shouldShow = num < num_diffusion_models;
                                }

                                // --- VAE Variations ---
                                else if (widget.name.startsWith("vae_variation_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_vae_variations;
                                }

                                // --- CLIP Variations ---
                                else if (widget.name.startsWith("clip_model_variation_")) {
                                    const parts = widget.name.split("_");
                                    const num = parseInt(parts[3]);
                                    const isSecondary = parts.length > 4 && parts[4] === "2";

                                    if (num < num_clip_variations) {
                                        const clipTypeWidget = self.widgets.find(w => w.name === `clip_type_variation_${num}`);
                                        let clipType = clipTypeWidget ? clipTypeWidget.value : "default";
                                        
                                        let resolvedClipType = clipType;
                                        if (clipType === "default") {
                                            resolvedClipType = preset.toLowerCase();
                                        }
                                        
                                        // Dual CLIP types: FLUX, Hunyuan Video, Hunyuan 1.5 (NOT WAN 2.1, NOT WAN 2.2)
                                        const dualClipTypes = ["flux", "hunyuan_video", "hunyuan_video_15"];
                                        const needsDualClip = dualClipTypes.includes(resolvedClipType);
                                        
                                        if (isSecondary) {
                                            shouldShow = needsDualClip && !baked_vae_clip;
                                        } else {
                                            shouldShow = !baked_vae_clip;
                                        }
                                    }
                                }
                                else if (widget.name.startsWith("clip_type_variation_")) {
                                    const num = parseInt(widget.name.split("_")[3]);
                                    shouldShow = num < num_clip_variations;
                                }
                                else if (widget.name.startsWith("clip_device_variation_")) {
                                    const num = parseInt(widget.name.split("_")[3]);
                                    shouldShow = num < num_clip_variations;
                                }

                                // --- LoRA Fields ---
                                else if (widget.name.startsWith("lora_")) {
                                    const parts = widget.name.split("_");
                                    const loraNum = parseInt(parts[1]);

                                    if (loraNum < num_loras) {
                                        if (widget.name.includes("_low")) {
                                            // Show _low LoRA if preset is WAN2.2 OR base clip_type is wan22
                                            const baseClipType = getVal("clip_type", "default");
                                            shouldShow = isWAN22 || baseClipType === "wan22";
                                        } else if (widget.name.includes("combiner")) {
                                            shouldShow = loraNum < (num_loras - 1);
                                        } else {
                                            shouldShow = true;
                                        }
                                    }
                                }

                                if (shouldShow) {
                                    widget.computeSize = widget.origComputeSize;
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 630;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        const triggerWidgets = [
                            "preset", "num_diffusion_models", "num_vae_variations",
                            "num_clip_variations", "num_loras", "baked_vae_clip", "diffusion_model"
                        ];

                        for (let i = 1; i < 5; i++) {
                            triggerWidgets.push(`baked_vae_clip_variation_${i}`);
                            triggerWidgets.push(`clip_type_variation_${i}`);
                            triggerWidgets.push(`diffusion_model_variation_${i}`);
                        }

                        triggerWidgets.forEach(name => {
                            const w = self.widgets.find(w => w.name === name);
                            if (w) {
                                const originalCallback = w.callback;
                                w.callback = function (value) {
                                    if (originalCallback) originalCallback.call(this, value);
                                    updateVisibility();
                                };
                            }
                        });

                        const buttonCallback = () => {
                            updateVisibility();
                        };

                        this.addWidget("button", "Update Inputs", null, buttonCallback);

                        setTimeout(() => {
                            updateVisibility();
                        }, 50);

                        // Add canvas dividers between variation groups
                        const originalOnDrawForeground = self.onDrawForeground;
                        self.onDrawForeground = function(ctx) {
                            if (originalOnDrawForeground) {
                                originalOnDrawForeground.call(this, ctx);
                            }
                            
                            // Get current variation count
                            const numWidget = this.widgets.find(w => w.name === "num_diffusion_models");
                            const numVariations = numWidget ? parseInt(numWidget.value, 10) : 1;
                            
                            if (numVariations <= 1) return; // No dividers needed for single model
                            
                            // Find the Y positions where each variation group starts
                            // Look for diffusion_model_variation_i widgets
                            const dividerPositions = [];
                            
                            for (let i = 1; i < numVariations; i++) {
                                const varWidget = this.widgets.find(w => w.name === `diffusion_model_variation_${i}`);
                                if (varWidget) {
                                    // Find the widget index to calculate Y position
                                    const widgetIndex = this.widgets.indexOf(varWidget);
                                    if (widgetIndex >= 0) {
                                        // Calculate Y position based on visible widgets before this one
                                        let yPos = LiteGraph.NODE_TITLE_HEIGHT;
                                        for (let j = 0; j < widgetIndex; j++) {
                                            const w = this.widgets[j];
                                            if (w.computeSize) {
                                                const size = w.computeSize(this.size[0]);
                                                if (size[1] > 0) {
                                                    yPos += size[1] + 4; // Widget height + spacing
                                                }
                                            } else {
                                                yPos += 20; // Default widget height
                                            }
                                        }
                                        // Only add divider if widget is visible (has height)
                                        if (varWidget.computeSize) {
                                            const varSize = varWidget.computeSize(this.size[0]);
                                            if (varSize[1] > 0) {
                                                dividerPositions.push({y: yPos, variation: i});
                                            }
                                        }
                                    }
                                }
                            }
                            
                            // Draw dividers
                            if (dividerPositions.length > 0) {
                                const nodeWidth = this.size[0];
                                
                                dividerPositions.forEach(pos => {
                                    const y = pos.y - 6; // Position slightly above the widget
                                    
                                    // Draw gradient divider line
                                    const gradient = ctx.createLinearGradient(10, 0, nodeWidth - 10, 0);
                                    gradient.addColorStop(0, "rgba(100, 150, 255, 0)");
                                    gradient.addColorStop(0.1, "rgba(100, 150, 255, 0.6)");
                                    gradient.addColorStop(0.5, "rgba(100, 150, 255, 0.8)");
                                    gradient.addColorStop(0.9, "rgba(100, 150, 255, 0.6)");
                                    gradient.addColorStop(1, "rgba(100, 150, 255, 0)");
                                    
                                    ctx.beginPath();
                                    ctx.strokeStyle = gradient;
                                    ctx.lineWidth = 2;
                                    ctx.moveTo(15, y);
                                    ctx.lineTo(nodeWidth - 15, y);
                                    ctx.stroke();
                                    
                                    // Draw variation label
                                    ctx.fillStyle = "rgba(100, 150, 255, 0.9)";
                                    ctx.font = "bold 10px sans-serif";
                                    ctx.textAlign = "center";
                                    ctx.fillText(`── Model ${pos.variation + 1} ──`, nodeWidth / 2, y - 3);
                                    ctx.textAlign = "left";
                                });
                            }
                        };

                    } catch (e) {
                        console.error("[ModelCompare] Error in onNodeCreated:", e);
                    }
                });
            }

            // --- PromptCompare Logic ---
            if (nodeData.name === "PromptCompare") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    const self = this;
                    // Multiple delays to ensure widgets are fully loaded
                    setTimeout(() => {
                        if (self.size) {
                            self.size[0] = 450;
                        }
                        // Trigger visibility update after configure
                        if (self._updatePromptVisibility) {
                            self._updatePromptVisibility();
                        }
                    }, 50);
                    // Additional delayed update for slow widget loading
                    setTimeout(() => {
                        if (self._updatePromptVisibility) {
                            self._updatePromptVisibility();
                        }
                    }, 300);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;

                        // Store origComputeSize for all widgets
                        const ensureOrigComputeSize = () => {
                            self.widgets.forEach((w) => {
                                if (!w.origComputeSize) {
                                    if (typeof w.computeSize === 'function') {
                                        w.origComputeSize = w.computeSize;
                                    } else {
                                        w.origComputeSize = () => [200, 60]; // Default for text widgets
                                    }
                                }
                            });
                        };

                        const updatePromptVisibility = () => {
                            ensureOrigComputeSize();
                            
                            // Get mode widgets (names must match Python INPUT_TYPES exactly)
                            const promptSourceWidget = self.widgets.find((x) => x.name === "prompt_source");
                            const fileLoadModeWidget = self.widgets.find((x) => x.name === "file_load_mode");
                            const numPosWidget = self.widgets.find((x) => x.name === "num_positive_prompts");
                            const numNegWidget = self.widgets.find((x) => x.name === "num_negative_prompts");
                            
                            const promptSource = promptSourceWidget ? promptSourceWidget.value : "manual";
                            const fileLoadMode = fileLoadModeWidget ? fileLoadModeWidget.value : "all";
                            const numPos = numPosWidget ? parseInt(numPosWidget.value, 10) : 1;
                            const numNeg = numNegWidget ? parseInt(numNegWidget.value, 10) : 1;
                            
                            const isManualMode = promptSource === "manual";
                            const isFileMode = promptSource === "file";
                            const isRangeMode = fileLoadMode === "range";

                            // Widgets that are always visible
                            const alwaysVisible = ["prompt_source", "prompt_mode"];
                            
                            // Widgets visible only in manual mode
                            const manualModeWidgets = [
                                "num_positive_prompts", "num_negative_prompts"
                            ];
                            
                            // Widgets visible only in file mode  
                            const fileModeWidgets = ["prompt_file_path", "file_load_mode"];
                            
                            // Widgets visible only in file mode with range
                            const fileRangeWidgets = ["file_start_index", "file_end_index", "file_max_prompts"];

                            self.widgets.forEach((widget) => {
                                if (!widget.name || widget.type === "button") {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    }
                                    return;
                                }

                                let shouldShow = false;

                                // Always visible widgets
                                if (alwaysVisible.includes(widget.name)) {
                                    shouldShow = true;
                                }
                                // Manual mode widgets
                                else if (manualModeWidgets.includes(widget.name)) {
                                    shouldShow = isManualMode;
                                }
                                // File mode widgets
                                else if (fileModeWidgets.includes(widget.name)) {
                                    shouldShow = isFileMode;
                                }
                                // File range widgets
                                else if (fileRangeWidgets.includes(widget.name)) {
                                    shouldShow = isFileMode && isRangeMode;
                                }
                                // Positive prompts (manual mode only)
                                else if (widget.name.startsWith("positive_prompt_")) {
                                    if (isManualMode) {
                                        const parts = widget.name.split("_");
                                        const num = parseInt(parts[parts.length - 1], 10);
                                        shouldShow = num <= numPos;
                                    } else {
                                        shouldShow = false;
                                    }
                                }
                                // Negative prompts (manual mode only)
                                else if (widget.name.startsWith("negative_prompt_")) {
                                    if (isManualMode) {
                                        const parts = widget.name.split("_");
                                        const num = parseInt(parts[parts.length - 1], 10);
                                        shouldShow = num <= numNeg;
                                    } else {
                                        shouldShow = false;
                                    }
                                }

                                // Apply visibility using both computeSize AND hidden property
                                if (shouldShow) {
                                    widget.computeSize = widget.origComputeSize;
                                    widget.hidden = false;
                                    // Restore original type if it was converted
                                    if (widget._origType) {
                                        widget.type = widget._origType;
                                        delete widget._origType;
                                    }
                                } else {
                                    widget.computeSize = () => [0, -4];
                                    widget.hidden = true;
                                    // For multiline widgets, convert to hidden type
                                    if (widget.type && widget.type !== "converted-widget") {
                                        widget._origType = widget.type;
                                        widget.type = "converted-widget";
                                    }
                                }
                            });

                            // Force node resize
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 450;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        // Store the function on the node for later access
                        self._updatePromptVisibility = updatePromptVisibility;

                        // Add callbacks to control widgets
                        const controlWidgets = [
                            "prompt_source", "file_load_mode", 
                            "num_positive_prompts", "num_negative_prompts"
                        ];
                        
                        controlWidgets.forEach(widgetName => {
                            const widget = self.widgets.find(w => w.name === widgetName);
                            if (widget) {
                                const originalCallback = widget.callback;
                                widget.callback = function (value) {
                                    if (originalCallback) originalCallback.call(this, value);
                                    updatePromptVisibility();
                                };
                            }
                        });

                        // Add Update Inputs button
                        const updateBtn = this.addWidget("button", "Update Inputs", null, () => {
                            updatePromptVisibility();
                        });
                        if (updateBtn && !updateBtn.origComputeSize) {
                            updateBtn.origComputeSize = updateBtn.computeSize || (() => [200, 30]);
                        }

                        // Initial visibility update with multiple delays to ensure widgets are ready
                        // ComfyUI can be slow to create widgets
                        setTimeout(() => updatePromptVisibility(), 50);
                        setTimeout(() => updatePromptVisibility(), 150);
                        setTimeout(() => updatePromptVisibility(), 500);

                    } catch (e) {
                        console.error("[PromptCompare] Error in onNodeCreated:", e);
                    }
                });
            }

            // --- SamplerCompareSimple Logic ---
            if (nodeData.name === "SamplerCompareSimple") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 400;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;

                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                if (typeof w.computeSize === 'function') {
                                    w.origComputeSize = w.computeSize;
                                } else {
                                    w.origComputeSize = () => [200, 20];
                                }
                            }
                        });

                        const updateSamplerVisibility = () => {
                            const presetWidget = self.widgets.find(w => w.name === "preset");
                            const preset = presetWidget ? presetWidget.value : "STANDARD";

                            const isWAN22 = preset === "WAN2.2";
                            const isFLUX = preset === "FLUX" || preset === "FLUX2";
                            const isQWEN = preset === "QWEN";
                            const isHUNYUAN = preset === "HUNYUAN_VIDEO" || preset === "HUNYUAN_VIDEO_15";
                            const isWAN = preset === "WAN2.1" || preset === "WAN2.2";

                            self.widgets.forEach((widget) => {
                                let shouldShow = true;

                                if (widget.name === "wan_high_start" || widget.name === "wan_high_end" || widget.name === "wan_low_start" || widget.name === "wan_low_end") {
                                    shouldShow = isWAN22;
                                }
                                else if (widget.name === "flux_guidance") {
                                    shouldShow = isFLUX;
                                }
                                else if (widget.name === "shift") {
                                    shouldShow = isHUNYUAN || isWAN;
                                }
                                else if (widget.name === "shift_low") {
                                    shouldShow = isWAN22;
                                }
                                else if (widget.name === "qwen_shift" || widget.name === "qwen_cfg_norm") {
                                    shouldShow = isQWEN;
                                }

                                if (shouldShow) {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    } else {
                                        widget.computeSize = () => [200, 20];
                                    }
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 400;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        const presetWidget = self.widgets.find(w => w.name === "preset");
                        if (presetWidget) {
                            const originalCallback = presetWidget.callback;
                            presetWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updateSamplerVisibility();
                            };
                        }

                        this.addWidget("button", "Update Inputs", null, () => {
                            updateSamplerVisibility();
                        });

                        setTimeout(() => {
                            updateSamplerVisibility();
                        }, 100);

                    } catch (e) {
                        // Silent fail
                    }
                });
            }

            // --- GridCompare Logic ---
            if (nodeData.name === "GridCompare") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 400;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;

                        // Store original computeSize for all widgets
                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                if (typeof w.computeSize === 'function') {
                                    w.origComputeSize = w.computeSize;
                                } else {
                                    w.origComputeSize = () => [200, 20];
                                }
                            }
                        });

                        const updateGridVisibility = () => {
                            const presetModeWidget = self.widgets.find(w => w.name === "preset_mode");
                            const presetMode = presetModeWidget ? presetModeWidget.value : "manual";

                            const isSmartMode = presetMode === "smart_auto" || presetMode === "smart_custom";
                            const isManualMode = presetMode === "manual";

                            // Widgets shown only in manual mode (user configures axes)
                            const manualOnlyWidgets = [
                                "row_axis", "col_axis", 
                                "nest_axis_1", "nest_axis_2", "nest_axis_3", "nest_axis_4",
                                "nest_axis_5", "nest_axis_6", "nest_axis_7", "nest_axis_8"
                            ];

                            self.widgets.forEach((widget) => {
                                if (!widget.name) return;

                                let shouldShow = true;

                                // In smart_auto mode, hide manual axis controls
                                if (presetMode === "smart_auto") {
                                    if (manualOnlyWidgets.includes(widget.name)) {
                                        shouldShow = false;
                                    }
                                }
                                // In smart_custom mode, show axis controls but grayed out for customization
                                // (they get populated by analyze results)

                                // Apply visibility
                                if (shouldShow) {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    } else {
                                        widget.computeSize = () => [200, 20];
                                    }
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            // Resize node
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 400;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        // Hook preset_mode widget change
                        const presetModeWidget = self.widgets.find(w => w.name === "preset_mode");
                        if (presetModeWidget) {
                            const originalCallback = presetModeWidget.callback;
                            presetModeWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updateGridVisibility();
                            };
                        }

                        // Analyze connected config and suggest optimal layout
                        const analyzeConnectedConfig = async () => {
                            // Find connected config input
                            const configInput = self.inputs?.find(i => i.name === "config");
                            if (!configInput || !configInput.link) {
                                alert("Connect a config input first (from SamplerCompare node)");
                                return;
                            }

                            // Find the source node providing the config
                            const graph = appRef.graph;
                            const link = graph.links[configInput.link];
                            if (!link) {
                                alert("Could not find connected config link");
                                return;
                            }

                            const sourceNode = graph.getNodeById(link.origin_id);
                            if (!sourceNode) {
                                alert("Could not find source config node");
                                return;
                            }

                            // Build a mock config from the source node's values
                            // This traverses upstream to gather model/prompt/sampling variations
                            const buildMockConfig = async () => {
                                const config = {
                                    model_variations: [],
                                    vae_variations: [],
                                    clip_variations: [],
                                    lora_config: [],
                                    prompt_variations: [],
                                    sampling_params: [],
                                    combinations: []
                                };

                                // Find connected upstream nodes
                                const findUpstreamNode = (node, inputName) => {
                                    const input = node.inputs?.find(i => i.name === inputName);
                                    if (input && input.link) {
                                        const upLink = graph.links[input.link];
                                        if (upLink) {
                                            return graph.getNodeById(upLink.origin_id);
                                        }
                                    }
                                    return null;
                                };

                                // Extract values from widget by name
                                const getWidgetValue = (node, name, defaultVal = null) => {
                                    const widget = node.widgets?.find(w => w.name === name);
                                    return widget ? widget.value : defaultVal;
                                };

                                // Find ModelCompareLoaders upstream
                                const modelNode = findUpstreamNode(sourceNode, "model") || 
                                                  findUpstreamNode(sourceNode, "loaders");
                                if (modelNode && modelNode.type === "ModelCompareLoaders") {
                                    const numModels = getWidgetValue(modelNode, "num_diffusion_models", 1);
                                    const baseModel = getWidgetValue(modelNode, "diffusion_model", "");
                                    
                                    // Add base model
                                    if (baseModel) {
                                        config.model_variations.push({ 
                                            name: baseModel.split('/').pop(),
                                            display_name: baseModel.split('/').pop() 
                                        });
                                    }
                                    
                                    // Add model variations
                                    for (let i = 1; i < numModels; i++) {
                                        const varModel = getWidgetValue(modelNode, `diffusion_model_variation_${i}`, "");
                                        if (varModel) {
                                            config.model_variations.push({ 
                                                name: varModel.split('/').pop(),
                                                display_name: varModel.split('/').pop() 
                                            });
                                        }
                                    }

                                    // VAE variations
                                    const numVAE = getWidgetValue(modelNode, "num_vae_variations", 1);
                                    const baseVAE = getWidgetValue(modelNode, "vae", "");
                                    if (baseVAE) config.vae_variations.push({ name: baseVAE });
                                    for (let i = 0; i < numVAE; i++) {
                                        const varVAE = getWidgetValue(modelNode, `vae_variation_${i}`, "");
                                        if (varVAE) config.vae_variations.push({ name: varVAE });
                                    }

                                    // LoRA config
                                    const numLoras = getWidgetValue(modelNode, "num_loras", 0);
                                    for (let i = 0; i < numLoras; i++) {
                                        const loraName = getWidgetValue(modelNode, `lora_${i}`, "");
                                        const loraStrengths = getWidgetValue(modelNode, `lora_${i}_strengths`, "1.0");
                                        if (loraName) {
                                            config.lora_config.push({
                                                name: loraName,
                                                strengths: loraStrengths.split(',').map(s => parseFloat(s.trim())).filter(v => !isNaN(v))
                                            });
                                        }
                                    }
                                }

                                // Find PromptCompare upstream
                                const promptNode = findUpstreamNode(sourceNode, "prompt_config") ||
                                                   findUpstreamNode(sourceNode, "prompts");
                                if (promptNode && promptNode.type === "PromptCompare") {
                                    const numPos = getWidgetValue(promptNode, "num_positive_prompts", 1);
                                    const numNeg = getWidgetValue(promptNode, "num_negative_prompts", 1);
                                    
                                    for (let i = 1; i <= numPos; i++) {
                                        const posPrompt = getWidgetValue(promptNode, `positive_prompt_${i}`, "");
                                        for (let j = 1; j <= numNeg; j++) {
                                            const negPrompt = getWidgetValue(promptNode, `negative_prompt_${j}`, "");
                                            config.prompt_variations.push({
                                                positive: posPrompt,
                                                negative: negPrompt
                                            });
                                        }
                                    }
                                }

                                // Find SamplingConfigChain or sampling parameters
                                const samplingNode = findUpstreamNode(sourceNode, "sampling") ||
                                                     findUpstreamNode(sourceNode, "sampling_config");
                                if (samplingNode) {
                                    // Build sampling params from connected chain or simple node
                                    const samplers = getWidgetValue(samplingNode, "sampler_name", "euler");
                                    const schedulers = getWidgetValue(samplingNode, "scheduler", "normal");
                                    const steps = getWidgetValue(samplingNode, "steps", "20");
                                    const cfg = getWidgetValue(samplingNode, "cfg", "7.0");
                                    
                                    config.sampling_params.push({
                                        sampler_name: samplers.includes(',') ? samplers.split(',').map(s => s.trim()) : [samplers],
                                        scheduler: schedulers.includes(',') ? schedulers.split(',').map(s => s.trim()) : [schedulers],
                                        steps: steps.toString().includes(',') ? steps.split(',').map(s => parseInt(s.trim())).filter(v => !isNaN(v)) : [parseInt(steps)],
                                        cfg: cfg.toString().includes(',') ? cfg.split(',').map(s => parseFloat(s.trim())).filter(v => !isNaN(v)) : [parseFloat(cfg)]
                                    });
                                }

                                return config;
                            };

                            try {
                                const mockConfig = await buildMockConfig();
                                
                                // Call the analysis API
                                const response = await fetch('/model_compare/analyze_config', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify(mockConfig)
                                });

                                if (!response.ok) {
                                    const error = await response.json();
                                    alert(`Analysis failed: ${error.error || 'Unknown error'}`);
                                    return;
                                }

                                const result = await response.json();
                                
                                // Apply the layout recommendation to widgets
                                if (result.layout) {
                                    const layout = result.layout;
                                    
                                    // Update row/col axis widgets
                                    const rowAxisWidget = self.widgets.find(w => w.name === "row_axis");
                                    const colAxisWidget = self.widgets.find(w => w.name === "col_axis");
                                    
                                    if (rowAxisWidget && layout.row_axis) {
                                        rowAxisWidget.value = layout.row_axis;
                                        if (rowAxisWidget.callback) rowAxisWidget.callback(layout.row_axis);
                                    }
                                    if (colAxisWidget && layout.col_axis) {
                                        colAxisWidget.value = layout.col_axis;
                                        if (colAxisWidget.callback) colAxisWidget.callback(layout.col_axis);
                                    }
                                    
                                    // Update nest axes
                                    if (layout.nest_levels) {
                                        for (let i = 0; i < 8; i++) {
                                            const nestWidget = self.widgets.find(w => w.name === `nest_axis_${i + 1}`);
                                            if (nestWidget) {
                                                const value = layout.nest_levels[i] || "none";
                                                nestWidget.value = value;
                                                if (nestWidget.callback) nestWidget.callback(value);
                                            }
                                        }
                                    }
                                    
                                    // Show success message
                                    let msg = `Layout optimized!\n`;
                                    msg += `• Row axis: ${layout.row_axis || 'auto'}\n`;
                                    msg += `• Col axis: ${layout.col_axis || 'auto'}\n`;
                                    if (layout.nest_levels?.length > 0) {
                                        msg += `• Nest levels: ${layout.nest_levels.join(' → ')}\n`;
                                    }
                                    msg += `• Total combinations: ${result.analysis?.total_combinations || 'unknown'}`;
                                    
                                    alert(msg);
                                } else {
                                    alert("No layout recommendation available. Config may be too simple.");
                                }

                                // Refresh canvas
                                if (appRef && appRef.graph) {
                                    appRef.graph.setDirtyCanvas(true, true);
                                }

                            } catch (e) {
                                console.error("[GridCompare] Analyze error:", e);
                                alert(`Analysis error: ${e.message}`);
                            }
                        };

                        // Add analyze button
                        this.addWidget("button", "🔍 Analyze & Optimize Layout", null, () => {
                            analyzeConnectedConfig();
                        });

                        // Add update button
                        this.addWidget("button", "Update Inputs", null, () => {
                            updateGridVisibility();
                        });

                        // Initial visibility update
                        setTimeout(() => {
                            updateGridVisibility();
                        }, 100);

                    } catch (e) {
                        console.error("[GridCompare] Error in onNodeCreated:", e);
                    }
                });
            }

            // --- SamplingConfigChain Logic ---
            if (nodeData.name === "SamplingConfigChain") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 400;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;
                        globalAppRef = app; // Store for global popup function

                        // Store original computeSize for all widgets
                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                if (typeof w.computeSize === 'function') {
                                    w.origComputeSize = w.computeSize;
                                } else {
                                    w.origComputeSize = () => [200, 20];
                                }
                            }
                        });

                        const updateConfigVisibility = () => {
                            const configTypeWidget = self.widgets.find(w => w.name === "config_type");
                            const configType = configTypeWidget ? configTypeWidget.value : "STANDARD";

                            // Define which config type shows which fields
                            const isQWEN = configType === "QWEN";
                            const isQWEN_EDIT = configType === "QWEN_EDIT";
                            const isZ_IMAGE = configType === "Z_IMAGE";
                            const isWAN21 = configType === "WAN2.1";
                            const isWAN22 = configType === "WAN2.2";
                            const isHUNYUAN = configType === "HUNYUAN_VIDEO" || configType === "HUNYUAN_VIDEO_15";
                            const isFLUX = configType === "FLUX" || configType === "FLUX2" || configType === "FLUX_KONTEXT";
                            const isVideo = isWAN21 || isWAN22 || isHUNYUAN;

                            // Common fields always shown
                            const alwaysShow = [
                                "config", "variation_index", "config_type",
                                "seed", "seed_control", "steps", "cfg",
                                "sampler_name", "scheduler", "denoise",
                                "width", "height"  // Always show dimensions
                            ];

                            self.widgets.forEach((widget) => {
                                if (!widget.name) return;

                                let shouldShow = false;

                                // Always show common fields and buttons
                                if (alwaysShow.includes(widget.name) || widget.type === "button") {
                                    shouldShow = true;
                                }
                                // Video frame count for video models
                                else if (widget.name === "num_frames") {
                                    shouldShow = isVideo;
                                }
                                // QWEN fields (QWEN and QWEN_EDIT only - NOT Z_IMAGE)
                                else if (widget.name.startsWith("qwen_")) {
                                    shouldShow = isQWEN || isQWEN_EDIT;
                                }
                                // Z_IMAGE/Lumina2 shift (separate from QWEN)
                                else if (widget.name === "lumina_shift") {
                                    shouldShow = isZ_IMAGE;
                                }
                                // WAN 2.1 fields
                                else if (widget.name === "wan_shift") {
                                    shouldShow = isWAN21;
                                }
                                // WAN 2.2 fields
                                else if (widget.name.startsWith("wan22_")) {
                                    shouldShow = isWAN22;
                                }
                                // Hunyuan fields
                                else if (widget.name === "hunyuan_shift") {
                                    shouldShow = isHUNYUAN;
                                }
                                // FLUX fields
                                else if (widget.name === "flux_guidance") {
                                    shouldShow = isFLUX;
                                }
                                // FPS for video models
                                else if (widget.name === "fps") {
                                    shouldShow = isVideo;
                                }

                                // Apply visibility
                                if (shouldShow) {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    } else {
                                        widget.computeSize = () => [200, 20];
                                    }
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            // Resize node
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 400;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        // Hook config_type widget change
                        const configTypeWidget = self.widgets.find(w => w.name === "config_type");
                        if (configTypeWidget) {
                            const originalCallback = configTypeWidget.callback;
                            configTypeWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updateConfigVisibility();
                            };
                        }

                        // Store options on sampler/scheduler widgets for button access
                        const samplerWidget = self.widgets.find(w => w.name === "sampler_name");
                        const schedulerWidget = self.widgets.find(w => w.name === "scheduler");
                        
                        if (samplerWidget) {
                            samplerWidget._multiSelectOptions = VALID_SAMPLERS;
                            samplerWidget._multiSelectFieldName = "Sampler";
                        }
                        if (schedulerWidget) {
                            schedulerWidget._multiSelectOptions = VALID_SCHEDULERS;
                            schedulerWidget._multiSelectFieldName = "Scheduler";
                        }

                        // Add multi-select button for sampler
                        this.addWidget("button", "🎲 Select Samplers", null, () => {
                            const w = self.widgets.find(w => w.name === "sampler_name");
                            if (w) {
                                const fakeEvent = { clientX: 300, clientY: 300 };
                                showMultiSelectPopup(w, VALID_SAMPLERS, "Sampler", fakeEvent);
                            }
                        });
                        
                        // Add multi-select button for scheduler
                        this.addWidget("button", "📅 Select Schedulers", null, () => {
                            const w = self.widgets.find(w => w.name === "scheduler");
                            if (w) {
                                const fakeEvent = { clientX: 300, clientY: 300 };
                                showMultiSelectPopup(w, VALID_SCHEDULERS, "Scheduler", fakeEvent);
                            }
                        });

                        // Add update button
                        this.addWidget("button", "Update Inputs", null, () => {
                            updateConfigVisibility();
                        });

                        // Initial visibility update
                        setTimeout(() => {
                            updateConfigVisibility();
                        }, 100);

                    } catch (e) {
                        console.error("[SamplingConfigChain] Error:", e);
                    }
                });
            }

            // --- LoraCompare Logic ---
            if (nodeData.name === "LoraCompare") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 500;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;

                        // Store original computeSize for all widgets
                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                if (typeof w.computeSize === 'function') {
                                    w.origComputeSize = w.computeSize;
                                } else {
                                    w.origComputeSize = () => [200, 20];
                                }
                            }
                        });

                        const updateLoraVisibility = () => {
                            const numLorasWidget = self.widgets.find(w => w.name === "num_loras");
                            const loraModeWidget = self.widgets.find(w => w.name === "lora_mode");
                            
                            const numLoras = numLorasWidget ? parseInt(numLorasWidget.value, 10) : 1;
                            const loraMode = loraModeWidget ? loraModeWidget.value : "SINGLE";
                            const isHighLow = loraMode === "HIGH_LOW_PAIR";

                            // Always show these
                            const alwaysShow = ["num_loras", "lora_mode"];

                            self.widgets.forEach((widget) => {
                                if (!widget.name) return;

                                let shouldShow = false;

                                // Always show control fields
                                if (alwaysShow.includes(widget.name) || widget.type === "button") {
                                    shouldShow = true;
                                }
                                // LoRA slot fields
                                else if (widget.name.startsWith("lora_")) {
                                    // Parse lora_N or lora_N_something
                                    const match = widget.name.match(/^lora_(\d+)(_(.+))?$/);
                                    if (match) {
                                        const loraNum = parseInt(match[1], 10);
                                        const suffix = match[3] || ""; // strengths, label, low, low_strengths, low_label, combinator
                                        
                                        // Show if within num_loras
                                        if (loraNum < numLoras) {
                                            if (suffix === "" || suffix === "strengths" || suffix === "label") {
                                                // Primary LoRA fields always shown when slot is active
                                                shouldShow = true;
                                            }
                                            else if (suffix === "low" || suffix === "low_strengths" || suffix === "low_label") {
                                                // LOW fields only shown in HIGH_LOW_PAIR mode
                                                shouldShow = isHighLow;
                                            }
                                            else if (suffix === "combinator") {
                                                // Combinator shown if there's another LoRA after this
                                                shouldShow = loraNum < numLoras - 1;
                                            }
                                        }
                                    }
                                }

                                // Apply visibility
                                if (shouldShow) {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    } else {
                                        widget.computeSize = () => [200, 20];
                                    }
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            // Resize node
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 500;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        // Hook num_loras widget change
                        const numLorasWidget = self.widgets.find(w => w.name === "num_loras");
                        if (numLorasWidget) {
                            const originalCallback = numLorasWidget.callback;
                            numLorasWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updateLoraVisibility();
                            };
                        }

                        // Hook lora_mode widget change
                        const loraModeWidget = self.widgets.find(w => w.name === "lora_mode");
                        if (loraModeWidget) {
                            const originalCallback = loraModeWidget.callback;
                            loraModeWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updateLoraVisibility();
                            };
                        }

                        // Add update button
                        this.addWidget("button", "Update Inputs", null, () => {
                            updateLoraVisibility();
                        });

                        // Initial visibility update
                        setTimeout(() => {
                            updateLoraVisibility();
                        }, 100);

                    } catch (e) {
                        console.error("[LoraCompare] Error:", e);
                    }
                });
            }

            // --- SamplerCompareAdvanced Logic ---
            if (nodeData.name === "SamplerCompareAdvanced") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 400;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;
                        globalAppRef = app; // Store for global popup function

                        // Store original computeSize for all widgets
                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                if (typeof w.computeSize === 'function') {
                                    w.origComputeSize = w.computeSize;
                                } else {
                                    w.origComputeSize = () => [200, 20];
                                }
                            }
                        });

                        const updateSamplerVisibility = () => {
                            const numFieldsWidget = self.widgets.find(w => w.name === "num_global_fields");
                            const numFields = numFieldsWidget ? parseInt(numFieldsWidget.value, 10) : 0;

                            // Map param types to which value widget should be shown
                            // NEW: Each param type has its own dedicated STRING widget
                            const paramTypeToValueWidget = {
                                "seed": "global_value_seed",
                                "steps": "global_value_steps",
                                "cfg": "global_value_cfg",
                                "denoise": "global_value_denoise",
                                "sampler_name": "global_value_sampler",
                                "scheduler": "global_value_scheduler",
                            };

                            self.widgets.forEach((widget) => {
                                if (!widget.name) return;

                                let shouldShow = false;

                                // Always show required fields and video inputs
                                const alwaysShow = [
                                    "config", "latent", "num_global_fields",
                                    "video_latent", "start_image", "end_image"
                                ];
                                
                                if (alwaysShow.includes(widget.name) || widget.type === "button") {
                                    shouldShow = true;
                                }
                                // Handle global_param_type_N widgets
                                else if (widget.name.startsWith("global_param_type_")) {
                                    const idx = parseInt(widget.name.split("_")[3], 10);
                                    shouldShow = idx < numFields;
                                }
                                // Handle global_seed_control_N widgets (only shown when param_type is seed)
                                else if (widget.name.startsWith("global_seed_control_")) {
                                    const idx = parseInt(widget.name.split("_")[3], 10);
                                    if (idx < numFields) {
                                        const paramTypeWidget = self.widgets.find(w => w.name === `global_param_type_${idx}`);
                                        const paramType = paramTypeWidget ? paramTypeWidget.value : "NONE";
                                        shouldShow = paramType === "seed";
                                    }
                                }
                                // Handle global_value_*_N widgets
                                else if (widget.name.startsWith("global_value_")) {
                                    // Parse: global_value_seed_0, global_value_steps_1, etc.
                                    const parts = widget.name.split("_");
                                    const idx = parseInt(parts[parts.length - 1], 10);
                                    
                                    // Only show if within num_global_fields
                                    if (idx < numFields) {
                                        // Get the param_type for this index
                                        const paramTypeWidget = self.widgets.find(w => w.name === `global_param_type_${idx}`);
                                        const paramType = paramTypeWidget ? paramTypeWidget.value : "NONE";
                                        
                                        // Determine which value widget type should be shown
                                        const expectedValueType = paramTypeToValueWidget[paramType];
                                        
                                        if (expectedValueType) {
                                            // Build the expected widget name
                                            const expectedName = `${expectedValueType}_${idx}`;
                                            shouldShow = widget.name === expectedName;
                                        }
                                    }
                                }

                                // Apply visibility
                                if (shouldShow) {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    } else {
                                        widget.computeSize = () => [200, 20];
                                    }
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            // Resize node
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 400;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        // Hook num_global_fields widget change
                        const numFieldsWidget = self.widgets.find(w => w.name === "num_global_fields");
                        if (numFieldsWidget) {
                            const originalCallback = numFieldsWidget.callback;
                            numFieldsWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updateSamplerVisibility();
                            };
                        }

                        // Hook all global_param_type_N widgets
                        for (let i = 0; i < 8; i++) {
                            const paramTypeWidget = self.widgets.find(w => w.name === `global_param_type_${i}`);
                            if (paramTypeWidget) {
                                const originalCallback = paramTypeWidget.callback;
                                paramTypeWidget.callback = function (value) {
                                    if (originalCallback) originalCallback.call(this, value);
                                    updateSamplerVisibility();
                                };
                            }
                        }

                        // Add multi-select button for global sampler override
                        this.addWidget("button", "🎲 Select Global Samplers", null, () => {
                            // Find the sampler value widget that's currently visible
                            let samplerWidget = null;
                            for (let i = 0; i < 8; i++) {
                                const paramTypeWidget = self.widgets.find(w => w.name === `global_param_type_${i}`);
                                if (paramTypeWidget && paramTypeWidget.value === "sampler_name") {
                                    samplerWidget = self.widgets.find(w => w.name === `global_value_sampler_${i}`);
                                    break;
                                }
                            }
                            if (samplerWidget) {
                                const fakeEvent = { clientX: 300, clientY: 300 };
                                showMultiSelectPopup(samplerWidget, VALID_SAMPLERS, "Global Sampler", fakeEvent);
                            } else {
                                alert("Please set a global field to 'sampler_name' first.");
                            }
                        });
                        
                        // Add multi-select button for global scheduler override
                        this.addWidget("button", "📅 Select Global Schedulers", null, () => {
                            // Find the scheduler value widget that's currently visible
                            let schedulerWidget = null;
                            for (let i = 0; i < 8; i++) {
                                const paramTypeWidget = self.widgets.find(w => w.name === `global_param_type_${i}`);
                                if (paramTypeWidget && paramTypeWidget.value === "scheduler") {
                                    schedulerWidget = self.widgets.find(w => w.name === `global_value_scheduler_${i}`);
                                    break;
                                }
                            }
                            if (schedulerWidget) {
                                const fakeEvent = { clientX: 300, clientY: 300 };
                                showMultiSelectPopup(schedulerWidget, VALID_SCHEDULERS, "Global Scheduler", fakeEvent);
                            } else {
                                alert("Please set a global field to 'scheduler' first.");
                            }
                        });

                        // Add update button
                        this.addWidget("button", "Update Fields", null, () => {
                            updateSamplerVisibility();
                        });

                        // Initial visibility update
                        setTimeout(() => {
                            updateSamplerVisibility();
                        }, 100);

                    } catch (e) {
                        console.error("[SamplerCompareAdvanced] Error:", e);
                    }
                });
            }

            // --- CompareTracker Logic ---
            if (nodeData.name === "CompareTracker") {
                // Set default size on configure
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 300;
                            this.size[1] = 280;
                        }
                    }, 10);
                });

                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    try {
                        const self = this;
                        const appRef = app;

                        // Initialize tracker state on the node
                        self._trackerData = {
                            status: "idle",
                            total: 0,
                            completed: 0,
                            currentModel: "",
                            modelIndex: 0,
                            totalModels: 0,
                            chain: 0,
                            totalChains: 0,
                            warnings: [],
                            startTime: null,
                            htmlGridPath: null,
                            htmlGridUrl: null,
                            // Timing stats
                            speed: null,
                            avgSpeed: null,
                            elapsedSeconds: 0,
                            etaSeconds: null,
                            currentStep: 0,
                            totalSteps: 0,
                        };

                        // Set default size
                        self.size = [300, 280];

                        // Helper to format speed display like tqdm
                        const formatSpeed = (speed) => {
                            if (speed === null || speed === undefined) return "";
                            if (speed >= 1.0) {
                                return `${speed.toFixed(2)}it/s`;
                            } else if (speed > 0) {
                                return `${(1.0 / speed).toFixed(2)}s/it`;
                            } else if (speed < 0) {
                                // Negative means s/it was stored
                                return `${(-speed).toFixed(2)}s/it`;
                            }
                            return "";
                        };

                        // Helper to format time in human readable format
                        const formatTime = (seconds) => {
                            if (seconds === null || seconds === undefined || seconds < 0) return "";
                            if (seconds < 60) return `${seconds.toFixed(0)}s`;
                            if (seconds < 3600) {
                                const mins = Math.floor(seconds / 60);
                                const secs = Math.floor(seconds % 60);
                                return `${mins}m ${secs}s`;
                            }
                            const hours = Math.floor(seconds / 3600);
                            const mins = Math.floor((seconds % 3600) / 60);
                            return `${hours}h ${mins}m`;
                        };

                        // Custom draw function for the tracker display
                        const originalOnDrawForeground = self.onDrawForeground;
                        self.onDrawForeground = function(ctx) {
                            if (originalOnDrawForeground) {
                                originalOnDrawForeground.call(this, ctx);
                            }
                            
                            const data = this._trackerData || {};
                            const x = 10;
                            let y = 40; // Start below title
                            const lineHeight = 18;
                            const width = this.size[0] - 20;
                            
                            // Background
                            ctx.fillStyle = "#1a1a2e";
                            ctx.fillRect(5, 30, this.size[0] - 10, this.size[1] - 35);
                            
                            // Border
                            ctx.strokeStyle = "#4a4a6a";
                            ctx.lineWidth = 1;
                            ctx.strokeRect(5, 30, this.size[0] - 10, this.size[1] - 35);
                            
                            ctx.font = "12px monospace";
                            
                            // Title
                            ctx.fillStyle = "#88ccff";
                            ctx.textAlign = "center";
                            ctx.fillText("═══ COMPARE TRACKER ═══", this.size[0] / 2, y);
                            y += lineHeight + 5;
                            
                            ctx.textAlign = "left";
                            
                            if (data.status === "idle" || !data.total) {
                                // Idle state
                                ctx.fillStyle = "#888888";
                                ctx.fillText("⏸ Waiting for workflow...", x, y);
                            } else if (data.status === "complete") {
                                // Complete state
                                ctx.fillStyle = "#88ff88";
                                ctx.fillText(`✓ Complete! ${data.total} generated`, x, y);
                                y += lineHeight;
                                
                                // Show total elapsed time
                                if (data.elapsedSeconds > 0) {
                                    ctx.fillStyle = "#aaaaaa";
                                    ctx.fillText(`  Total time: ${formatTime(data.elapsedSeconds)}`, x, y);
                                    y += lineHeight;
                                    
                                    // Show average time per combination
                                    if (data.avgSpeed > 0) {
                                        ctx.fillText(`  Avg: ${formatTime(data.avgSpeed)}/combo`, x, y);
                                        y += lineHeight;
                                    }
                                }
                                
                                // Show HTML Grid Available button
                                if (data.htmlGridUrl) {
                                    y += 5;
                                    ctx.fillStyle = "#88ccff";
                                    ctx.fillText("📊 HTML Grid Available", x, y);
                                    y += lineHeight;
                                    
                                    // Draw a clickable button
                                    const btnX = x;
                                    const btnY = y - 12;
                                    const btnWidth = 130;
                                    const btnHeight = 22;
                                    
                                    // Store button bounds for click detection
                                    this._htmlGridButton = { x: btnX, y: btnY, width: btnWidth, height: btnHeight, url: data.htmlGridUrl };
                                    
                                    // Button background
                                    ctx.fillStyle = "#336699";
                                    ctx.fillRect(btnX, btnY, btnWidth, btnHeight);
                                    
                                    // Button border
                                    ctx.strokeStyle = "#5588bb";
                                    ctx.lineWidth = 1;
                                    ctx.strokeRect(btnX, btnY, btnWidth, btnHeight);
                                    
                                    // Button text
                                    ctx.fillStyle = "#ffffff";
                                    ctx.font = "11px monospace";
                                    ctx.textAlign = "center";
                                    ctx.fillText("🔗 Open HTML Grid", btnX + btnWidth/2, btnY + 15);
                                    ctx.textAlign = "left";
                                    
                                    y += lineHeight + 5;
                                }
                            } else {
                                // Active/sampling state
                                const pct = data.total > 0 ? (data.completed / data.total) * 100 : 0;
                                
                                // Progress text with speed
                                ctx.fillStyle = "#ffffff";
                                let progressText = `Progress: ${data.completed}/${data.total} (${pct.toFixed(0)}%)`;
                                ctx.fillText(progressText, x, y);
                                y += lineHeight;
                                
                                // Progress bar
                                const barWidth = width - 10;
                                const barHeight = 12;
                                const barX = x + 5;
                                const fillWidth = (pct / 100) * barWidth;
                                
                                // Bar background
                                ctx.fillStyle = "#333355";
                                ctx.fillRect(barX, y - 10, barWidth, barHeight);
                                
                                // Bar fill with gradient
                                const gradient = ctx.createLinearGradient(barX, 0, barX + fillWidth, 0);
                                gradient.addColorStop(0, "#4488ff");
                                gradient.addColorStop(1, "#88ccff");
                                ctx.fillStyle = gradient;
                                ctx.fillRect(barX, y - 10, fillWidth, barHeight);
                                
                                // Bar border
                                ctx.strokeStyle = "#6666aa";
                                ctx.strokeRect(barX, y - 10, barWidth, barHeight);
                                
                                y += lineHeight + 5;
                                
                                // Speed and ETA line (like tqdm output)
                                const speedStr = formatSpeed(data.speed);
                                const etaStr = data.etaSeconds > 0 ? formatTime(data.etaSeconds) : "";
                                const elapsedStr = formatTime(data.elapsedSeconds);
                                
                                if (speedStr || etaStr) {
                                    ctx.fillStyle = "#88ff88";
                                    let timingLine = "";
                                    if (speedStr) timingLine += `⚡ ${speedStr}`;
                                    if (etaStr) timingLine += `  ETA: ${etaStr}`;
                                    if (elapsedStr) timingLine += `  [${elapsedStr}]`;
                                    ctx.fillText(timingLine, x, y);
                                    y += lineHeight;
                                }
                                
                                // Step progress within current combination
                                if (data.totalSteps > 0 && data.currentStep > 0) {
                                    ctx.fillStyle = "#aaaaaa";
                                    ctx.font = "11px monospace";
                                    ctx.fillText(`  Step: ${data.currentStep}/${data.totalSteps}`, x, y);
                                    y += lineHeight - 2;
                                    ctx.font = "12px monospace";
                                }
                                
                                // Current model
                                if (data.currentModel) {
                                    ctx.fillStyle = "#cccccc";
                                    const modelText = data.currentModel.length > 25 
                                        ? data.currentModel.substring(0, 22) + "..." 
                                        : data.currentModel;
                                    ctx.fillText(`Model: ${modelText}`, x, y);
                                    y += lineHeight;
                                    
                                    ctx.fillStyle = "#888888";
                                    ctx.fillText(`  (${data.modelIndex + 1}/${data.totalModels})`, x, y);
                                    y += lineHeight;
                                }
                                
                                // Chain info
                                if (data.totalChains > 1) {
                                    ctx.fillStyle = "#aaaaaa";
                                    ctx.fillText(`Chain: ${data.chain}/${data.totalChains}`, x, y);
                                    y += lineHeight;
                                }
                            }
                            
                            // Warnings section (only show if active/preparing, hide when complete)
                            const warnings = data.warnings || [];
                            if (warnings.length > 0 && data.status !== "complete") {
                                y += 5;
                                ctx.fillStyle = "#ffaa44";
                                ctx.fillText("⚠ Warnings:", x, y);
                                y += lineHeight;
                                
                                ctx.fillStyle = "#ff8844";
                                ctx.font = "11px monospace";
                                warnings.slice(0, 2).forEach(w => {
                                    const warnText = w.length > 30 ? w.substring(0, 27) + "..." : w;
                                    ctx.fillText(`  ${warnText}`, x, y);
                                    y += lineHeight - 2;
                                });
                            }
                        };
                        
                        // Add click handler for the HTML Grid button
                        const originalOnMouseDown = self.onMouseDown;
                        self.onMouseDown = function(e, local_pos, graphCanvas) {
                            // Check if click is on HTML Grid button
                            if (this._htmlGridButton && this._trackerData && this._trackerData.htmlGridUrl) {
                                const btn = this._htmlGridButton;
                                const nodeY = 30; // Offset for node title
                                if (local_pos[0] >= btn.x && local_pos[0] <= btn.x + btn.width &&
                                    local_pos[1] >= btn.y && local_pos[1] <= btn.y + btn.height) {
                                    // Open the HTML grid in a new tab
                                    // URL is relative (starts with /), prepend origin
                                    let url = this._trackerData.htmlGridUrl;
                                    if (url.startsWith('/')) {
                                        url = window.location.origin + url;
                                    }
                                    window.open(url, '_blank');
                                    return true;
                                }
                            }
                            if (originalOnMouseDown) {
                                return originalOnMouseDown.call(this, e, local_pos, graphCanvas);
                            }
                            return false;
                        };

                        // Trigger initial redraw
                        setTimeout(() => {
                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        }, 100);

                    } catch (e) {
                        console.error("[CompareTracker] Error:", e);
                    }
                });

                // Handle execution output to update display
                chainCallback(nodeType.prototype, "onExecuted", function (output) {
                    try {
                        if (output) {
                            // Check current state - don't overwrite complete/sampling with preparing
                            const currentStatus = this._trackerData?.status;
                            const outputStatus = output.status?.[0] || output.status || "preparing";
                            
                            // If we're complete, only update if output also says complete
                            // This prevents the tracker from resetting when ComfyUI re-executes the node
                            if (currentStatus === "complete" && outputStatus !== "complete") {
                                // Keep current complete state - don't reset
                                return;
                            }
                            
                            // If we're actively sampling, don't reset to preparing
                            if (currentStatus === "sampling" && outputStatus === "preparing") {
                                return;
                            }
                            
                            // For fresh state or valid transitions, update the data
                            // But preserve WebSocket-updated fields like completed count
                            const currentCompleted = this._trackerData?.completed || 0;
                            const currentTotal = this._trackerData?.total || 0;
                            
                            this._trackerData = {
                                status: outputStatus,
                                total: output.total?.[0] || output.total || currentTotal || 0,
                                completed: currentStatus === "complete" ? currentTotal : currentCompleted,
                                currentModel: this._trackerData?.currentModel || "",
                                modelIndex: this._trackerData?.modelIndex || 0,
                                totalModels: output.models?.[0] || output.models || 0,
                                chain: this._trackerData?.chain || 0,
                                totalChains: output.chains?.[0] || output.chains || 0,
                                warnings: output.warnings?.[0] || output.warnings || [],
                                startTime: this._trackerData?.startTime || Date.now(),
                                // Preserve WebSocket-provided data
                                htmlGridPath: this._trackerData?.htmlGridPath,
                                htmlGridUrl: this._trackerData?.htmlGridUrl,
                            };
                            
                            // Request redraw
                            if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
                                window.comfyAPI.app.app.graph.setDirtyCanvas(true, true);
                            }
                        }
                    } catch (e) {
                        console.error("[CompareTracker] onExecuted error:", e);
                    }
                });
            }
        }
    });
}

// Function to update tracker display with progress data from websocket
function updateTrackerDisplay(node, data) {
    if (!node) return;
    
    const currentStatus = node._trackerData?.status;
    const newStatus = data.status || "sampling";
    
    // Don't downgrade from "complete" to "preparing" or "idle" - preserve completed state
    // Only reset if we're actually starting sampling (status="sampling" with completed=0)
    if (currentStatus === "complete") {
        // Only allow transition FROM complete if:
        // 1. New status is "sampling" AND completed is 0 (new job starting)
        // 2. New status is explicitly "complete" (update to complete state)
        const isNewJobStarting = newStatus === "sampling" && (data.completed_combinations === 0 || data.completed_combinations === undefined);
        const isStillComplete = newStatus === "complete";
        
        if (!isNewJobStarting && !isStillComplete) {
            // Ignore this update - don't overwrite completed state with preparing/idle
            return;
        }
    }
    
    // Update the node's tracker data
    node._trackerData = {
        status: newStatus,
        total: data.total_combinations || 0,
        completed: data.completed_combinations || 0,
        currentModel: data.current_model || "",
        modelIndex: data.current_model_index || 0,
        totalModels: data.total_models || 1,
        chain: data.current_chain || 0,
        totalChains: data.total_chains || 1,
        warnings: data.warnings || [],
        startTime: data.start_time,
        htmlGridPath: data.html_grid_path || null,
        htmlGridUrl: data.html_grid_url || null,
        // Timing stats
        speed: data.speed || null,
        avgSpeed: data.avg_speed || null,
        elapsedSeconds: data.elapsed_seconds || 0,
        etaSeconds: data.eta_seconds || null,
        currentStep: data.current_step || 0,
        totalSteps: data.total_steps || 0,
    };
    
    // Request redraw
    if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
        window.comfyAPI.app.app.graph.setDirtyCanvas(true, true);
    }
}

// Listen for websocket progress messages from the sampler
function setupProgressListener() {
    console.log("[ModelCompare] Setting up progress listener");
    
    // Store reference to our handler
    window._modelCompareProgressHandler = function(data) {
        console.log("[ModelCompare] Progress handler called:", data?.status, data?.completed_combinations, "/", data?.total_combinations);
        if (!data) return;
        
        // Find all CompareTracker nodes and update them
        if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
            const app = window.comfyAPI.app.app;
            if (app.graph) {
                const nodes = app.graph._nodes || [];
                let trackerCount = 0;
                nodes.forEach(node => {
                    if (node.type === "CompareTracker") {
                        trackerCount++;
                        updateTrackerDisplay(node, data);
                    }
                });
                console.log("[ModelCompare] Updated", trackerCount, "CompareTracker nodes");
            }
        }
    };
    
    // Create our own WebSocket connection for progress updates
    // This is more reliable than trying to hook into ComfyUI's socket
    function createProgressSocket() {
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            console.log("[ModelCompare] Creating WebSocket connection to:", wsUrl);
            const ws = new WebSocket(wsUrl);
            
            ws.onopen = function() {
                console.log("[ModelCompare] WebSocket connected");
            };
            
            ws.onmessage = function(event) {
                try {
                    const msg = JSON.parse(event.data);
                    if (msg.type === "model_compare_progress") {
                        console.log("[ModelCompare] Received progress message:", msg.data?.status);
                        window._modelCompareProgressHandler(msg.data);
                    }
                } catch (e) {
                    // Ignore parse errors for binary messages
                }
            };
            
            ws.onclose = function() {
                console.log("[ModelCompare] WebSocket closed, reconnecting in 2s");
                // Reconnect after a delay
                setTimeout(createProgressSocket, 2000);
            };
            
            ws.onerror = function(e) {
                console.warn("[ModelCompare] WebSocket error:", e);
                // Will trigger onclose for reconnect
            };
            
            window._modelCompareSocket = ws;
        } catch (e) {
            console.error("[ModelCompare] WebSocket setup error:", e);
            // Retry after delay
            setTimeout(createProgressSocket, 2000);
        }
    }
    
    // Start the dedicated progress socket
    createProgressSocket();
}

// Setup listener after a short delay
setTimeout(setupProgressListener, 100);

// ======== TOOLBAR BUTTON ========
// Add Model Compare Gallery button to ComfyUI toolbar

function getMCIcon() {
    // MC Logo SVG (simplified for toolbar)
    return `<svg viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg" style="width:20px;height:20px">
        <defs>
            <clipPath id="mc-text-mask">
                <path d="M60 380 L60 130 L130 130 L195 280 L260 130 L330 130 L330 380 L260 380 L260 220 L195 380 L130 220 L130 380 Z" />
                <path d="M482 190 A 130 130 0 1 0 482 320 L 412 290 A 60 60 0 1 1 412 220 Z" />
            </clipPath>
        </defs>
        <rect x="0" y="0" width="512" height="512" fill="#DCEFF5" rx="80"/>
        <g clip-path="url(#mc-text-mask)">
            <rect width="512" height="512" fill="#081226"/>
            <path d="M0 512 V 250 Q 150 350 300 200 T 512 150 V 512 Z" fill="#102240"/>
            <path d="M0 512 V 320 Q 180 420 320 280 T 512 300 V 512 Z" fill="#1A355E"/>
            <path d="M0 512 V 400 Q 200 480 350 350 T 512 380 V 512 Z" fill="#234B8E"/>
        </g>
    </svg>`;
}

function setupToolbarButton() {
    // Wait for app to be ready
    if (!window.comfyAPI?.app?.app?.menu?.settingsGroup) {
        setTimeout(setupToolbarButton, 500);
        return;
    }
    
    try {
        const app = window.comfyAPI.app.app;
        const settingsGroup = app.menu.settingsGroup;
        
        if (!settingsGroup?.element?.parentElement) {
            setTimeout(setupToolbarButton, 500);
            return;
        }
        
        // Check if button already exists
        if (document.getElementById('mc-gallery-btn')) {
            return;
        }
        
        // Create button manually (more reliable across ComfyUI versions)
        const buttonElement = document.createElement('button');
        buttonElement.id = 'mc-gallery-btn';
        buttonElement.className = 'comfyui-button comfyui-menu-mobile-collapse';
        buttonElement.title = 'Model Compare Gallery';
        buttonElement.innerHTML = getMCIcon();
        buttonElement.style.cssText = 'display:flex;align-items:center;justify-content:center;padding:4px 8px;cursor:pointer;';
        buttonElement.addEventListener('click', openGallery);
        
        // Wrap in button group div
        const wrapper = document.createElement('div');
        wrapper.className = 'comfyui-button-group';
        wrapper.appendChild(buttonElement);
        
        settingsGroup.element.before(wrapper);
        
        console.log("[ModelCompare] Gallery toolbar button added");
        
    } catch (e) {
        console.error("[ModelCompare] Error setting up toolbar button:", e);
    }
}

function openGallery() {
    window.open('/model-compare/gallery', '_blank');
}

// Setup toolbar button after a delay
setTimeout(setupToolbarButton, 1000);

tryRegisterExtension();
