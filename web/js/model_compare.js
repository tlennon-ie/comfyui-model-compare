// Model Compare Web Extension
// Adds dynamic "Update Inputs" buttons to Model Compare nodes

console.log("[ModelCompare] model_compare.js loaded");

// Wait for app to be available
async function setupModelCompareExtension() {
    console.log("[ModelCompare] Waiting for app object...");
    
    // The app object should be available from the parent scope
    if (typeof app === "undefined") {
        console.error("[ModelCompare] App object not available!");
        return;
    }
    
    console.log("[ModelCompare] App object found, registering extension");
    
    // Register the extension with ComfyUI
    app.registerExtension({
        name: "comfyui-model-compare",
        
        async beforeRegisterNodeDef(nodeType, nodeData, app) {
            console.log(`[ModelCompare] beforeRegisterNodeDef called for: ${nodeData.name}`);
            
            // Handle ModelCompareLoaders - add update button
            if (nodeData.name === "ModelCompareLoaders") {
                console.log("[ModelCompare] Setting up ModelCompareLoaders node");
                
                const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
                
                nodeType.prototype.onNodeCreated = function() {
                    console.log("[ModelCompare] Creating ModelCompareLoaders node instance");
                    
                    // Call original if it exists
                    if (originalOnNodeCreated) {
                        originalOnNodeCreated.call(this);
                    }
                    
                    // Add update button
                    this.addWidget("button", "Update Inputs", null, () => {
                        console.log("[ModelCompare] Update Inputs button clicked");
                        
                        const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                        const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                        const num_vaes = this.widgets.find(w => w.name === "num_vaes")?.value || 0;
                        const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                        const num_loras = this.widgets.find(w => w.name === "num_loras")?.value || 0;

                        console.log(`[ModelCompare] Values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                        
                        // Trigger graph update
                        app.graph.change();
                    });
                    
                    console.log("[ModelCompare] Update Inputs button added");
                };
            }

            // Handle ModelCompareLoadersAdvanced - add update button
            if (nodeData.name === "ModelCompareLoadersAdvanced") {
                console.log("[ModelCompare] Setting up ModelCompareLoadersAdvanced node");
                
                const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
                
                nodeType.prototype.onNodeCreated = function() {
                    console.log("[ModelCompare] Creating ModelCompareLoadersAdvanced node instance");
                    
                    // Call original if it exists
                    if (originalOnNodeCreated) {
                        originalOnNodeCreated.call(this);
                    }
                    
                    // Add update button
                    this.addWidget("button", "Update Inputs", null, () => {
                        console.log("[ModelCompare] Update Inputs button clicked on Advanced loader");
                        
                        if (!this.inputs || this.inputs.length === 0) {
                            console.warn("[ModelCompare] No inputs found");
                            return;
                        }

                        // Try to find connected config node
                        const configInput = this.inputs.find(input => input.name === "config");
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
                                    }
                                }
                            } catch (e) {
                                console.error("[ModelCompare] Error reading config:", e);
                            }
                        } else {
                            console.warn("[ModelCompare] Config not connected");
                            alert("Please connect the config output from ModelCompareLoaders");
                        }
                        
                        // Trigger graph update
                        app.graph.change();
                    });
                    
                    console.log("[ModelCompare] Update Inputs button added to Advanced loader");
                };
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

// Call setup immediately (app should be available)
setupModelCompareExtension();
