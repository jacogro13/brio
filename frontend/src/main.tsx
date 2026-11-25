import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import { api } from "./api/client";
import { clearToken, makeAuthMiddleware } from "./api/session";
import { LanguageProvider } from "./i18n";
import "highlight.js/styles/github.css";
import "katex/dist/katex.min.css";
import "./index.css";

// A rejected token drops back to the auth page.
api.use(
  makeAuthMiddleware(() => {
    clearToken();
    window.location.reload();
  })
);

// Reads retry once (a blip on the LAN); writes never retry, so nothing is
// sent twice.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1 },
    mutations: { retry: false },
  },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <App />
      </LanguageProvider>
    </QueryClientProvider>
  </StrictMode>
);
