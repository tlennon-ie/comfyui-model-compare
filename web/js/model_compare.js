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
                        
                        const updateVisibility = () => {
                            const num_checkpoints = self.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = self.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = self.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = self.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Updating: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            
                            // Find the node's input container in the DOM
                            const nodeElement = self.element;
                            if (!nodeElement) {
                                console.log("[ModelCompare] Node element not found");
                                return;
                            }
                            
                            // Get all input container divs (ComfyUI structure)
                            const inputContainers = nodeElement.querySelectorAll(".comfy-node-inputs > div");
                            console.log(`[ModelCompare] Found ${inputContainers.length} input containers`);
                            
                            let hiddenCount = 0;
                            let visibleCount = 0;
                            
                            inputContainers.forEach((container, idx) => {
                                // Find the widget by matching text content or data attributes
                                const widget = self.widgets[idx];
                                if (!widget || !widget.name) return;
                                
                                let shouldShow = false;
                                
                                if (widget.name.startsWith("num_") || widget.type === "button") {
                                    shouldShow = true;
                                } else if (widget.name.startsWith("checkpoint_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_checkpoints;
                                } else if (widget.name.startsWith("diffusion_model_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_diffusion_models;
                                } else if (widget.name.startsWith("vae_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_vaes;
                                } else if (widget.name.startsWith("text_encoder_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_text_encoders;
                                } else if (widget.name.startsWith("lora_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_loras;
                                }
                                
                                if (shouldShow) {
                                    container.style.display = "";
                                    visibleCount++;
                                } else {
                                    container.style.display = "none";
                                    hiddenCount++;
                                }
                            });
                            
                            console.log(`[ModelCompare] Visibility updated: ${visibleCount} visible, ${hiddenCount} hidden`);
                            
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
                            
                            const nodeElement = self.element;
                            if (!nodeElement) return;
                            
                            const inputContainers = nodeElement.querySelectorAll(".comfy-node-inputs > div");
                            
                            inputContainers.forEach((container, idx) => {
                                const widget = self.widgets[idx];
                                if (!widget || !widget.name) return;
                                
                                let hide = false;
                                
                                if (widget.name.startsWith("num_") || widget.type === "button") {
                                    hide = false;
                                } else if (widget.name.startsWith("checkpoint_")) {
                                    hide = !widget.name.includes("checkpoint_0");
                                } else if (widget.name.startsWith("diffusion_model_")) {
                                    hide = !widget.name.includes("diffusion_model_0");
                                } else if (widget.name.startsWith("vae_")) {
                                    hide = !widget.name.includes("vae_0");
                                } else if (widget.name.startsWith("text_encoder_")) {
                                    hide = !widget.name.includes("text_encoder_0");
                                } else if (widget.name.startsWith("lora_")) {
                                    hide = !widget.name.includes("lora_0");
                                }
                                
                                container.style.display = hide ? "none" : "";
                            });
                            
                            if (appRef && appRef.canvas) {
                                appRef.canvas.requestDraw();
                            }
                        }, 100);
                        
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
