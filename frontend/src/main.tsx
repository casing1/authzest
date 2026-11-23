import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { takeRepairLaunchToken } from "./repair-client.js";
import "./styles.css";

const initialAIToken = takeRepairLaunchToken(window.location, window.history);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App initialAIToken={initialAIToken} />
  </StrictMode>,
);
