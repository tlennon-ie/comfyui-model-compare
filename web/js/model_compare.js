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

let registerAttempts = 0;
const maxAttempts = 100;

function tryRegisterExtension() {
    registerAttempts++;
    
    if (window.comfyAPI && window.comfyAPI.app && window.comfyAPI.app.app) {
        const app = window.comfyAPI.app.app;
        console.log("[ModelCompare] Found ComfyApp at window.comfyAPI.app.app");
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
            if (nodeData.name === "ModelCompareLoaders") {
                console.log("[ModelCompare] Setting up ModelCompareLoaders");
                
                chainCallback(nodeType.prototype, "onNodeCreated", function () {
                    console.log("[ModelCompare] onNodeCreated called for ModelCompareLoaders");
                    
                    try {
                        const self = this;
                        const appRef = app;
                        
                        // Store original widgets list and create index map
                        const allWidgets = [...self.widgets];
                        const widgetMap = {};
                        allWidgets.forEach((w, idx) => {
                            if (w.name) widgetMap[w.name] = { widget: w, index: idx };
                        });
                        
                        const updateVisibility = () => {
                            const num_checkpoints = self.widgets.find(w => w.name === "num_checkpoints")?.value || 0;
                            const num_diffusion_models = self.widgets.find(w => w.name === "num_diffusion_models")?.value || 0;
                            const num_vaes = self.widgets.find(w => w.name === "num_vaes")?.value || 0;
                            const num_text_encoders = self.widgets.find(w => w.name === "num_text_encoders")?.value || 0;
                            const num_loras = self.widgets.find(w => w.name === "num_loras")?.value || 0;
                            
                            console.log(`[ModelCompare] Updating: checkpoints=${num_checkpoints}, diffusion=${num_diffusion_models}, vaes=${num_vaes}, encoders=${num_text_encoders}, loras=${num_loras}`);
                            
                            allWidgets.forEach((widget) => {
                                if (!widget.name) return;
                                
                                let shouldShow = false;
                                
                                if (widget.name.startsWith("num_") || widget.type === "button") {
                                    shouldShow = true;
                                } else if (widget.name.startsWith("checkpoint_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_checkpoints;
                                } else if (widget.name.startsWith("diffusion_model_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_diffusion_models;
                                } else if (widget.name.startsWith("vae_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_vaes;
                                } else if (widget.name.startsWith("text_encoder_")) {
                                    const num = parseInt(widget.name.split("_")[2]);
                                    shouldShow = num < num_text_encoders;
                                } else if (widget.name.startsWith("lora_")) {
                                    const num = parseInt(widget.name.split("_")[1]);
                                    shouldShow = num < num_loras;
                                }
                                
                                // Remove from DOM if hidden, keep in widgets array
                                if (!shouldShow) {
                                    if (widget.element && widget.element.parentNode) {
                                        widget.element.style.display = "none";
                                    }
                                } else {
                                    if (widget.element) {
                                        widget.element.style.display = "";
                                    }
                                }
                            });
                            
                            if (appRef && appRef.canvas) {
                                appRef.canvas.requestDraw();
                            }
                        };
                        
                        const buttonCallback = () => {
                            console.log("[ModelCompare] Update Inputs button clicked");
                            updateVisibility();
                        };
                        
                        this.addWidget("button", "Update Inputs", null, buttonCallback);
                        
                        setTimeout(() => {
                            console.log("[ModelCompare] Initial visibility setup");
                            allWidgets.forEach((widget) => {
                                if (!widget.name || widget.name.startsWith("num_") || widget.type === "button") {
                                    return;
                                }
                                
                                let hide = true;
                                if (widget.name.startsWith("checkpoint_") && widget.name.includes("checkpoint_0")) hide = false;
                                else if (widget.name.startsWith("diffusion_model_") && widget.name.includes("diffusion_model_0")) hide = false;
                                else if (widget.name.startsWith("vae_") && widget.name.includes("vae_0")) hide = false;
                                else if (widget.name.startsWith("text_encoder_") && widget.name.includes("text_encoder_0")) hide = false;
                                else if (widget.name.startsWith("lora_") && widget.name.includes("lora_0")) hide = false;
                                
                                if (widget.element) {
                                    widget.element.style.display = hide ? "none" : "";
                                }
                            });
                            if (appRef && appRef.canvas) {
                                appRef.canvas.requestDraw();
                            }
                        }, 50);
                        
                    } catch (e) {
                        console.error("[ModelCompare] Error in onNodeCreated:", e);
                    }
                });
            }
        }
    });
    
    console.log("[ModelCompare] Extension registered successfully");
}

tryRegisterExtension();
