// Renders the app (or a hook) against a FakeServer: a fresh QueryClient with no
// retries, the client injected through ApiProvider, and the language provider.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactNode } from "react";
import App from "../App";
import { createApiClient } from "../api/client";
import { setToken } from "../api/session";
import { ApiProvider } from "../hooks/ApiProvider";
import { LanguageProvider } from "../i18n";
import type { FakeServer } from "./fakeServer";

export function testClient(server: FakeServer) {
  return createApiClient({ baseUrl: "http://test/api", fetch: server.fetch });
}

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

/** A `wrapper` for `render`/`renderHook`: query client + fake API + language. */
export function providersFor(server: FakeServer, queryClient = testQueryClient()) {
  const client = testClient(server);
  return function Providers({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ApiProvider client={client}>
          <LanguageProvider>{children}</LanguageProvider>
        </ApiProvider>
      </QueryClientProvider>
    );
  };
}

/** Render the signed-in app against `server`. */
export function renderApp(server: FakeServer) {
  setToken("test-token");
  const queryClient = testQueryClient();
  return { queryClient, ...render(<App />, { wrapper: providersFor(server, queryClient) }) };
}
