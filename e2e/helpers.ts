import type { APIRequestContext, Page } from '@playwright/test';

const TOKEN_KEY = 'chatbot_token';

/**
 * Register a fresh user via the API and inject their JWT into localStorage
 * before any page script runs, so `page.goto('/')` lands straight in the chat
 * (not the auth page). Returns the created username. Each call uses a unique
 * username so specs are isolated from one another.
 */
export async function registerAndLogin(
  page: Page,
  request: APIRequestContext
): Promise<{ username: string; token: string }> {
  const username = `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const password = 'pw-e2e-123';

  const reg = await request.post('/api/auth/register', {
    data: { username, password },
  });
  if (!reg.ok()) {
    throw new Error(`register failed: ${reg.status()} ${await reg.text()}`);
  }
  const res = await request.post('/api/auth/login', {
    data: { username, password },
  });
  if (!res.ok()) {
    // e.g. a 429 from the login rate limit — fail loudly here rather than
    // injecting an undefined token (which sends the auth middleware into a 401→reload loop).
    throw new Error(`login failed: ${res.status()} ${await res.text()}`);
  }
  const { access_token } = await res.json();

  // Runs before app scripts on every navigation in this page (survives reload).
  await page.addInitScript(
    ([key, token]) => {
      localStorage.setItem(key, token);
    },
    [TOKEN_KEY, access_token] as const
  );

  return { username, token: access_token };
}
