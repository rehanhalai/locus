import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, HashRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "./lib/query-client";
import "./index.css";
import App from "./App.tsx";

const isElectron =
  typeof window !== "undefined" &&
  (window.location.protocol === "file:" || navigator.userAgent.includes("Electron"));

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {isElectron ? (
        <HashRouter>
          <App />
        </HashRouter>
      ) : (
        <BrowserRouter>
          <App />
        </BrowserRouter>
      )}
    </QueryClientProvider>
  </StrictMode>
);
