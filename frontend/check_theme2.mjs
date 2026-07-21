
import { theme } from "antd";
console.log("defaultAlgorithm:", typeof theme.defaultAlgorithm);
console.log("is function:", typeof theme.defaultAlgorithm === "function");

// Check if it returns a valid algorithm
try {
  const algo = theme.defaultAlgorithm;
  console.log("algo type:", typeof algo);
} catch(e) {
  console.log("ERROR:", e.message);
}
