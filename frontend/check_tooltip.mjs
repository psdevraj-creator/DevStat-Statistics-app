
import React from "react";
import ReactDOMServer from "react-dom/server";
import { Tooltip, Button, ConfigProvider } from "antd";
import { SwapOutlined } from "@ant-design/icons";

try {
  const html = ReactDOMServer.renderToString(
    React.createElement(ConfigProvider, null,
      React.createElement(Tooltip, { 
        title: "Standardize all selected date columns to YYYY-MM-DD format."
      },
        React.createElement(Button, { 
          size: "small", 
          icon: React.createElement(SwapOutlined)
        }, "Fix Date Formats")
      )
    )
  );
  console.log("Tooltip: OK, len:", html.length);
} catch(e) {
  console.log("FAIL:", e.message);
}
