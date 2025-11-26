// ComfyUI web extension entry point
// This file is loaded from: /extensions/comfyui-model-compare/index.js

console.log("[ModelCompare] Web index.js loaded");

// Load the type registration first
const typeRegistrationPath = new URL("./model_compare_types.js", import.meta.url);
import(typeRegistrationPath.href).then(() => {
    console.log("[ModelCompare] Type registration loaded successfully");
}).catch(err => {
    console.error("[ModelCompare] Failed to load type registration:", err);
});

// Load the main model_compare extension
const extensionPath = new URL("./js/model_compare.js", import.meta.url);
console.log(`[ModelCompare] Attempting to load extension from: ${extensionPath}`);

import(extensionPath.href).then(() => {
    console.log("[ModelCompare] Web plugin loaded successfully");
}).catch(err => {
    console.error("[ModelCompare] Failed to load web plugin:", err);
    console.error("[ModelCompare] Error details:", err.message);
});
