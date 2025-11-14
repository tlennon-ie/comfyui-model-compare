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
                        // Add button widget
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked!");
                            
                            // Get the num_* values from the node's widgets
                            const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = this.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = this.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            
                            // Hide/show widgets based on num_* values
                            this.widgets.forEach((widget, idx) => {
                                let shouldShow = true;
                                
                                // Hide checkpoint widgets beyond num_checkpoints
                                if (widget.name && widget.name.startsWith("checkpoint_")) {
                                    const checkpointNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = checkpointNum < num_checkpoints;
                                }
                                
                                // Hide diffusion_model widgets beyond num_diffusion_models
                                if (widget.name && widget.name.startsWith("diffusion_model_")) {
                                    const diffusionNum = parseInt(widget.name.split("_")[2]);
                                    shouldShow = diffusionNum < num_diffusion_models;
                                }
                                
                                // Hide vae widgets beyond num_vaes
                                if (widget.name && widget.name.startsWith("vae_")) {
                                    const vaeNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = vaeNum < num_vaes;
                                }
                                
                                // Hide text_encoder widgets beyond num_text_encoders
                                if (widget.name && widget.name.startsWith("text_encoder_")) {
                                    const encNum = parseInt(widget.name.split("_")[2]);
                                    shouldShow = encNum < num_text_encoders;
                                }
                                
                                // Hide lora widgets beyond num_loras
                                if (widget.name && widget.name.startsWith("lora_")) {
                                    const loraNum = parseInt(widget.name.split("_")[1]);
                                    shouldShow = loraNum < num_loras;
                                }
                                
                                // Set widget visibility
                                if (widget.element) {
                                    widget.element.style.display = shouldShow ? "" : "none";
                                }
                            });
                            
                            // Trigger graph change to refresh the UI
                            app.graph.change();
                        };
                        
                        // Add widget using addWidget method with button type
                        this.addWidget("button", "Update Inputs", null, buttonCallback);
                        console.log("[ModelCompare] Update Inputs button added successfully via addWidget");
                        
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
