// Overrides the client `useApi()` returns. Only tests need it: without a
// provider, hooks use the app-wide `api`. Kept apart from useApi.ts because a
// .tsx file may only export components (react-refresh).
import type { ReactNode } from "react";
import { ApiContext, type ApiClient } from "./useApi";

export function ApiProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}
