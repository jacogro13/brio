// Chatbot's session wiring, kept outside the canonical client.ts: token storage,
// the username shown in the top bar, and the auth middleware (Bearer header, and
// a rejected token dropping back to the auth page).
import type { Middleware } from "openapi-fetch";

export const TOKEN_KEY = "chatbot_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

/** Decode the `username` claim from the stored JWT (no verification — display
 * only). Returns null if there's no/invalid token. */
export function getUsername(): string | null {
  const token = getToken();
  if (!token) return null;
  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return typeof payload.username === "string" ? payload.username : null;
  } catch {
    return null;
  }
}

/**
 * Adds `Authorization: Bearer …` when there is a token. A 401/403 calls
 * `onRejected` **only if the request carried a token**: a wrong password on
 * `/auth/login` (401, no token) must reach the form as an `ApiError`, not reload.
 * Register it after `throwOnError` (openapi-fetch runs `onResponse`
 * last-registered-first), so it sees the response before the error is thrown.
 */
export function makeAuthMiddleware(onRejected: () => void): Middleware {
  return {
    onRequest({ request }) {
      const token = getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
    onResponse({ request, response }) {
      const rejected = response.status === 401 || response.status === 403;
      if (rejected && request.headers.has("Authorization")) onRejected();
      return undefined;
    },
  };
}
