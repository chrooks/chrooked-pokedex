import React from "react";
import ReactDOM from "react-dom/client";
import { registerSW } from "virtual:pwa-register";
import App from "./App";
import "./styles/tokens.css";
import "./styles/global.css";

// #122: the service worker that makes the dex work offline. autoUpdate swaps
// in a new build on the next load; no prompt.
registerSW({ immediate: true });

const rootElement = document.getElementById("app-root");
if (!rootElement) {
  throw new Error("Missing #app-root element");
}

ReactDOM.createRoot(rootElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
