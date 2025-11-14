// Dynamically load the model compare extension
import("./js/model_compare.js").then(() => {
    console.log("[ModelCompare] Web plugin loaded successfully");
}).catch(err => {
    console.error("[ModelCompare] Failed to load web plugin:", err);
});
