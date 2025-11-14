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
                        // Function to update visibility based on num_* values
                        const updateWidgetVisibility = () => {
                            // Get the num_* values from the node's widgets
                            const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = this.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = this.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            // Hide/show widgets based on num_* values
                            this.widgets.forEach((widget) => {
                                let shouldShow = false;
                                
                                // Show checkpoint widgets up to num_checkpoints
                                if (widget.name && widget.name.startsWith("checkpoint_")) {
                                    const checkpointNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = checkpointNum < num_checkpoints;
                                }
                                
                                // Show diffusion_model widgets up to num_diffusion_models
                                else if (widget.name && widget.name.startsWith("diffusion_model_")) {
                                    const diffusionNum = parseInt(widget.name.split("_")[2]);
                                    shouldShow = diffusionNum < num_diffusion_models;
                                }
                                
                                // Show vae widgets up to num_vaes
                                else if (widget.name && widget.name.startsWith("vae_")) {
                                    const vaeNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = vaeNum < num_vaes;
                                }
                                
                                // Show text_encoder widgets up to num_text_encoders
                                else if (widget.name && widget.name.startsWith("text_encoder_")) {
                                    const encNum = parseInt(widget.name.split("_")[2]);
                                    shouldShow = encNum < num_text_encoders;
                                }
                                
                                // Show lora and lora_*_strengths widgets up to num_loras
                                else if (widget.name && widget.name.startsWith("lora_")) {
                                    const loraMatch = widget.name.match(/^lora_(\d+)/);
                                    if (loraMatch) {
                                        const loraNum = parseInt(loraMatch[1]);
                                        shouldShow = loraNum < num_loras;
                                    }
                                }
                                
                                // Set widget visibility
                                if (widget.element) {
                                    widget.element.style.display = shouldShow ? "" : "none";
                                }
                            });
                        };
                        
                        // Add button widget
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked!");
                            updateWidgetVisibility();
                            // Trigger graph change to refresh the UI
                            app.graph.change();
                        };
                        
                        // Add the button widget
                        this.addWidget("button", "Update Inputs", null, buttonCallback);
                        console.log("[ModelCompare] Update Inputs button added successfully via addWidget");
                        
                        // On initial creation, hide all but first of each type
                        // This happens after a small delay to ensure widgets are initialized
                        setTimeout(() => {
                            // Set all num_* to 1 by default (only first of each type visible)
                            const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints");
                            const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models");
                            const num_vaes = this.widgets.find(w => w.name === "num_vaes");
                            const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders");
                            const num_loras = this.widgets.find(w => w.name === "num_loras");
                            
                            // Initialize to show only first of each (value = 1 means show first 1)
                            if (!num_checkpoints || num_checkpoints.value === undefined) {
                                // Keep default values from INPUT_TYPES
                            }
                            
                            updateWidgetVisibility();
                        }, 100);
                        
                    } catch (e) {
                        console.error("[ModelCompare] Error adding button:", e);
                    }
                });
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

// Start trying to register the extension
tryRegisterExtension();
