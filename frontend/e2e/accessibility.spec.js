import { expect, test } from '@playwright/test';
import { PLAYER, stubBackend } from './support';

async function openApp(page, { authenticated = false, onboardingSeen = true, language } = {}) {
  await page.addInitScript(
    ({ authenticated, onboardingSeen, language, player }) => {
      if (authenticated) {
        localStorage.setItem('prism-auth', JSON.stringify({ state: { player, isAuthenticated: true, roles: [] }, version: 0 }));
      }
      if (onboardingSeen) localStorage.setItem('prism_onboarding_seen', '1');
      if (language) localStorage.setItem('prism-language', language);
    },
    { authenticated, onboardingSeen, language, player: PLAYER }
  );
  await stubBackend(page);
}

test('the skip link is the first tab stop and moves focus to the main content', async ({ page }) => {
  await openApp(page);
  // /login autofocuses its form, so use a page that does not.
  await page.goto('/auth/callback');

  await page.keyboard.press('Tab');
  const skip = page.locator('a.skip-link');
  await expect(skip).toBeFocused();
  expect((await skip.boundingBox()).y).toBeGreaterThanOrEqual(0);

  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(/#main-content$/);
  await expect(page.locator('main#main-content')).toBeFocused();
});

test('the document language and direction follow the selected language', async ({ page }) => {
  await openApp(page, { language: 'ur' });
  await page.goto('/login');
  await expect(page.locator('html')).toHaveAttribute('lang', 'ur');
  await expect(page.locator('html')).toHaveAttribute('dir', 'rtl');
  await expect(page.locator('a.skip-link')).toHaveText('مرکزی مواد پر جائیں');
});

test('English stays left-to-right', async ({ page }) => {
  await openApp(page);
  await page.goto('/login');
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  await expect(page.locator('html')).toHaveAttribute('dir', 'ltr');
});

test.describe('onboarding tour', () => {
  test('is a labelled modal that traps focus and closes on Escape', async ({ page }) => {
    await openApp(page, { authenticated: true, onboardingSeen: false });
    await page.goto('/stats');

    const dialog = page.getByRole('dialog');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute('aria-modal', 'true');
    const labelledBy = await dialog.getAttribute('aria-labelledby');
    await expect(page.locator(`#${labelledBy}`)).toBeVisible();

    const focusIsInside = () => page.evaluate(() => Boolean(document.activeElement?.closest('[role="dialog"]')));
    expect(await focusIsInside()).toBe(true);
    for (let i = 0; i < 6; i += 1) {
      await page.keyboard.press('Tab');
      expect(await focusIsInside()).toBe(true);
    }
    await page.keyboard.press('Shift+Tab');
    expect(await focusIsInside()).toBe(true);

    await page.keyboard.press('Escape');
    await expect(dialog).toHaveCount(0);
    expect(await page.evaluate(() => localStorage.getItem('prism_onboarding_seen'))).toBe('1');
  });
});
