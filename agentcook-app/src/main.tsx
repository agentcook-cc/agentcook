import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { installWebVitals } from "./observability/web-vitals";
import "./i18n";
import "./index.css";
import "./styles/hljs-theme.css";

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Mount node #root missing from index.html");
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

installWebVitals({ surface: "app" });
