
import React from "react";
import ReactDOMServer from "react-dom/server";
import { Checkbox, ConfigProvider } from "antd";

try {
  const html = ReactDOMServer.renderToString(
    React.createElement(ConfigProvider, null,
      React.createElement(Checkbox, { checked: false, onChange: () => {} },
        React.createElement("span", null, "Day first (DD/MM/YYYY)")
      )
    )
  );
  console.log("Checkbox render: OK, length:", html.length);
} catch(e) {
  console.log("Checkbox render FAIL:", e.message);
}
