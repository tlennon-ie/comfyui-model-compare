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
                            const num_model_variations = self.widgets.find(w => w.name === "num_model_variations")?.value || 1;
                            const num_vae_variations = self.widgets.find(w => w.name === "num_vae_variations")?.value || 1;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Updating: model_variations=${num_model_variations}, vae_variations=${num_vae_variations}, loras=${num_loras}`);
                            
                            let hiddenCount = 0;
                            let visibleCount = 0;
                            
                            // Update computeSize for all widgets based on visibility
                            self.widgets.forEach((widget) => {
                                if (!widget.name) {
                                    // Always show unnamed widgets
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                    return;
                                }
                                
                                // Always show base fields and control widgets
                                const baseFields = ["base_model", "vae", "clip_model", "clip_type"];
                                const controlFields = ["num_model_variations", "num_vae_variations", "num_loras"];
                                
                                if (baseFields.includes(widget.name) || 
                                    controlFields.includes(widget.name) || 
                                    widget.type === "button") {
                                    widget.computeSize = widget.origComputeSize;
                                    visibleCount++;
                                    return;
                                }
                                
                                let shouldShow = false;
                                
                                // Model variations - show indices 1 through num_model_variations-1
                                if (widget.name.startsWith("model_variation_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_model_variations;
                                }
                                // VAE variations - show indices 1 through num_vae_variations-1
                                else if (widget.name.startsWith("vae_variation_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_vae_variations;
                                }
                                // LoRA pairs (name and strength) - show indices 0 through num_loras-1
                                else if (widget.name.startsWith("lora_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_loras;
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
                            
                            if (appRef && appRef.canvas) {
                                appRef.canvas.requestDraw();
                            }
                        };
                        
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked");
                            updateVisibility();
                        };
                        
                        this.addWidget("button", "Update Inputs", null, buttonCallback);
                        console.log("[ModelCompare] Update Inputs button added");
                        
                        // Initial setup - hide all but first of each type
                        setTimeout(() => {
                            console.log("[ModelCompare] Initial visibility setup");
                            
                            const baseFields = ["base_model", "vae", "clip_model", "clip_type"];
                            const controlFields = ["num_model_variations", "num_vae_variations", "num_loras"];
                            
                            self.widgets.forEach((widget) => {
                                if (!widget.name || baseFields.includes(widget.name) || 
                                    controlFields.includes(widget.name) || widget.type === "button") {
                                    // Always show base and control fields
                                    widget.computeSize = widget.origComputeSize;
                                    return;
                                }
                                
                                let hide = true;
                                
                                // Show only first variation of each type initially
                                if (widget.name.startsWith("model_variation_")) {
                                    hide = !widget.name.includes("model_variation_1");
                                } else if (widget.name.startsWith("vae_variation_")) {
                                    hide = !widget.name.includes("vae_variation_1");
                                } else if (widget.name.startsWith("lora_")) {
                                    hide = true;  // Hide all loras by default
                                }
                                
                                if (hide) {
                                    widget.computeSize = () => [0, -4];
                                } else {
                                    widget.computeSize = widget.origComputeSize;
                                }
                            });
                            
                            // Recalculate node size based on widget sizes
                            if (self.size) {
                                self.setSize(self.computeSize());
                            }
                            
                            if (appRef && appRef.canvas) {
                                appRef.canvas.requestDraw();
                            }
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
