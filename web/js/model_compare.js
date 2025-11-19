// Model Compare Web Extension
// Adds "Update Inputs" button to Model Compare nodes

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
            if (nodeData.name === "ModelCompareLoaders") {
                console.log("[ModelCompare] Setting up ModelCompareLoaders");
                
                // Add configure hook to restore width when loading workflows
                chainCallback(nodeType.prototype, "configure", function(info) {
                    // Restore the width to 630 after configuration
                    setTimeout(() => {
                        if (this.size) {
                            this.size[0] = 630;
                        }
                    }, 10);
                });
                
                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    console.log("[ModelCompare] onNodeCreated called for ModelCompareLoaders");
                    
                    try {
                        const self = this;
                        const appRef = app;
                        
                        // Store original computeSize for each widget ONCE, on first access
                        self.widgets.forEach((w) => {
                            if (!w.origComputeSize) {
                                w.origComputeSize = w.computeSize;
                            }
                        });
                        
                        const updateVisibility = () => {
                            const num_diffusion_models = self.widgets.find(w => w.name === "num_diffusion_models")?.value || 1;
                            const num_vae_variations = self.widgets.find(w => w.name === "num_vae_variations")?.value || 1;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;
                            const num_clip_variations = self.widgets.find(w => w.name === "num_clip_variations")?.value || 1;
                            const preset = self.widgets.find(w => w.name === "preset")?.value || "QWEN";
                            
                            console.log(`[ModelCompare] Updating visibility: preset=${preset}, model_variations=${num_diffusion_models}, vae_variations=${num_vae_variations}, clip_variations=${num_clip_variations}, loras=${num_loras}`);
                            
                            let hiddenCount = 0;
                            let visibleCount = 0;
                            
                            // Define preset-specific field filters
                            const isQWEN = preset === "QWEN";
                            const isFLUX = preset === "FLUX";
                            
                            // Update computeSize for all widgets based on visibility
                            self.widgets.forEach((widget) => {
                                if (!widget.name) {
                                    // Always show unnamed widgets
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                    return;
                                }
                                
                                // Always show base fields and control widgets
                                const baseFields = ["base_model", "vae", "clip_type", "preset", "diffusion_model"];
                                const controlFields = ["num_diffusion_models", "num_vae_variations", "num_clip_variations", "num_loras"];
                                
                                if (baseFields.includes(widget.name) || 
                                    controlFields.includes(widget.name) || 
                                    widget.type === "button") {
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                    return;
                                }
                                
                                let shouldShow = false;
                                
                                // Model variations - show indices 1 through num_diffusion_models-1
                                if (widget.name.startsWith("model_variation_") || widget.name.startsWith("diffusion_model_variation_")) {
                                    const num = parseInt(widget.name.split("_").pop());
                                    shouldShow = num < num_diffusion_models;
                                }
                                // VAE variations - show indices 1 through num_vae_variations-1
                                else if (widget.name.startsWith("vae_variation_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_vae_variations;
                                }
                                // LoRA fields - show only the ones we need
                                else if (widget.name.startsWith("lora_")) {
                                    const parts = widget.name.split("_");
                                    const loraNum = parseInt(parts[1]);
                                    
                                    // Check if this is a combiner field
                                    if (widget.name.includes("combiner")) {
                                        // Only show combiner if there's a NEXT lora coming
                                        // Combiner for lora_0 only shows if num_loras >= 2
                                        shouldShow = loraNum < (num_loras - 1);
                                    } else {
                                        // Show lora itself if we need it
                                        shouldShow = loraNum < num_loras;
                                    }
                                }
                                // clip_model (singular) - only show for QWEN
                                // For QWEN: clip_model is variation 1, clip_model_1 is variation 2, etc.
                                else if (widget.name === "clip_model") {
                                    shouldShow = isQWEN;
                                }
                                // QWEN-style CLIP variations - single CLIP per variation
                                // clip_model_1, clip_model_2, etc. are additional variations beyond the base clip_model
                                // clip_model is variation 0, clip_model_1 is variation 1, clip_model_2 is variation 2, etc.
                                // With num_clip_variations=1: only clip_model (variation 0) shown
                                // With num_clip_variations=2: clip_model (0) and clip_model_1 (1) shown
                                // With num_clip_variations=3: clip_model (0), clip_model_1 (1), and clip_model_2 (2) shown
                                else if (widget.name.startsWith("clip_model_") && !widget.name.includes("_a") && !widget.name.includes("_b")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = isQWEN && num < num_clip_variations;
                                }
                                // FLUX-style CLIP pair variations - always shown as pairs
                                // clip_model_a and clip_model_b are the first pair (num_clip_variations >= 1)
                                // clip_model_1_a and clip_model_1_b are the second pair (num_clip_variations >= 2)
                                // clip_model_2_a and clip_model_2_b are the third pair (num_clip_variations >= 3)
                                else if (widget.name.match(/^clip_model(_\d+)?_[ab]$/)) {
                                    if (isFLUX) {
                                        // Parse the pair index from the field name
                                        const match = widget.name.match(/^clip_model(?:_(\d+))?_[ab]$/);
                                        const pairIndex = match[1] ? parseInt(match[1]) : 0;
                                        // Show pair if its index is less than num_clip_variations
                                        shouldShow = pairIndex < num_clip_variations;
                                    }
                                }
                                // clip_model_2 should only show for FLUX (it's part of the legacy/base naming)
                                else if (widget.name === "clip_model_2") {
                                    shouldShow = false;  // Don't show this field anymore, use clip_model_a/b instead
                                }
                                
                                if (shouldShow) {
                                    // Show: restore original computeSize
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                } else {
                                    // Hide: return [0, -4] to collapse the space
                                    widget.computeSize = () => [0, -4];
                                    hiddenCount++;
                                }
                            });
                            
                            console.log(`[ModelCompare] Visibility updated: ${visibleCount} visible, ${hiddenCount} hidden`);
                            
                            // Recalculate the node's size based on the new widget sizes
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            
                            // Restore node width after size recalculation
                            self.size[0] = 630;
                            
                            if (appRef && appRef.graph) {
                                appRef.graph.setDirtyCanvas(true, true);
                            }
                        };
                        
                        // Find the preset widget and add change detection
                        const presetWidget = self.widgets.find(w => w.name === "preset");
                        if (presetWidget) {
                            console.log("[ModelCompare] Found preset widget:", presetWidget);
                            const originalCallback = presetWidget.callback;
                            presetWidget.callback = function(value) {
                                console.log(`[ModelCompare] Preset widget callback fired with value: ${value}`);
                                if (originalCallback) {
                                    originalCallback.call(this, value);
                                }
                                console.log("[ModelCompare] Calling updateVisibility after preset change");
                                updateVisibility();
                            };
                            console.log("[ModelCompare] Preset change callback attached");
                        } else {
                            console.warn("[ModelCompare] Could not find preset widget");
                        }
                        
                        // Find num_diffusion_models widget and add change detection
                        const numModelsWidget = self.widgets.find(w => w.name === "num_diffusion_models");
                        if (numModelsWidget) {
                            const originalCallback = numModelsWidget.callback;
                            numModelsWidget.callback = function(value) {
                                if (originalCallback) {
                                    originalCallback.call(this, value);
                                }
                                updateVisibility();
                            };
                        }
                        
                        // Find num_vae_variations widget and add change detection
                        const numVaeWidget = self.widgets.find(w => w.name === "num_vae_variations");
                        if (numVaeWidget) {
                            const originalCallback = numVaeWidget.callback;
                            numVaeWidget.callback = function(value) {
                                if (originalCallback) {
                                    originalCallback.call(this, value);
                                }
                                updateVisibility();
                            };
                        }
                        
                        // Find num_loras widget and add change detection
                        const numLorasWidget = self.widgets.find(w => w.name === "num_loras");
                        if (numLorasWidget) {
                            const originalCallback = numLorasWidget.callback;
                            numLorasWidget.callback = function(value) {
                                if (originalCallback) {
                                    originalCallback.call(this, value);
                                }
                                updateVisibility();
                            };
                        }
                        
                        // Find num_clip_variations widget and add change detection
                        const numClipVariationsWidget = self.widgets.find(w => w.name === "num_clip_variations");
                        if (numClipVariationsWidget) {
                            const originalCallback = numClipVariationsWidget.callback;
                            numClipVariationsWidget.callback = function(value) {
                                if (originalCallback) {
                                    originalCallback.call(this, value);
                                }
                                updateVisibility();
                            };
                        }
                        
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked");
                            updateVisibility();
                        };
                        
                        this.addWidget("button", "Update Inputs", null, buttonCallback);
                        console.log("[ModelCompare] Update Inputs button added");
                        
                        // Set node width to double the default (ComfyUI default is usually 315, so set to ~630)
                        self.size = [630, self.size[1]];
                        
                        // Initial setup
                        setTimeout(() => {
                            console.log("[ModelCompare] Initial visibility setup");
                            updateVisibility();
                        }, 50);
                        
                    } catch (e) {
                        console.error("[ModelCompare] Error in onNodeCreated:", e);
                        console.error(e.stack);
                    }
                });
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

tryRegisterExtension();
