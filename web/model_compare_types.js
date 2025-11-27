import { app } from "../../scripts/app.js";

/**
 * Model Compare - Node Type Registration and Connection Suggestions
 * 
 * This extension:
 * 1. Registers custom data types (MODEL_COMPARE_CONFIG, PROMPT_COMPARE_CONFIG, etc.)
 * 2. Sets up default node suggestions for when users drag connections
 * 3. Adds Model Compare nodes to the suggested connection list for compatible types
 */

// Define the Model Compare node chain mappings
// When an output slot is dragged, these nodes will appear as suggestions
const MODEL_COMPARE_SUGGESTIONS = {
    // Custom types from Model Compare nodes
    "MODEL_COMPARE_CONFIG": {
        // Nodes that can accept MODEL_COMPARE_CONFIG
        input: ["SamplerCompareAdvanced", "GridCompare", "SamplingConfigChain"],
        // Nodes that output MODEL_COMPARE_CONFIG  
        output: ["ModelCompareLoaders", "SamplerCompareAdvanced", "SamplingConfigChain"]
    },
    "PROMPT_COMPARE_CONFIG": {
        input: ["ModelCompareLoaders"],
        output: ["PromptCompare"]
    },
    "LORA_COMPARE_CONFIG": {
        input: ["LoraCompare", "ModelCompareLoaders"],
        output: ["LoraCompare"]
    },
    // Standard ComfyUI types - add our nodes as options
    "IMAGE": {
        input: ["GridCompare", "VideoPreview", "VideoGridPreview", "HistogramAnalyzer", "HistogramComparator"],
        output: ["SamplerCompareAdvanced", "GridCompare", "VideoGridPreview"]
    },
    "STRING": {
        input: ["VideoPreview", "VideoGridPreview"],
        output: ["GridCompare", "SamplerCompareAdvanced"]
    }
};

// Register the extension
app.registerExtension({
    name: "ModelCompareNodes.TypeRegistration",

    async setup() {
        console.log("[ModelCompare] Setting up type registration and connection suggestions...");
        
        // Wait a bit for LiteGraph to be fully loaded
        setTimeout(() => {
            registerConnectionSuggestions();
        }, 500);
    },

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        // Track our nodes for later reference
        const modelCompareNodes = [
            "ModelCompareLoaders",
            "PromptCompare",
            "SamplingConfigChain",
            "LoraCompare",
            "SamplerCompareAdvanced",
            "GridCompare",
            "VideoPreview",
            "VideoGridPreview",
            "HistogramAnalyzer",
            "HistogramComparator"
        ];
        
        if (modelCompareNodes.includes(nodeData.name)) {
            console.log("[ModelCompare] Registered node:", nodeData.name);
        }
    },
});

/**
 * Register Model Compare nodes as default suggestions for connection types
 */
function registerConnectionSuggestions() {
    if (typeof LiteGraph === 'undefined') {
        console.warn("[ModelCompare] LiteGraph not available, skipping connection suggestions");
        return;
    }

    // Initialize slot_types_default if they don't exist
    if (!LiteGraph.slot_types_default_in) {
        LiteGraph.slot_types_default_in = {};
    }
    if (!LiteGraph.slot_types_default_out) {
        LiteGraph.slot_types_default_out = {};
    }

    // Register suggestions for each type
    for (const [slotType, suggestions] of Object.entries(MODEL_COMPARE_SUGGESTIONS)) {
        // Input suggestions (when dragging FROM an output slot)
        if (suggestions.input && suggestions.input.length > 0) {
            if (!LiteGraph.slot_types_default_in[slotType]) {
                LiteGraph.slot_types_default_in[slotType] = [];
            }
            // Add our nodes to the beginning of the list (higher priority)
            for (const nodeName of suggestions.input.reverse()) {
                const arr = LiteGraph.slot_types_default_in[slotType];
                // Remove if already exists
                const idx = arr.indexOf(nodeName);
                if (idx !== -1) {
                    arr.splice(idx, 1);
                }
                // Add to beginning
                arr.unshift(nodeName);
            }
        }

        // Output suggestions (when dragging FROM an input slot)
        if (suggestions.output && suggestions.output.length > 0) {
            if (!LiteGraph.slot_types_default_out[slotType]) {
                LiteGraph.slot_types_default_out[slotType] = [];
            }
            // Add our nodes to the beginning of the list (higher priority)
            for (const nodeName of suggestions.output.reverse()) {
                const arr = LiteGraph.slot_types_default_out[slotType];
                // Remove if already exists
                const idx = arr.indexOf(nodeName);
                if (idx !== -1) {
                    arr.splice(idx, 1);
                }
                // Add to beginning
                arr.unshift(nodeName);
            }
        }
    }

    console.log("[ModelCompare] Connection suggestions registered for types:", Object.keys(MODEL_COMPARE_SUGGESTIONS));
}
