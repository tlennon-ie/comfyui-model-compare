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
                                "seed", "steps", "cfg",
                                "sampler_name", "scheduler", "denoise",
                                "width", "height"  // Always show dimensions
                            ];

                            self.widgets.forEach((widget) => {
                                if (!widget.name) return;

                                let shouldShow = false;

                                // Always show common fields
                                if (alwaysShow.includes(widget.name)) {
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
                            const paramTypeToValueWidget = {
                                "seed": "global_value_int",
                                "steps": "global_value_int",
                                "cfg": "global_value_float",
                                "denoise": "global_value_float",
                                "seed_control": "global_value_seed_control",
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
                                // Handle global_value_*_N widgets
                                else if (widget.name.startsWith("global_value_")) {
                                    // Parse: global_value_int_0, global_value_float_1, etc.
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
        }
    });
}

tryRegisterExtension();
