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
            
            // Handle ModelCompareLoaders - add update button
            if (node.type === "ModelCompareLoaders") {
                console.log("[ModelCompare] Adding button to ModelCompareLoaders instance");
                
                // Add update button using proper widget construction
                const self = node;
                const widget = {
                    name: "update_inputs_button",
                    type: "button",
                    draw: function(ctx, node, widgetWidth, y, widgetHeight) {
                        const show = this.value !== false;
                        const sz = show ? widgetHeight - 4 : 0;
                        const x = 6;
                        ctx.fillStyle = this.bgColor || "#222";
                        ctx.fillRect(0, y, widgetWidth, widgetHeight);
                        ctx.fillStyle = "#fff";
                        ctx.font = "16px Arial";
                        ctx.textAlign = "left";
                        ctx.fillText("Update Inputs", 15, y + 20);
                    },
                    mouse: function(event, pos, node) {
                        if (event.type === "pointerdown") {
                            console.log("[ModelCompare] Update Inputs button clicked");
                            
                            const num_checkpoints = self.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = self.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = self.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = self.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;

                            console.log(`[ModelCompare] Values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            alert(`Loaders configured for:\n- ${num_checkpoints} Checkpoints\n- ${num_diffusion_models} Diffusion Models\n- ${num_vaes} VAEs\n- ${num_text_encoders} Text Encoders\n- ${num_loras} LoRAs`);
                            
                            app.graph.change();
                            return true;
                        }
                    },
                    value: true
                };
                
                node.widgets.push(widget);
                console.log("[ModelCompare] Update Inputs button added to ModelCompareLoaders");
            }

            // Handle ModelCompareLoadersAdvanced - add update button
            if (node.type === "ModelCompareLoadersAdvanced") {
                console.log("[ModelCompare] Adding button to ModelCompareLoadersAdvanced instance");
                
                // Add update button using proper widget construction
                const self = node;
                const widget = {
                    name: "update_inputs_button",
                    type: "button",
                    draw: function(ctx, node, widgetWidth, y, widgetHeight) {
                        const show = this.value !== false;
                        const sz = show ? widgetHeight - 4 : 0;
                        const x = 6;
                        ctx.fillStyle = this.bgColor || "#222";
                        ctx.fillRect(0, y, widgetWidth, widgetHeight);
                        ctx.fillStyle = "#fff";
                        ctx.font = "16px Arial";
                        ctx.textAlign = "left";
                        ctx.fillText("Update Inputs", 15, y + 20);
                    },
                    mouse: function(event, pos, node) {
                        if (event.type === "pointerdown") {
                            console.log("[ModelCompare] Update Inputs button clicked on Advanced loader");
                            
                            if (!self.inputs || self.inputs.length === 0) {
                                console.warn("[ModelCompare] No inputs found");
                                return;
                            }

                            // Try to find connected config node
                            const configInput = self.inputs.find(input => input.name === "config");
                            if (configInput && configInput.link !== undefined && configInput.link !== null) {
                                try {
                                    const sourceLink = app.graph.links[configInput.link];
                                    if (sourceLink) {
                                        const sourceNode = app.graph.getNodeById(sourceLink.origin_id);
                                        if (sourceNode) {
                                            const num_checkpoints = sourceNode.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                                            const num_diffusion_models = sourceNode.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                                            const num_vaes = sourceNode.widgets.find(w => w.name === "num_vaes")?.value || 0;
                                            const num_text_encoders = sourceNode.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                                            const num_loras = sourceNode.widgets.find(w => w.name === "num_loras")?.value || 0;

                                            console.log(`[ModelCompare] Connected values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                                            
                                            alert(`Connected to ModelCompareLoaders:\n\n- Checkpoints: ${num_checkpoints}\n- Diffusion Models: ${num_diffusion_models}\n- VAEs: ${num_vaes}\n- Text Encoders: ${num_text_encoders}\n- LoRAs: ${num_loras}`);
                                            return true;
                                        }
                                    }
                                } catch (e) {
                                    console.error("[ModelCompare] Error reading config:", e);
                                }
                            } else {
                                console.warn("[ModelCompare] Config not connected");
                                alert("Please connect the config output from ModelCompareLoaders");
                                return true;
                            }
                        }
                    },
                    value: true
                };
                
                node.widgets.push(widget);
                console.log("[ModelCompare] Update Inputs button added to ModelCompareLoadersAdvanced");
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

// Call setup immediately (will wait for app if needed)
setupModelCompareExtension();
