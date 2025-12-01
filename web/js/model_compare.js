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
    
    // Buttons row
    const btnRow = document.createElement('div');
    btnRow.style.cssText = `
        display: flex;
        gap: 8px;
        margin-top: 8px;
        padding-top: 8px;
        border-top: 1px solid #444;
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
    
    btnRow.appendChild(clearBtn);
    btnRow.appendChild(closeBtn);
    popup.appendChild(btnRow);
    
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

                    } catch (e) {
                        console.error("[ModelCompare] Error in onNodeCreated:", e);
                    }
                });
            }

            // --- PromptCompare Logic ---
            if (nodeData.name === "PromptCompare") {
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 400;
                        }
                        // Trigger visibility update after configure
                        if (this._updatePromptVisibility) {
                            this._updatePromptVisibility();
                        }
                    }, 50);
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
                            
                            const numWidget = self.widgets.find((x) => x.name === "num_prompt_variations");
                            const num_prompt_variations = numWidget ? parseInt(numWidget.value, 10) : 1;

                            self.widgets.forEach((widget) => {
                                if (!widget.name || widget.type === "button") {
                                    if (widget.origComputeSize) {
                                        widget.computeSize = widget.origComputeSize;
                                    }
                                    return;
                                }

                                // Always show prompt 1 and the slider
                                if (widget.name === "num_prompt_variations" || 
                                    widget.name === "positive_prompt_1" || 
                                    widget.name === "negative_prompt_1") {
                                    widget.computeSize = widget.origComputeSize;
                                    return;
                                }

                                let shouldShow = false;

                                // Check for positive_prompt_N or negative_prompt_N
                                if (widget.name.startsWith("positive_prompt_") || widget.name.startsWith("negative_prompt_")) {
                                    const parts = widget.name.split("_");
                                    const num = parseInt(parts[parts.length - 1], 10);
                                    shouldShow = num <= num_prompt_variations;
                                }

                                if (shouldShow) {
                                    widget.computeSize = widget.origComputeSize;
                                } else {
                                    widget.computeSize = () => [0, -4];
                                }
                            });

                            // Force node resize
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            self.size[0] = 400;

                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };

                        // Store the function on the node for later access
                        self._updatePromptVisibility = updatePromptVisibility;

                        // Add callback to num_prompt_variations widget
                        const numWidget = self.widgets.find(w => w.name === "num_prompt_variations");
                        if (numWidget) {
                            const originalCallback = numWidget.callback;
                            numWidget.callback = function (value) {
                                if (originalCallback) originalCallback.call(this, value);
                                updatePromptVisibility();
                            };
                        }

                        // Add Update Inputs button
                        const updateBtn = this.addWidget("button", "Update Inputs", null, () => {
                            updatePromptVisibility();
                        });
                        if (updateBtn && !updateBtn.origComputeSize) {
                            updateBtn.origComputeSize = updateBtn.computeSize || (() => [200, 30]);
                        }

                        // Initial visibility update with delay to ensure widgets are ready
                        setTimeout(() => {
                            updatePromptVisibility();
                        }, 100);

                    } catch (e) {
                        // Silent fail
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
                        globalAppRef = app;

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

                        // Add multi-select button for sampler
                        this.addWidget("button", "🎲 Select Samplers", null, () => {
                            const samplerWidget = self.widgets.find(w => w.name === "sampler_name");
                            if (samplerWidget) {
                                const fakeEvent = { clientX: 300, clientY: 300 };
                                showMultiSelectPopup(samplerWidget, VALID_SAMPLERS, "Sampler", fakeEvent);
                            } else {
                                console.warn("[SamplingConfigChain] sampler_name widget not found");
                            }
                        });

                        // Add multi-select button for scheduler
                        this.addWidget("button", "📅 Select Schedulers", null, () => {
                            const schedulerWidget = self.widgets.find(w => w.name === "scheduler");
                            if (schedulerWidget) {
                                const fakeEvent = { clientX: 300, clientY: 300 };
                                showMultiSelectPopup(schedulerWidget, VALID_SCHEDULERS, "Scheduler", fakeEvent);
                            } else {
                                console.warn("[SamplingConfigChain] scheduler widget not found");
                            }
                        });

                        // Initial node size
                        setTimeout(() => {
                            if (self.size) {
                                self.size[0] = 400;
                            }
                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        }, 100);

                    } catch (e) {
                        console.error("[SamplingConfigChain] Error:", e);
                    }
                });
            }

            // --- CompareTracker Logic ---
            if (nodeData.name === "CompareTracker") {
                // Set default size on configure
                chainCallback(nodeType.prototype, "configure", function (info) {
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 280;
                            this.size[1] = 240;
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
                        };

                        // Set default size
                        self.size = [280, 240];

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
                                
                                // Show elapsed time if available
                                if (data.elapsed) {
                                    ctx.fillStyle = "#aaaaaa";
                                    ctx.fillText(`  Time: ${data.elapsed}`, x, y);
                                    y += lineHeight;
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
                                
                                // Progress text
                                ctx.fillStyle = "#ffffff";
                                ctx.fillText(`Progress: ${data.completed}/${data.total} (${pct.toFixed(0)}%)`, x, y);
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
                            
                            // Warnings section
                            const warnings = data.warnings || [];
                            if (warnings.length > 0) {
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
                                    const url = window.location.origin + this._trackerData.htmlGridUrl;
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
                            this._trackerData = {
                                status: output.status || "preparing",
                                total: output.total || 0,
                                completed: 0,
                                currentModel: "",
                                modelIndex: 0,
                                totalModels: output.models || 0,
                                chain: 0,
                                totalChains: output.chains || 0,
                                warnings: output.warnings || [],
                                startTime: Date.now(),
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
    
    // Update the node's tracker data
    node._trackerData = {
        status: data.status || "sampling",
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
    };
    
    // Request redraw
    if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
        window.comfyAPI.app.app.graph.setDirtyCanvas(true, true);
    }
}

// Listen for websocket progress messages from the sampler
function setupProgressListener() {
    // Store reference to our handler
    window._modelCompareProgressHandler = function(data) {
        if (!data) return;
        
        // Find all CompareTracker nodes and update them
        if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
            const app = window.comfyAPI.app.app;
            if (app.graph) {
                const nodes = app.graph._nodes || [];
                nodes.forEach(node => {
                    if (node.type === "CompareTracker") {
                        updateTrackerDisplay(node, data);
                    }
                });
            }
        }
    };
    
    // Track if we've successfully hooked
    let hooked = false;
    
    // Method: Find and hook the websocket by searching the api object
    function tryHookApi() {
        try {
            // Try to find the api object in various locations
            let api = null;
            
            // Check common locations
            if (window.comfyAPI?.api) {
                api = window.comfyAPI.api;
            } else if (window.app?.api) {
                api = window.app.api;
            }
            
            if (!api) {
                // Debug: log what we can find
                if (window.comfyAPI) {
                    console.log("[ModelCompare] comfyAPI keys:", Object.keys(window.comfyAPI));
                }
                return false;
            }
            
            // The socket might be a private property or accessed differently
            // Let's search for it
            let socket = null;
            
            // Try direct property
            if (api.socket) {
                socket = api.socket;
            }
            // Try as a getter or through prototype
            else if (api._socket) {
                socket = api._socket;
            }
            // Search through api properties
            else {
                for (const key of Object.keys(api)) {
                    const val = api[key];
                    if (val && val instanceof WebSocket) {
                        socket = val;
                        console.log("[ModelCompare] Found socket at api." + key);
                        break;
                    }
                }
            }
            
            // Also check if api itself might have addEventListener (event emitter pattern)
            if (!socket && api.addEventListener) {
                // ComfyUI api might be an EventTarget
                api.addEventListener("model_compare_progress", function(event) {
                    console.log("[ModelCompare] Got event via api EventTarget");
                    window._modelCompareProgressHandler(event.detail);
                });
                console.log("[ModelCompare] Attached to api as EventTarget");
                hooked = true;
                return true;
            }
            
            if (socket && !socket._modelCompareHooked) {
                socket.addEventListener('message', function(event) {
                    try {
                        const msg = JSON.parse(event.data);
                        if (msg.type === "model_compare_progress") {
                            console.log("[ModelCompare] Progress:", msg.data.completed_combinations, "/", msg.data.total_combinations);
                            window._modelCompareProgressHandler(msg.data);
                        }
                    } catch (e) {}
                });
                socket._modelCompareHooked = true;
                console.log("[ModelCompare] WebSocket listener attached successfully");
                hooked = true;
                return true;
            }
        } catch (e) {
            console.log("[ModelCompare] Hook error:", e);
        }
        return false;
    }
    
    // Also try to find ALL websockets on the page
    function findAllWebSockets() {
        // Check if there are any websockets in the global scope
        const checkLocations = [
            'window.comfyAPI.api.socket',
            'window.comfyAPI.api._socket', 
            'window.app.api.socket',
            'window.app.api._socket',
            'window.comfyAPI.app.app.api.socket',
        ];
        
        for (const loc of checkLocations) {
            try {
                const socket = eval(loc);
                if (socket && socket instanceof WebSocket && !socket._modelCompareHooked) {
                    socket.addEventListener('message', function(event) {
                        try {
                            const msg = JSON.parse(event.data);
                            if (msg.type === "model_compare_progress") {
                                console.log("[ModelCompare] Progress via", loc);
                                window._modelCompareProgressHandler(msg.data);
                            }
                        } catch (e) {}
                    });
                    socket._modelCompareHooked = true;
                    console.log("[ModelCompare] Hooked socket at:", loc);
                    return true;
                }
            } catch (e) {
                // Location doesn't exist
            }
        }
        return false;
    }
    
    // Try hooking periodically until successful
    let attempts = 0;
    const maxAttempts = 60;
    const retryInterval = setInterval(() => {
        attempts++;
        if (tryHookApi() || findAllWebSockets() || attempts >= maxAttempts) {
            clearInterval(retryInterval);
            if (attempts >= maxAttempts && !hooked) {
                console.log("[ModelCompare] WebSocket hook failed. Trying fallback polling...");
                // Fallback: poll for websocket messages by checking a global
                startPollingFallback();
            }
        }
    }, 500);
    
    console.log("[ModelCompare] Progress listener initializing...");
}

// Fallback: Create our own websocket connection to receive messages
function startPollingFallback() {
    console.log("[ModelCompare] Starting polling fallback");
    
    // Create a separate websocket to the same endpoint
    try {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        const ws = new WebSocket(wsUrl);
        
        ws.onopen = function() {
            console.log("[ModelCompare] Fallback WebSocket connected");
        };
        
        ws.onmessage = function(event) {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === "model_compare_progress") {
                    console.log("[ModelCompare] Progress via fallback WS");
                    window._modelCompareProgressHandler(msg.data);
                }
            } catch (e) {}
        };
        
        ws.onerror = function(e) {
            console.log("[ModelCompare] Fallback WS error:", e);
        };
    } catch (e) {
        console.log("[ModelCompare] Could not create fallback WS:", e);
    }
}

// Setup listener after a short delay
setTimeout(setupProgressListener, 100);

tryRegisterExtension();
