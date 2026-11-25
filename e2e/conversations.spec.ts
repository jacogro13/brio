import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

test.beforeEach(async ({ page, request }) => {
  await registerAndLogin(page, request);
});

test('create a conversation, send a message, delete it', async ({ page }) => {
  await page.goto('/');

  // Homepage starts on a draft chat: composer + greeting, no row yet.
  await expect(page.getByPlaceholder(/Type a message/)).toBeVisible();
  await expect(page.getByText(/how can I help/i)).toBeVisible();

  // "+ New chat" stays a draft — still no conversation row until we send.
  await page.getByRole('button', { name: '+ New chat' }).click();
  await expect(page.locator('button[title="Delete"]')).toHaveCount(0);

  // Send a message — this promotes the draft to a real conversation.
  await page.getByPlaceholder(/Type a message/).fill('Hello!');
  await page.getByRole('button', { name: 'Send' }).click();

  // Wait for user message to appear in thread. Scope to the bubble — once the
  // reply lands, "Hello!" also shows as the sidebar item and the top-bar title.
  await expect(page.locator('.bubble-user', { hasText: 'Hello!' })).toBeVisible();

  // Wait for assistant reply (mock LLM responds quickly)
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  // Title in sidebar should update from first message
  await expect(page.getByRole('button', { name: 'Hello!' })).toBeVisible();

  // Delete the conversation
  await page.locator('button[title="Delete"]').first().click();

  // Deleting the active conversation lands back on a fresh draft (greeting +
  // composer), and its row is gone.
  await expect(page.getByText(/how can I help/i)).toBeVisible();
  await expect(page.getByPlaceholder(/Type a message/)).toBeVisible();
  await expect(page.locator('button[title="Delete"]')).toHaveCount(0);
});

test('conversation persists across reload', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();
  await page.getByPlaceholder(/Type a message/).fill('Persist me');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  await page.reload();

  // Conversation should appear in sidebar
  await expect(page.getByText('Persist me')).toBeVisible();
});
