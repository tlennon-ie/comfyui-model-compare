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

// Wait for app to be injected into window.comfyAPI
let registerAttempts = 0;
const maxAttempts = 100;

function tryRegisterExtension() {
    registerAttempts++;
    
    // The actual app is at window.comfyAPI.app.app
    if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
        const app = window.comfyAPI.app.app;
        console.log("[ModelCompare] Found ComfyApp at window.comfyAPI.app.app");
        console.log("[ModelCompare] app.registerExtension exists?", typeof app.registerExtension);
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
            console.log(`[ModelCompare] beforeRegisterNodeDef called for: ${nodeData.name}`);
            
            if (nodeData.name === "ModelCompareLoaders") {
                console.log("[ModelCompare] Setting up ModelCompareLoaders");
                
                // Chain the onNodeCreated callback
                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    console.log("[ModelCompare] onNodeCreated called for ModelCompareLoaders instance");
                    
                    try {
                        const self = this;
                        
                        // Function to update visibility based on num_* values
                        const updateWidgetVisibility = () => {
                            console.log("[ModelCompare] updateWidgetVisibility called");
                            
                            // Get the num_* values from the node's widgets
                            const num_checkpoints = self.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = self.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = self.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = self.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Current values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            
                            let visibleCount = 0;
                            
                            // Hide/show widgets based on num_* values
                            self.widgets.forEach((widget) => {
                                let shouldShow = false;
                                
                                // Skip sliders and button - always show
                                if (!widget.name || widget.type === "button" || widget.name.startsWith("num_")) {
                                    shouldShow = true;
                                }
                                
                                // Show checkpoint widgets up to num_checkpoints
                                else if (widget.name.startsWith("checkpoint_")) {
                                    const checkpointNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = checkpointNum < num_checkpoints;
                                }
                                
                                // Show diffusion_model widgets up to num_diffusion_models
                                else if (widget.name.startsWith("diffusion_model_")) {
                                    const diffusionNum = parseInt(widget.name.split("_")[2]);
                                    shouldShow = diffusionNum < num_diffusion_models;
                                }
                                
                                // Show vae widgets up to num_vaes
                                else if (widget.name.startsWith("vae_")) {
                                    const vaeNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = vaeNum < num_vaes;
                                }
                                
                                // Show text_encoder widgets up to num_text_encoders
                                else if (widget.name.startsWith("text_encoder_")) {
                                    const encNum = parseInt(widget.name.split("_")[2]);
                                    shouldShow = encNum < num_text_encoders;
                                }
                                
                                // Show lora and lora_*_strengths widgets up to num_loras
                                else if (widget.name.startsWith("lora_")) {
                                    const loraMatch = widget.name.match(/^lora_(\d+)/);
                                    if (loraMatch) {
                                        const loraNum = parseInt(loraMatch[1]);
                                        shouldShow = loraNum < num_loras;
                                    }
                                }
                                
                                // Use ComfyUI's widget.hidden property
                                widget.hidden = !shouldShow;
                                if (shouldShow) visibleCount++;
                            });
                            
                            console.log(`[ModelCompare] Updated visibility - ${visibleCount} widgets visible`);
                            
                            // Request canvas redraw
                            if (app && app.canvas) {
                                app.canvas.requestDraw();
                            }
                        };
                        
                        // Add button widget
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked!");
                            updateWidgetVisibility();
                        };
                        
                        // Add the button widget
                        this.addWidget("button", "Update Inputs", null, buttonCallback);
                        console.log("[ModelCompare] Update Inputs button added successfully via addWidget");
                        
                        // On initial creation, hide all but first of each type
                        // This happens after a small delay to ensure widgets are initialized
                        setTimeout(() => {
                            console.log("[ModelCompare] Initializing widget visibility");
                            self.widgets.forEach((widget) => {
                                if (!widget.name || widget.type === "button" || widget.name.startsWith("num_")) {
                                    widget.hidden = false;
                                } else if (widget.name.startsWith("checkpoint_")) {
                                    widget.hidden = !widget.name.includes("checkpoint_0");
                                } else if (widget.name.startsWith("diffusion_model_")) {
                                    widget.hidden = !widget.name.includes("diffusion_model_0");
                                } else if (widget.name.startsWith("vae_")) {
                                    widget.hidden = !widget.name.includes("vae_0");
                                } else if (widget.name.startsWith("text_encoder_")) {
                                    widget.hidden = !widget.name.includes("text_encoder_0");
                                } else if (widget.name.startsWith("lora_")) {
                                    widget.hidden = !widget.name.includes("lora_0");
                                }
                            });
                            if (app && app.canvas) {
                                app.canvas.requestDraw();
                            }
                        }, 50);
                        
                    } catch (e) {
                        console.error("[ModelCompare] Error in onNodeCreated:", e);
                    }
                });
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

// Start trying to register the extension
tryRegisterExtension();
