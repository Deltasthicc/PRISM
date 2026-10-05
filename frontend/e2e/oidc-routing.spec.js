import { expect, test } from '@playwright/test';
import { PLAYER, arriveFromIdentityProvider, stubBackend } from './support';

const me = (overrides) => ({
  status: 'not_registered',
  player_id: null,
  username: null,
  roles: [],
  requested_role: null,
  ...overrides,
});

async function signInAs(page, meBody, meStatus = 200) {
  await stubBackend(page, (path) => (path === '/auth/me' ? { status: meStatus, json: meBody } : undefined));
  await arriveFromIdentityProvider(page);
}

test('an approved user with a role leaves the auth screens with their identity loaded', async ({ page }) => {
  await signInAs(
    page,
    me({ status: 'approved', player_id: PLAYER.player_id, username: PLAYER.username, roles: ['learner'], requested_role: 'learner' })
  );

  await page.waitForURL((url) => !url.pathname.startsWith('/auth/'));

  const stored = JSON.parse(await page.evaluate(() => localStorage.getItem('prism-auth'))).state;
  expect(stored.isAuthenticated).toBe(true);
  expect(stored.player.player_id).toBe(PLAYER.player_id);
  expect(stored.roles).toEqual(['learner']);
});

test('a new identity is shown the registration form', async ({ page }) => {
  await signInAs(page, me({ status: 'not_registered' }));
  await expect(page.getByRole('heading', { name: 'Complete your registration' })).toBeVisible();
});

test('a pending request shows the waiting screen', async ({ page }) => {
  await signInAs(page, me({ status: 'pending_approval', player_id: 'p-2', requested_role: 'trainer' }));
  await expect(page.getByRole('heading', { name: 'Waiting for admin approval' })).toBeVisible();
});

test('a rejected request says so', async ({ page }) => {
  await signInAs(page, me({ status: 'rejected', player_id: 'p-3', requested_role: 'learner' }));
  await expect(page.getByRole('heading', { name: 'Access request declined' })).toBeVisible();
});

test('an approved account without a role is not signed in and is told why', async ({ page }) => {
  await signInAs(page, me({ status: 'approved', player_id: PLAYER.player_id, requested_role: 'trainer' }));
  await expect(page.getByRole('heading', { name: 'Approved, role not assigned yet' })).toBeVisible();

  const raw = await page.evaluate(() => localStorage.getItem('prism-auth'));
  const stored = raw ? JSON.parse(raw).state : null;
  expect(stored?.isAuthenticated ?? false).toBe(false);
});

test('an unauthenticated /auth/me on the callback shows an error with a way back', async ({ page }) => {
  await signInAs(page, { detail: 'Authentication required' }, 401);
  await expect(page.getByRole('link', { name: 'Back to sign in' })).toBeVisible();
});

test('signing out from the pending screen ends the identity-provider session and returns to /login', async ({ page }) => {
  await signInAs(page, me({ status: 'pending_approval', player_id: 'p-2', requested_role: 'learner' }));
  await expect(page.getByRole('heading', { name: 'Waiting for admin approval' })).toBeVisible();
  expect(await page.evaluate(() => sessionStorage.getItem('prism-oidc-session'))).not.toBeNull();

  await page.getByRole('button', { name: 'Sign out' }).click();

  await page.waitForURL('**/login');
  expect(await page.evaluate(() => sessionStorage.getItem('prism-oidc-session'))).toBeNull();
});

test('submitting the registration form re-checks the real status', async ({ page }) => {
  let registered = false;
  await stubBackend(page, (path, request) => {
    if (path === '/auth/register') {
      registered = true;
      return { json: { binding_id: 'b-1', player_id: 'p-9', requested_role: 'trainer', status: 'pending' } };
    }
    if (path === '/auth/me') {
      return {
        json: registered
          ? me({ status: 'pending_approval', player_id: 'p-9', requested_role: 'trainer' })
          : me({ status: 'not_registered' }),
      };
    }
    return undefined;
  });
  await arriveFromIdentityProvider(page);

  await page.getByLabel('Username').fill('new_trainer');
  await page.getByLabel('Full name').fill('New Trainer');
  await page.getByRole('combobox').selectOption('trainer');
  await page.getByRole('button', { name: 'Request access' }).click();

  await expect(page.getByRole('heading', { name: 'Waiting for admin approval' })).toBeVisible();
});
