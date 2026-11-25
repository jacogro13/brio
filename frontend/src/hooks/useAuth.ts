// Signing in and out (Blueprint v2, F2). The token itself lives in
// api/session.ts; components and App use these instead of importing it.
import { useMutation } from "@tanstack/react-query";
import { clearToken, getToken, getUsername, setToken } from "../api/session";
import type { Lang } from "../i18n/strings";
import { useApi } from "./useApi";

/** True when a token is stored (it may still be rejected by the server). */
export function isSignedIn(): boolean {
  return getToken() !== null;
}

/** The signed-in username, for display only. */
export function currentUsername(): string | null {
  return getUsername();
}

/** Drop the token and go back to the auth page. */
export function logout(): void {
  clearToken();
  window.location.reload();
}

/** Log in and store the token. */
export function useLogin() {
  const api = useApi();
  return useMutation({
    mutationFn: async ({ username, password }: { username: string; password: string }) =>
      (await api.POST("/auth/login", { body: { username, password } })).data!.access_token,
    onSuccess: (token) => setToken(token),
  });
}

/** Register a new user (open self-registration); `language` seeds their preference. */
export function useRegister() {
  const api = useApi();
  return useMutation({
    mutationFn: async (body: { username: string; password: string; language: Lang }) => {
      await api.POST("/auth/register", { body });
    },
  });
}
