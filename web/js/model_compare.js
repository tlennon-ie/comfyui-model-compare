// Model Compare Web Extension
// Adds "Update Inputs" button to Model Compare nodes and handles dynamic visibility

console.log("[ModelCompare] model_compare.js loaded");

function chainCallback(object, property, callback) {
    if (object == undefined) {
        console.error("[ModelCompare] Tried to add callback to non-existant object");
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
        console.log("[ModelCompare] Found ComfyApp at window.comfyAPI.app.app");
        registerExtension(app);
        return;
    }

    if (registerAttempts < maxAttempts) {
        setTimeout(tryRegisterExtension, 50);
    } else {
        console.error("[ModelCompare] Failed to find proper app after " + maxAttempts + " attempts");
    }
}

function registerExtension(app) {
    console.log("[ModelCompare] Registering extension with app object");

    app.registerExtension({
        name: "comfyui-model-compare",

        async beforeRegisterNodeDef(nodeType, nodeData, app) {
            // --- ModelCompareLoaders Logic ---
            if (nodeData.name === "ModelCompareLoaders") {
                console.log("[ModelCompare] Setting up ModelCompareLoaders");

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

                            let hiddenCount = 0;
                            let visibleCount = 0;

                            self.widgets.forEach((widget) => {
                                if (!widget.name) {
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                    return;
                                }

                                const alwaysShow = [
                                    "preset", "diffusion_model", "num_diffusion_models",
                                    "num_vae_variations", "num_clip_variations", "num_loras",
                                    "clip_type"
                                ];

                                if (alwaysShow.includes(widget.name) || widget.type === "button") {
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
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
                                    shouldShow = isWAN22;
                                }
                                else if (widget.name === "vae") {
                                    shouldShow = !baked_vae_clip;
                                }
                                else if (widget.name === "clip_model") {
                                    shouldShow = !baked_vae_clip;
                                }
                                else if (widget.name === "clip_model_2") {
                                    // Show second CLIP only for dual-CLIP presets/types
                                    const needsDualClip = ["flux", "wan", "hunyuan_video", "hunyuan_video_15"].includes(preset.toLowerCase());
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
                                            shouldShow = isWAN22;
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
                                        
                                        const dualClipTypes = ["flux", "wan", "hunyuan_video", "hunyuan_video_15"];
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

                                // --- LoRA Fields ---
                                else if (widget.name.startsWith("lora_")) {
                                    const parts = widget.name.split("_");
                                    const loraNum = parseInt(parts[1]);

                                    if (loraNum < num_loras) {
                                        if (widget.name.includes("_low")) {
                                            shouldShow = isWAN22;
                                        } else if (widget.name.includes("combiner")) {
                                            shouldShow = loraNum < (num_loras - 1);
                                        } else {
                                            shouldShow = true;
                                        }
                                    }
                                }

                                if (shouldShow) {
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                } else {
                                    widget.computeSize = () => [0, -4];
                                    hiddenCount++;
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
                console.log("[ModelCompare] Setting up PromptCompare");

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
                                w.origComputeSize = w.computeSize;
                            }
                        });

                        const updatePromptVisibility = () => {
                            const getVal = (n, d) => {
                                const w = self.widgets.find((x) => x.name === n);
                                return w ? w.value : d;
                            };

                            const num_prompt_variations = parseInt(getVal("num_prompt_variations", 1), 10);
                            console.log("[ModelCompare] PromptCompare num_prompt_variations:", num_prompt_variations);

                            const alwaysShow = ["positive_prompt_1", "negative_prompt_1", "num_prompt_variations"];

                            self.widgets.forEach((widget) => {
                                if (!widget.name || widget.type === "button") {
                                    widget.computeSize = widget.origComputeSize;
                                    return;
                                }

                                if (alwaysShow.includes(widget.name)) {
                                    widget.computeSize = widget.origComputeSize;
                                    return;
                                }

                                let shouldShow = false;

                                if (widget.name.startsWith("positive_prompt_") || widget.name.startsWith("negative_prompt_")) {
                                    const parts = widget.name.split("_");
                                    const num = parseInt(parts[parts.length - 1], 10);
                                    shouldShow = num <= num_prompt_variations;
                                    if (!shouldShow) {
                                        console.log(`[ModelCompare] Hiding ${widget.name} (num=${num}, max=${num_prompt_variations})`);
                                    }
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

                        const triggerWidgets = ["num_prompt_variations"];

                        triggerWidgets.forEach(name => {
                            const w = self.widgets.find(w => w.name === name);
                            if (w) {
                                const originalCallback = w.callback;
                                w.callback = function (value) {
                                    if (originalCallback) originalCallback.call(this, value);
                                    updatePromptVisibility();
                                };
                            }
                        });

                        // Add Update Inputs button and save its origComputeSize
                        const updateBtn = this.addWidget("button", "Update Inputs", null, () => {
                            updatePromptVisibility();
                        });
                        if (updateBtn && !updateBtn.origComputeSize) {
                            updateBtn.origComputeSize = updateBtn.computeSize;
                        }

                        setTimeout(() => {
                            updatePromptVisibility();
                        }, 50);

                    } catch (e) {
                        console.error("[ModelCompare] Error in PromptCompare onNodeCreated:", e);
                    }
                });
            }

            // --- SamplerCompareSimple Logic ---
            if (nodeData.name === "SamplerCompareSimple") {
                console.log("[ModelCompare] Setting up SamplerCompareSimple");

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
                        console.error("[ModelCompare] Error in Sampler onNodeCreated:", e);
                    }
                });
            }

            // --- GridCompare Logic ---
            if (nodeData.name === "GridCompare") {
                console.log("[ModelCompare] Setting up GridCompare");

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

    console.log("[ModelCompare] Extension registered successfully");
}

tryRegisterExtension();
