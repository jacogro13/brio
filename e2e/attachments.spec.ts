import { readFile } from 'node:fs/promises';
import { expect, test } from '@playwright/test';
import { registerAndLogin } from './helpers';

test.beforeEach(async ({ page, request }) => {
  await registerAndLogin(page, request);
});

// The e2e stack runs the mock LLM and a real Garage container (compose sets
// GARAGE_ENDPOINT=http://garage:3900), so this exercises the full upload →
// link → download path black-box.
test('attach a file, send it, and download it back', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: '+ New chat' }).click();
  await expect(page.getByPlaceholder(/Type a message/)).toBeVisible();

  // Attach a markdown file via the hidden file input behind the 📎 button.
  await page.locator('input[type="file"]').setInputFiles({
    name: 'notes.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# Notes\nThe secret code is BANANA42.\n'),
  });

  // A pending chip for the file appears in the composer.
  await expect(page.getByText('notes.md').first()).toBeVisible();

  // Send with the attachment.
  await page.getByPlaceholder(/Type a message/).fill('read my note');
  await page.getByRole('button', { name: 'Send' }).click();

  // User message + assistant reply (mock) land.
  await expect(page.getByText('read my note')).toBeVisible();
  await expect(page.getByText(/mock response/i)).toBeVisible({ timeout: 10000 });

  // The attachment chip renders on the sent message. Since Phase 7 it's a button
  // (the download fetches through the backend with the Bearer header, then saves
  // via a blob URL — a plain <a href> can't carry the token).
  const chip = page.getByRole('button', { name: /notes\.md/ });
  await expect(chip).toBeVisible();

  // Clicking it downloads the original bytes back through the backend.
  const downloadPromise = page.waitForEvent('download');
  await chip.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('notes.md');
  const contents = await readFile(await download.path(), 'utf-8');
  expect(contents).toContain('BANANA42');

  // Persists across reload. The app doesn't auto-open a conversation on load, so
  // re-select it from the sidebar (its title is the first user message).
  await page.reload();
  await page.getByRole('button', { name: 'read my note', exact: true }).click();
  await expect(page.getByRole('button', { name: /notes\.md/ })).toBeVisible();
});

test('uploading a file over the limit shows an error', async ({ page }) => {
  await page.goto('/');

  // The backend's limit is 10 MB.
  await page.locator('input[type="file"]').setInputFiles({
    name: 'big.txt',
    mimeType: 'text/plain',
    buffer: Buffer.alloc(11 * 1024 * 1024, 'a'),
  });

  await expect(page.getByText('The file is too large.')).toBeVisible();
  await expect(page.getByText('big.txt')).toHaveCount(0);
});
