import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

test.beforeEach(async ({ page, request }) => {
  await registerAndLogin(page, request);
});

// The mock LLM emits deterministic reasoning before its answer, but only when
// thinking is on. Thinking is a per-message composer toggle (🧠, "Toggle
// thinking"), like web access. This drives the toggle on, then asserts the
// collapsible "Thoughts" panel appears. Black-box: drives the UI only, no
// frontend/backend imports.

test('enabling thinking shows a collapsible thinking panel', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();

  // Turn thinking on via the composer toggle, then send.
  await page.getByRole('button', { name: 'Toggle thinking' }).click();
  await page.getByPlaceholder(/Type a message/).fill('Explain something');
  await page.getByRole('button', { name: 'Send' }).click();

  // Collapsed by default once the answer has arrived; reasoning hidden.
  const toggle = page.getByRole('button', { name: /Thoughts/ });
  await expect(toggle).toBeVisible();
  await expect(page.getByText(/Let me think about this/i)).toHaveCount(0);

  // Expanding reveals the persisted reasoning.
  await toggle.click();
  await expect(page.getByText(/Let me think about this/i)).toBeVisible();

  // Reasoning survives a reload (persisted, not just streamed).
  await page.reload();
  await page.getByRole('button', { name: 'Explain something', exact: true }).click();
  await expect(page.getByRole('button', { name: /Thoughts/ })).toBeVisible();
});

test('thinking is off by default (no reasoning panel)', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();
  await page.getByPlaceholder(/Type a message/).fill('Just answer');
  await page.getByRole('button', { name: 'Send' }).click();
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  await expect(page.getByRole('button', { name: /Thoughts/ })).toHaveCount(0);
});
