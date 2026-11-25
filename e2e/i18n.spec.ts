import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

test.beforeEach(async ({ page, request }) => {
  await registerAndLogin(page, request);
});

test('switching language translates the UI and persists to the server', async ({
  page,
}) => {
  await page.goto('/');

  // Fresh users default to English.
  await expect(page.getByText(/how can I help/i)).toBeVisible();
  await expect(page.getByPlaceholder(/Type a message/)).toBeVisible();

  // Switch to Italian via the EN · IT · DE selector.
  await page.getByRole('button', { name: 'IT', exact: true }).click();

  await expect(page.getByText(/Come posso aiutarti/i)).toBeVisible();
  await expect(page.getByPlaceholder(/Scrivi un messaggio/)).toBeVisible();
  await expect(page.getByText(/how can I help/i)).toHaveCount(0);

  // Drop the local cache so the reloaded page must learn the language from the
  // server profile (GET /auth/me), proving the PATCH persisted it.
  await page.evaluate(() => localStorage.removeItem('chatbot_lang'));
  await page.reload();

  await expect(page.getByText(/Come posso aiutarti/i)).toBeVisible();
  await expect(page.getByPlaceholder(/Scrivi un messaggio/)).toBeVisible();
});

test('a failed upload shows its error in Italian', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'IT', exact: true }).click();
  await expect(page.getByPlaceholder(/Scrivi un messaggio/)).toBeVisible();

  // Over the backend's 10 MB limit.
  await page.locator('input[type="file"]').setInputFiles({
    name: 'grande.txt',
    mimeType: 'text/plain',
    buffer: Buffer.alloc(11 * 1024 * 1024, 'a'),
  });

  await expect(page.getByText('Il file è troppo grande.')).toBeVisible();
});
