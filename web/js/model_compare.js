import { app } from "../../scripts/app.js";

const ModelCompareExtension = {
    name: "comfyui-model-compare.UI",
    
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        // Only process Model Compare nodes
        if (!nodeData.name.includes("ModelCompare")) {
            return;
        }

        // Handle ModelCompareLoaders - update button for num_* fields
        if (nodeData.name === "ModelCompareLoaders") {
            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                if (originalOnNodeCreated) {
                    originalOnNodeCreated.call(this);
                }
                
                // Add update button
                this.addWidget("button", "Update Inputs", null, () => {
                    console.log("[ModelCompare] Update button clicked");
                    
                    const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                    const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                    const num_vaes = this.widgets.find(w => w.name === "num_vaes")?.value || 0;
                    const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                    const num_loras = this.widgets.find(w => w.name === "num_loras")?.value || 0;

                    console.log(`[ModelCompare] Settings: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                    
                    // Trigger graph update
                    if (app.graph) {
                        app.graph.change();
                    }
                });
                
                console.log("[ModelCompare] ModelCompareLoaders node created with Update button");
            };
        }

        // Handle ModelCompareLoadersAdvanced - dynamic input fields
        if (nodeData.name === "ModelCompareLoadersAdvanced") {
            const originalOnNodeCreated = nodeType.prototype.onNodeCreated;
            
            nodeType.prototype.onNodeCreated = function() {
                if (originalOnNodeCreated) {
                    originalOnNodeCreated.call(this);
                }
                
                this.addWidget("button", "Update Inputs", null, () => {
                    console.log("[ModelCompare] Advanced loader Update button clicked");
                    
                    if (!this.inputs) {
                        console.warn("[ModelCompare] No inputs found");
                        return;
                    }

                    // Get the config input to determine num_* values
                    const configInput = this.inputs.find(input => input.name === "config");
                    if (!configInput || !configInput.link) {
                        console.warn("[ModelCompare] Config not connected");
                        return;
                    }

                    // Get config from connected node
                    const sourceLink = app.graph.links[configInput.link];
                    if (!sourceLink) {
                        console.warn("[ModelCompare] Could not find source link");
                        return;
                    }
                    
                    const sourceNode = app.graph.getNodeById(sourceLink.origin_id);
                    if (!sourceNode) {
                        console.warn("[ModelCompare] Could not find source node");
                        return;
                    }

                    const num_checkpoints = sourceNode.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                    const num_diffusion_models = sourceNode.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                    const num_vaes = sourceNode.widgets.find(w => w.name === "num_vaes")?.value || 0;
                    const num_text_encoders = sourceNode.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                    const num_loras = sourceNode.widgets.find(w => w.name === "num_loras")?.value || 0;

                    console.log(`[ModelCompare] Updating to: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);

                    // For now, just log - actual input manipulation would require ComfyUI internals
                    alert(`Click OK to refresh ComfyUI.\n\nExpected inputs:\n- Checkpoints: ${num_checkpoints}\n- Diffusion Models: ${num_diffusion_models}\n- VAEs: ${num_vaes}\n- Text Encoders: ${num_text_encoders}\n- LoRAs: ${num_loras}\n\nThis feature requires ComfyUI server-side support.`);
                    
                    // Trigger graph update
                    if (app.graph) {
                        app.graph.change();
                    }
                });
                
                console.log("[ModelCompare] ModelCompareLoadersAdvanced node created with Update button");
            };
        }
    }
};

app.registerExtension(ModelCompareExtension);

console.log("[ModelCompare] Web extension loaded");
