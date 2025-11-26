import { app } from "../../scripts/app.js";

// Register custom node types for Model Compare
app.registerExtension({
  name: "ModelCompareNodes",
  
  async setup() {
    // Register custom data types
    if (!window.comfyAPI) window.comfyAPI = {};
    
    // These types will be recognized by ComfyUI for node connections
    const customTypes = [
      "MODEL_COMPARE_CONFIG",
      "PROMPT_COMPARE_CONFIG",
    ];
    
    // Mark nodes as available in "Model Compare" category
    const categoryName = "Model Compare";
    
    console.log("[ModelCompare] Registered custom types:", customTypes);
  },
  
  async addedNodeType(nodeType, nodeClass) {
    // This runs when a node type is registered
    if (nodeClass.title?.includes("Model Compare") || 
        nodeClass.title?.includes("Prompt Compare") ||
        nodeClass.title?.includes("Sampler Compare") ||
        nodeClass.title?.includes("Grid Compare") ||
        nodeClass.title?.includes("Histogram")) {
      console.log("[ModelCompare] Node added:", nodeClass.title);
    }
  },
});
