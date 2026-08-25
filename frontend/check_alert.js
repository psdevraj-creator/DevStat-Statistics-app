
const React = require("react");
const antd = require("antd");
const a = antd.Alert;
console.log("isValidElement:", React.isValidElement(a));
const fwd = Symbol.for("react.forward_ref");
const memo = Symbol.for("react.memo");
console.log("isForwardRef:", a["$$typeof"] === fwd);
console.log("isMemo:", a["$$typeof"] === memo);
console.log("typeof:", typeof a);
