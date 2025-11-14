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

function registerExtension() {
    const app = globalThis.app;
    
    console.log("[ModelCompare] Registering extension with app object");
    
    // Register the extension with ComfyUI
    app.registerExtension({
        name: "comfyui-model-compare",
        
        async nodeCreated(node, app) {
            console.log(`[ModelCompare] nodeCreated called for: ${node.type}`);
            
            // Only add button to ModelCompareLoaders node
            if (node.type === "ModelCompareLoaders") {
                console.log("[ModelCompare] Adding Update Inputs button to ModelCompareLoaders");
                
                // Use setTimeout to ensure node is fully initialized
                setTimeout(() => {
                    try {
                        const self = node;
                        
                        // Create button widget using ComfyUI's standard approach
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked!");
                            
                            // Get the num_* values from the node's widgets
                            const num_checkpoints = self.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = self.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = self.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = self.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            
                            alert(`Model Comparison Configuration:\n\n✓ Checkpoints: ${num_checkpoints}\n✓ Diffusion Models: ${num_diffusion_models}\n✓ VAEs: ${num_vaes}\n✓ Text Encoders: ${num_text_encoders}\n✓ LoRAs: ${num_loras}`);
                        };
                        
                        // Add widget using addWidget method with button type
                        self.addWidget("button", "Update Inputs", null, buttonCallback);
                        console.log("[ModelCompare] Update Inputs button added successfully via addWidget");
                        
                    } catch (e) {
                        console.error("[ModelCompare] Error adding button:", e);
                    }
                }, 100);
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

// Call setup immediately (will wait for app if needed)
setupModelCompareExtension();
