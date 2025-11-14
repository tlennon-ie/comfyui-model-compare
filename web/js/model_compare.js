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
                
                // Create custom button widget
                const buttonWidget = {
                    name: "update_inputs_btn",
                    type: "custom",
                    value: "",
                    draw: function(ctx, node, widgetWidth, y, height) {
                        // Draw button background
                        const bgColor = "#1e1e1e";
                        const textColor = "#ffffff";
                        const hoverColor = "#333333";
                        
                        ctx.fillStyle = this.hovered ? hoverColor : bgColor;
                        ctx.fillRect(0, y, widgetWidth, height);
                        
                        // Draw button border
                        ctx.strokeStyle = "#444444";
                        ctx.lineWidth = 1;
                        ctx.strokeRect(0, y, widgetWidth, height);
                        
                        // Draw button text
                        ctx.fillStyle = textColor;
                        ctx.font = "14px monospace";
                        ctx.textAlign = "center";
                        ctx.textBaseline = "middle";
                        ctx.fillText("Update Inputs", widgetWidth / 2, y + height / 2);
                    },
                    mouse: function(event, pos, node) {
                        if (event.type === "pointerdown") {
                            console.log("[ModelCompare] Update Inputs button clicked!");
                            
                            // Get the num_* values from the node's widgets
                            const num_checkpoints = node.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = node.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = node.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = node.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = node.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            
                            // Show message to user
                            alert(`Model Comparison Configuration:\n\n✓ Checkpoints: ${num_checkpoints}\n✓ Diffusion Models: ${num_diffusion_models}\n✓ VAEs: ${num_vaes}\n✓ Text Encoders: ${num_text_encoders}\n✓ LoRAs: ${num_loras}`);
                            
                            // Trigger graph update to refresh node UI
                            app.graph.change();
                            return true;
                        }
                    },
                    hovered: false,
                };
                
                node.widgets.push(buttonWidget);
                console.log("[ModelCompare] Update Inputs button added successfully");
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

// Call setup immediately (will wait for app if needed)
setupModelCompareExtension();
