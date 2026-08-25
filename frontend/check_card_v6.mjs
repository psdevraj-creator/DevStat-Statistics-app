
import React from "react";
import ReactDOMServer from "react-dom/server";
import { Card, ConfigProvider } from "antd";

try {
  // Test 1: Card with styles prop (v6 way)
  const html1 = ReactDOMServer.renderToString(
    React.createElement(ConfigProvider, null,
      React.createElement(Card, { 
        styles: { body: { padding: 12 } }
      }, "test content")
    )
  );
  console.log("Card styles: OK, len:", html1.length);

  // Test 2: Card with bodyStyle (v4/v5 way - deprecated)
  try {
    const html2 = ReactDOMServer.renderToString(
      React.createElement(Card, { 
        bodyStyle: { padding: 12 }
      }, "test content")
    );
    console.log("Card bodyStyle: OK, len:", html2.length);
  } catch(e) {
    console.log("Card bodyStyle: FAIL -", e.message);
  }

} catch(e) {
  console.log("Card FAIL:", e.message);
  console.log("Stack:", e.stack?.split("\n").slice(0,3).join("\n"));
}
