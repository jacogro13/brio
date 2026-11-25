import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

test.beforeEach(async ({ page, request }) => {
  await registerAndLogin(page, request);
});

// Core interactions added in Phase 1: rename, edit (truncate + re-stream),
// retry (regenerate). Uses the mock LLM (replies "…mock response…").

test('rename a conversation from the sidebar', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();
  await page.getByPlaceholder(/Type a message/).fill('Rename me');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  const item = page.getByRole('button', { name: 'Rename me', exact: true });
  await expect(item).toBeVisible();
  const row = item.locator('..');
  await row.locator('button[title="Rename"]').click();

  // The rename field is the only <input> (composer is a <textarea>); exclude the
  // composer's hidden file input, which a bare locator('input') now also matches.
  const input = page.locator('input:not([type="file"])');
  await input.fill('Renamed!');
  await input.press('Enter');

  await expect(page.getByRole('button', { name: 'Renamed!', exact: true })).toBeVisible();
});

test('edit a user message truncates and re-streams', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();
  await page.getByPlaceholder(/Type a message/).fill('First message');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  const userBubble = page.locator('.bubble-user', { hasText: 'First message' });
  await userBubble.hover();
  await page.getByRole('button', { name: 'Edit', exact: true }).click();

  const editArea = page.locator('.bubble-user textarea');
  await editArea.fill('Edited message');
  await page.getByRole('button', { name: 'Save & submit' }).click();

  await expect(page.locator('.bubble-user', { hasText: 'Edited message' })).toBeVisible();
  await expect(page.locator('.bubble-user', { hasText: 'First message' })).toHaveCount(0);
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });
});

test('retry regenerates the last assistant message', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();
  await page.getByPlaceholder(/Type a message/).fill('Retry me');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  const assistantBubble = page.locator('.bubble-assistant').last();
  await assistantBubble.hover();
  await page.getByRole('button', { name: 'Retry', exact: true }).click();

  // Still exactly one assistant reply after regeneration (old one replaced).
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });
  await expect(page.locator('.bubble-assistant')).toHaveCount(1);
});
