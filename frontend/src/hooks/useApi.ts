// The API client the hooks use (Blueprint v2, F2), injectable for tests.
//
// Local deviation from Famiglia's hooks, which import `api` directly:
// openapi-fetch captures `fetch` when a client is created, so a test can't swap
// it afterwards. Hooks take their client from `useApi()` instead. The default
// is the app-wide `api` (with the auth middleware from `main.tsx`), so the app
// needs no provider; tests wrap in `<ApiProvider client={…}>` (ApiProvider.tsx)
// with a client on a fake `fetch` (see `src/test/`).
import { createContext, useContext } from "react";
import { api } from "../api/client";

export type ApiClient = typeof api;

export const ApiContext = createContext<ApiClient>(api);

export function useApi(): ApiClient {
  return useContext(ApiContext);
}
