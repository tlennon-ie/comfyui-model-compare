import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "ModelCompare.UI",
    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (!nodeData?.category?.includes("model")) {
            return;
        }

        // Handle ModelCompareLoaders - update button for num_* fields
        if (nodeData.name === "ModelCompareLoaders") {
            nodeType.prototype.onNodeCreated = function() {
                // Add update button
                this.addWidget("button", "Update Inputs", null, () => {
                    // Get current num_* values
                    const num_checkpoints = this.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                    const num_diffusion_models = this.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                    const num_vaes = this.widgets.find(w => w.name === "num_vaes")?.value || 0;
                    const num_text_encoders = this.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                    const num_loras = this.widgets.find(w => w.name === "num_loras")?.value || 0;

                    console.log("[ModelCompare] Update button clicked");
                    console.log(`  Checkpoints: ${num_checkpoints}, Diffusion Models: ${num_diffusion_models}`);
                    console.log(`  VAEs: ${num_vaes}, Text Encoders: ${num_text_encoders}, LoRAs: ${num_loras}`);

                    // Trigger graph update to propagate config
                    app.graph.change();
                });
            };
        }

        // Handle ModelCompareLoadersAdvanced - dynamic input fields
        if (nodeData.name === "ModelCompareLoadersAdvanced") {
            nodeType.prototype.onNodeCreated = function() {
                this.addWidget("button", "Update Inputs", null, () => {
                    if (!this.inputs) {
                        this.inputs = [];
                    }

                    // Get the config input to determine num_* values
                    const configInput = this.inputs.find(input => input.name === "config");
                    if (!configInput || !configInput.link) {
                        console.warn("[ModelCompare] Config not connected");
                        return;
                    }

                    // Get config from connected node
                    const sourceNode = app.graph.getNodeById(configInput.link.origin_id);
                    if (!sourceNode) {
                        console.warn("[ModelCompare] Could not find source node");
                        return;
                    }

                    const num_checkpoints = sourceNode.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                    const num_diffusion_models = sourceNode.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                    const num_vaes = sourceNode.widgets.find(w => w.name === "num_vaes")?.value || 0;
                    const num_text_encoders = sourceNode.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                    const num_loras = sourceNode.widgets.find(w => w.name === "num_loras")?.value || 0;

                    console.log("[ModelCompare] Updating advanced loader inputs");
                    console.log(`  Expected: ${num_checkpoints} checkpoints, ${num_diffusion_models} diffusion models`);
                    console.log(`  Expected: ${num_vaes} VAEs, ${num_text_encoders} text encoders, ${num_loras} LoRAs`);

                    // Count current inputs of each type
                    const checkpointInputs = this.inputs.filter(input => input.name.startsWith("checkpoint_"));
                    const diffusionInputs = this.inputs.filter(input => input.name.startsWith("diffusion_model_"));
                    const vaeInputs = this.inputs.filter(input => input.name.startsWith("vae_"));
                    const encoderInputs = this.inputs.filter(input => input.name.startsWith("text_encoder_"));
                    const loraInputs = this.inputs.filter(input => input.name.startsWith("lora_") && !input.name.includes("_strengths"));

                    // Update checkpoint inputs
                    const currentCheckpoints = checkpointInputs.length;
                    if (num_checkpoints < currentCheckpoints) {
                        for (let i = 0; i < currentCheckpoints - num_checkpoints; i++) {
                            this.removeInput(this.inputs.length - 1);
                        }
                    } else if (num_checkpoints > currentCheckpoints) {
                        for (let i = currentCheckpoints; i < num_checkpoints; i++) {
                            this.addInput(`checkpoint_${i}`, "COMBO");
                        }
                    }

                    // Update diffusion model inputs
                    const currentDiffusion = diffusionInputs.length;
                    if (num_diffusion_models < currentDiffusion) {
                        for (let i = 0; i < currentDiffusion - num_diffusion_models; i++) {
                            this.removeInput(this.inputs.length - 1);
                        }
                    } else if (num_diffusion_models > currentDiffusion) {
                        for (let i = currentDiffusion; i < num_diffusion_models; i++) {
                            this.addInput(`diffusion_model_${i}`, "COMBO");
                        }
                    }

                    // Update VAE inputs
                    const currentVaes = vaeInputs.length;
                    if (num_vaes < currentVaes) {
                        for (let i = 0; i < currentVaes - num_vaes; i++) {
                            this.removeInput(this.inputs.length - 1);
                        }
                    } else if (num_vaes > currentVaes) {
                        for (let i = currentVaes; i < num_vaes; i++) {
                            this.addInput(`vae_${i}`, "COMBO");
                        }
                    }

                    // Update text encoder inputs
                    const currentEncoders = encoderInputs.length;
                    if (num_text_encoders < currentEncoders) {
                        for (let i = 0; i < currentEncoders - num_text_encoders; i++) {
                            this.removeInput(this.inputs.length - 1);
                        }
                    } else if (num_text_encoders > currentEncoders) {
                        for (let i = currentEncoders; i < num_text_encoders; i++) {
                            this.addInput(`text_encoder_${i}`, "COMBO");
                        }
                    }

                    // Update LoRA inputs (also need strength fields)
                    const currentLoras = loraInputs.length;
                    if (num_loras < currentLoras) {
                        const inputsToRemove = (currentLoras - num_loras) * 2; // Each LoRA has 2 inputs
                        for (let i = 0; i < inputsToRemove; i++) {
                            this.removeInput(this.inputs.length - 1);
                        }
                    } else if (num_loras > currentLoras) {
                        for (let i = currentLoras; i < num_loras; i++) {
                            this.addInput(`lora_${i}`, "COMBO");
                        }
                    }

                    app.graph.change();
                });
            };
        }
    }
});
