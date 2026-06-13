import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/tokens.css";
import "./styles/global.css";

const rootElement = document.getElementById("app-root");
if (!rootElement) {
  throw new Error("Missing #app-root element");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
