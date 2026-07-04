import { expect, test } from '@playwright/test';

test('login page renders', async ({ page }) => {
  await page.goto('/login');
  await expect(page.getByAltText('Kairos Mesh')).toBeVisible();
  await expect(page.getByRole('button', { name: 'INITIALIZE_SESSION' })).toBeVisible();
});
