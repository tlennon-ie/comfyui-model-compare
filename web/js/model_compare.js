import { app } from "../../scripts/app.js";

// Register the extension with ComfyUI
app.registerExtension({
    name: "comfyui-model-compare",
    
    async setup() {
        console.log("[ModelCompare] Extension setup called");
    },
    
    async addedToGraph() {
        console.log("[ModelCompare] Added to graph");
    },
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        console.log(`[ModelCompare] Processing node: ${nodeData.name}`);
        
        // Handle ModelCompareLoaders - add update button
        if (nodeData.name === "ModelCompareLoaders") {
            console.log("[ModelCompare] Found ModelCompareLoaders node");
            
            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                console.log("[ModelCompare] Creating ModelCompareLoaders node instance");
                
                // Call original if it exists
                if (originalOnNodeCreated) {
                    originalOnNodeCreated.call(this);
                }
                
                // Add update button at the end
                this.addWidget("button", "Update Inputs", null, () => {
                    console.log("[ModelCompare] Update button clicked on ModelCompareLoaders");
                    
                    const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                    const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                    const num_vaes = this.widgets.find(w => w.name === "num_vaes")?.value || 0;
                    const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                    const num_loras = this.widgets.find(w => w.name === "num_loras")?.value || 0;

                    console.log(`[ModelCompare] Current values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                    
                    // Trigger graph update
                    if (app && app.graph) {
                        app.graph.change();
                    }
                });
            };
        }

        // Handle ModelCompareLoadersAdvanced - add update button
        if (nodeData.name === "ModelCompareLoadersAdvanced") {
            console.log("[ModelCompare] Found ModelCompareLoadersAdvanced node");
            
            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                console.log("[ModelCompare] Creating ModelCompareLoadersAdvanced node instance");
                
                // Call original if it exists
                if (originalOnNodeCreated) {
                    originalOnNodeCreated.call(this);
                }
                
                // Add update button
                this.addWidget("button", "Update Inputs", null, () => {
                    console.log("[ModelCompare] Update button clicked on ModelCompareLoadersAdvanced");
                    
                    if (!this.inputs || this.inputs.length === 0) {
                        console.warn("[ModelCompare] No inputs found on node");
                        return;
                    }

                    console.log(`[ModelCompare] Current inputs count: ${this.inputs.length}`);
                    
                    // Try to find connected config node
                    const configInput = this.inputs.find(input => input.name === "config");
                    if (configInput && configInput.link !== undefined && configInput.link !== null) {
                        console.log("[ModelCompare] Config input is connected");
                        
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

                                    console.log(`[ModelCompare] Connected node values: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                                    
                                    alert(`Connected to ModelCompareLoaders:\n\n- Checkpoints: ${num_checkpoints}\n- Diffusion Models: ${num_diffusion_models}\n- VAEs: ${num_vaes}\n- Text Encoders: ${num_text_encoders}\n- LoRAs: ${num_loras}\n\nNote: Dynamic input regeneration requires ComfyUI server-side support. Please reload the node for changes to take effect.`);
                                } else {
                                    console.warn("[ModelCompare] Could not find source node");
                                }
                            }
                        } catch (e) {
                            console.error("[ModelCompare] Error reading config:", e);
                        }
                    } else {
                        console.warn("[ModelCompare] Config input not connected");
                        alert("Please connect the config output from ModelCompareLoaders to the config input on this node.");
                    }
                    
                    // Trigger graph update
                    if (app && app.graph) {
                        app.graph.change();
                    }
                });
            };
        }
    }
});

console.log("[ModelCompare] Web extension initialized");
