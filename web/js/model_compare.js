// Model Compare Web Extension
// Adds dynamic "Update Inputs" buttons to Model Compare nodes

console.log("[ModelCompare] model_compare.js loaded");

// Wait for app to be available by checking the global scope
function setupModelCompareExtension() {
    // Check if app is available globally
    if (typeof globalThis.app !== "undefined") {
        console.log("[ModelCompare] App object found in globalThis");
        registerExtension();
        return;
    }
    
    // If not available, wait a bit and try again
    console.log("[ModelCompare] App not ready yet, waiting...");
    setTimeout(() => {
        if (typeof globalThis.app !== "undefined") {
            console.log("[ModelCompare] App object became available");
            registerExtension();
        } else {
            console.log("[ModelCompare] Still waiting for app object...");
            setupModelCompareExtension(); // Try again
        }
    }, 100);
}

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

function registerExtension() {
    const app = globalThis.app;
    
    console.log("[ModelCompare] Registering extension with app object");
    
    // Register the extension with ComfyUI
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
                            
                            alert(`Model Comparison Configuration:\n\n✓ Checkpoints: ${num_checkpoints}\n✓ Diffusion Models: ${num_diffusion_models}\n✓ VAEs: ${num_vaes}\n✓ Text Encoders: ${num_text_encoders}\n✓ LoRAs: ${num_loras}`);
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

// Call setup immediately (will wait for app if needed)
setupModelCompareExtension();
