// Model Compare Web Extension
// Adds "Update Inputs" button to Model Compare nodes and handles dynamic visibility

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
                                    // Show for WAN2.2 preset OR if base clip_type is wan22
                                    const baseClipType = getVal("clip_type", "default");
                                    shouldShow = isWAN22 || baseClipType === "wan22";
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
                                            // Show _low field if preset is WAN2.2 OR this variation's clip_type is wan22
                                            const varClipTypeWidget = self.widgets.find(w => w.name === `clip_type_variation_${num}`);
                                            const varClipType = varClipTypeWidget ? varClipTypeWidget.value : "default";
                                            shouldShow = isWAN22 || varClipType === "wan22";
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
        }
    });
}

tryRegisterExtension();
