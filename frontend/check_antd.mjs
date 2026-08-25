
import React from "react";
import ReactDOMServer from "react-dom/server";
import { Typography, Alert, Tag, Button } from "antd";

const { Text, Title } = Typography;

try {
  // Test Text with type="danger"
  const html1 = ReactDOMServer.renderToString(
    React.createElement(Text, { type: "danger" }, "error text")
  );
  console.log("Text danger: OK");

  // Test Alert with type="info"
  const html2 = ReactDOMServer.renderToString(
    React.createElement(Alert, { type: "info", message: "test", description: "desc" })
  );
  console.log("Alert: OK");

  // Test Tag with color
  const html3 = ReactDOMServer.renderToString(
    React.createElement(Tag, { color: "green" }, "test")
  );
  console.log("Tag: OK");

  // Test Button with type="link"
  const html4 = ReactDOMServer.renderToString(
    React.createElement(Button, { type: "link", size: "small" }, "Auto-fix")
  );
  console.log("Button link: OK");

} catch(e) {
  console.log("FAIL:", e.message);
}
