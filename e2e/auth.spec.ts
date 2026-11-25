import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

function uniqueUser() {
  return `e2e_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

test('register, logout, and log back in', async ({ page }) => {
  const username = uniqueUser();
  const password = 'pw-e2e-123';
  await page.goto('/');

  // Auth page is shown when there's no token.
  await page.getByRole('button', { name: 'Register', exact: true }).click();
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Create account' }).click();

  // Landed in the chat.
  await expect(page.getByRole('button', { name: '+ New chat' })).toBeVisible();

  // Log out → back to the auth page.
  await page.getByRole('button', { name: 'Logout' }).click();
  await expect(page.getByRole('button', { name: 'Create account' }).or(
    page.getByRole('button', { name: 'Log in' })
  )).toBeVisible();

  // Log back in with the same credentials.
  await page.getByRole('button', { name: 'Login', exact: true }).click();
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', { name: 'Log in' }).click();
  await expect(page.getByRole('button', { name: '+ New chat' })).toBeVisible();
});

test('wrong password shows an error', async ({ page, request }) => {
  const username = uniqueUser();
  await request.post('/api/auth/register', {
    data: { username, password: 'correct-pw' },
  });

  await page.goto('/');
  await page.getByLabel('Username').fill(username);
  await page.getByLabel('Password').fill('wrong-pw');
  await page.getByRole('button', { name: 'Log in' }).click();

  await expect(page.getByText(/invalid username or password/i)).toBeVisible();
  // Still on the auth page, not in the chat.
  await expect(page.getByRole('button', { name: '+ New chat' })).toHaveCount(0);
});

test('wrong password in Italian shows the Italian error', async ({ page, request }) => {
  const username = uniqueUser();
  await request.post('/api/auth/register', {
    data: { username, password: 'correct-pw' },
  });

  await page.goto('/');
  await page.getByRole('button', { name: 'IT', exact: true }).click();
  await page.getByLabel('Nome utente').fill(username);
  await page.getByLabel('Password').fill('wrong-pw');
  // Enter, not a click: the language buttons sit inside the form and must not
  // be its default (submit) button, or Enter would flip the UI back to English.
  await page.getByLabel('Password').press('Enter');

  await expect(page.getByText('Nome utente o password non validi.')).toBeVisible();
  await expect(page.getByText(/invalid username or password/i)).toHaveCount(0);
  // Still on the auth page, not in the chat.
  await expect(page.getByLabel('Nome utente')).toBeVisible();
});

test('rejected token drops back to the auth page', async ({ page }) => {
  // A garbage token, planted once: the reload that follows the 401 must not
  // plant it again (sessionStorage survives the reload, localStorage is cleared).
  await page.addInitScript(() => {
    if (sessionStorage.getItem('seeded')) return;
    sessionStorage.setItem('seeded', '1');
    localStorage.setItem('chatbot_token', 'not-a-valid-token');
  });

  await page.goto('/');

  await expect(page.getByRole('button', { name: 'Log in' })).toBeVisible();
  await expect(page.getByRole('button', { name: '+ New chat' })).toHaveCount(0);
});

test('users cannot see each other\'s conversations', async ({ page, request }) => {
  // User A creates a conversation via the API.
  const { token: tokenA } = await registerAndLogin(page, request);
  const created = await request.post('/api/conversations/', {
    headers: { Authorization: `Bearer ${tokenA}` },
  });
  const convA = await created.json();
  await request.post(`/api/conversations/${convA.id}/messages`, {
    headers: { Authorization: `Bearer ${tokenA}`, 'Content-Type': 'application/json' },
    data: { content: 'secret-from-A', attachment_ids: [], web_access: false },
  });

  // Now register user B in the browser (fresh token injected) and confirm B's
  // sidebar has none of A's conversations.
  await registerAndLogin(page, request);
  await page.goto('/');
  await expect(page.getByRole('button', { name: '+ New chat' })).toBeVisible();
  await expect(page.getByText('secret-from-A')).toHaveCount(0);
});
