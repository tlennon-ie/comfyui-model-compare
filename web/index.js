// ComfyUI web extension entry point
// This file is loaded from: /extensions/comfyui-model-compare/index.js
// We need to import the model_compare.js extension

console.log("[ModelCompare] Web index.js loaded");

// Use import() with the correct relative path from the current directory
const extensionPath = new URL("./js/model_compare.js", import.meta.url);
console.log(`[ModelCompare] Attempting to load extension from: ${extensionPath}`);

import(extensionPath.href).then(() => {
    console.log("[ModelCompare] Web plugin loaded successfully");
}).catch(err => {
    console.error("[ModelCompare] Failed to load web plugin:", err);
    console.error("[ModelCompare] Error details:", err.message);
});
