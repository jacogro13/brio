import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

test.beforeEach(async ({ page, request }) => {
  await registerAndLogin(page, request);
});

// Phase 6: with the 🌐 web-access toggle on and the mock LLM's `[use web]` hook,
// the backend runs the prompted-JSON tool loop against the mock search adapter,
// streams tool-activity chips, and answers using the (mock) result. Black-box:
// drives the UI only, no frontend/backend imports.

test('web access runs a search and shows an activity chip', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();

  // Turn web access on, then send a message that trips the mock `[use web]` hook.
  await page.getByRole('button', { name: 'Toggle web access' }).click();
  await page.getByPlaceholder(/Type a message/).fill('weather today [use web]');
  await page.getByRole('button', { name: 'Send' }).click();

  // The tool-activity chip for the search appears (mock query is "example").
  await expect(page.getByText(/Searching:\s*example/i)).toBeVisible({ timeout: 10000 });

  // The final answer is produced after the tool result.
  await expect(page.getByText(/Based on the search results/i)).toBeVisible({
    timeout: 10000,
  });

  // Activity survives a reload (persisted on tool_events, not just streamed).
  await page.reload();
  await page.getByRole('button', { name: /weather today/, exact: false }).first().click();
  await expect(page.getByText(/Searching:\s*example/i)).toBeVisible();
});
