import { expect, test } from '@playwright/test';
import { seedSession, stubBackend } from './support';

async function open(page, roles, path = '/') {
  await seedSession(page, { roles });
  await stubBackend(page, (apiPath) =>
    apiPath === '/learning/home/feed'
      ? { json: { announcements: [], new_courses: [], my_achievements: [], generated_at: '2026-10-05T00:00:00Z' } }
      : undefined
  );
  await page.goto(path);
  await expect(page.getByRole('navigation', { name: 'Work areas' })).toBeVisible();
}

const groups = (page) => page.getByRole('navigation', { name: 'Work areas' }).getByRole('group');

test('a trainee sees only the learning area', async ({ page }) => {
  await open(page, ['learner']);
  await expect(groups(page)).toHaveCount(1);
  await expect(page.getByRole('group', { name: 'Learning' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Certificates' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Approvals' })).toHaveCount(0);
});

test('a trainer sees only the teaching area', async ({ page }) => {
  await open(page, ['trainer']);
  await expect(groups(page)).toHaveCount(1);
  await expect(page.getByRole('link', { name: 'Content library' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Certificates' })).toHaveCount(0);
});

test('an organization admin sees the administration area', async ({ page }) => {
  await open(page, ['organization_admin']);
  await expect(groups(page)).toHaveCount(1);
  await expect(page.getByRole('link', { name: 'Trainer matching' })).toBeVisible();
});

test('with no roles (demo) every area is offered', async ({ page }) => {
  await open(page, []);
  await expect(groups(page)).toHaveCount(3);
});

test('the current page is marked in the work-areas bar', async ({ page }) => {
  await seedSession(page, { roles: ['organization_admin'] });
  await stubBackend(page, (apiPath) => (apiPath === '/auth/pending-registrations' ? { json: [] } : undefined));
  await page.goto('/admin/approvals');
  await expect(page.getByRole('link', { name: 'Approvals' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByRole('link', { name: 'Dashboard' })).not.toHaveAttribute('aria-current', 'page');
});

test('the home page shows the feed, including honest empty sections', async ({ page }) => {
  await seedSession(page, { roles: ['learner'] });
  await stubBackend(page, (apiPath) =>
    apiPath === '/learning/home/feed'
      ? {
          json: {
            announcements: [
              { announcement_id: 'a-1', kind: 'announcement', title: 'Monsoon workshop', body: 'Registration opens Monday.', published_at: '2026-10-01T09:00:00Z' },
            ],
            new_courses: [],
            my_achievements: [],
            generated_at: '2026-10-05T00:00:00Z',
          },
        }
      : undefined
  );
  await page.goto('/');
  await expect(page.getByText('Monsoon workshop')).toBeVisible();
  await expect(page.getByText('Registration opens Monday.')).toBeVisible();
  await expect(page.getByText('No new courses in the last 30 days.')).toBeVisible();
  await expect(page.getByText('No certificates earned in the last 90 days.')).toBeVisible();
});

test('a failed feed offers a retry instead of a blank page', async ({ page }) => {
  await seedSession(page, { roles: ['learner'] });
  let calls = 0;
  await stubBackend(page, (apiPath) => {
    if (apiPath !== '/learning/home/feed') return undefined;
    calls += 1;
    return calls <= 2
      ? { status: 500, json: { detail: 'boom' } }
      : { json: { announcements: [], new_courses: [], my_achievements: [], generated_at: 'x' } };
  });
  await page.goto('/');
  await expect(page.locator('main').getByRole('alert')).toBeVisible();
  await page.getByRole('button', { name: /retry/i }).click();
  await expect(page.getByText('No current announcements.')).toBeVisible();
});
