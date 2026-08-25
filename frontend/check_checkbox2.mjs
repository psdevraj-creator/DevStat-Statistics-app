
import React from "react";
import ReactDOMServer from "react-dom/server";
import { Checkbox, ConfigProvider } from "antd";

try {
  const html = ReactDOMServer.renderToString(
    React.createElement(ConfigProvider, null,
      React.createElement(Checkbox, { 
        checked: false,
        onChange: () => {}
      },
        React.createElement("span", { style: { fontSize: 12 } }, "Day first (DD/MM/YYYY)")
      )
    )
  );
  console.log("Checkbox with children: OK, len:", html.length);

  // Also test with plain text child
  const html2 = ReactDOMServer.renderToString(
    React.createElement(Checkbox, { checked: true }, "Test label")
  );
  console.log("Checkbox with string: OK, len:", html2.length);

} catch(e) {
  console.log("FAIL:", e.message);
  console.log("Stack:", e.stack?.split("\n").slice(0,3).join("\n"));
}
