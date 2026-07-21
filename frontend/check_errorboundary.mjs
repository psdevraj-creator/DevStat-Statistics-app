
import React from "react";
import ReactDOMServer from "react-dom/server";
import { Typography, Card, Button } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

const { Text, Title } = Typography;

try {
  const html = ReactDOMServer.renderToString(
    React.createElement("div", { style: { padding: 40, maxWidth: 600, margin: "80px auto" } },
      React.createElement(Card, { style: { borderLeft: "4px solid #e53e3e" } },
        React.createElement(Title, { level: 4, style: { color: "#e53e3e" } }, "Something went wrong"),
        React.createElement("div", { style: { background: "#f8fafc", padding: 16, borderRadius: 6, marginTop: 16, overflow: "auto", maxHeight: 300 } },
          React.createElement(Text, { type: "danger", strong: true }, "Error: "),
          React.createElement(Text, { type: "danger" }, "test message"),
          React.createElement("pre", { style: { fontSize: 11, marginTop: 12, whiteSpace: "pre-wrap" } }, "test stack")
        ),
        React.createElement(Button, { 
          type: "primary", 
          icon: React.createElement(ReloadOutlined),
          onClick: () => {},
          style: { marginTop: 16 }
        }, "Reload Page")
      )
    )
  );
  console.log("ErrorBoundary render: OK, length:", html.length);
} catch(e) {
  console.log("FAIL:", e.message);
  console.log("Stack:", e.stack?.split("\n").slice(0,5).join("\n"));
}
