import { expect, test } from '@playwright/test';
import { seedSession, stubBackend } from './support';

const PENDING = {
  binding_id: 'b-1',
  player_id: 'p-7',
  requested_role: 'trainer',
  registration_notes: 'Runs the monsoon forecasting workshop',
  created_at: '2026-10-01T09:30:00Z',
  username: 'asha_k',
  full_name: 'Asha Kulkarni',
  designation: 'Senior Scientist',
  department: 'IMD Pune',
  issuer: 'https://idp.test/realms/prism',
  subject_id: 'subject-abc-123',
};

test('shows what the applicant declared and where to grant the role', async ({ page }) => {
  await seedSession(page);
  await stubBackend(page, (path) => (path === '/auth/pending-registrations' ? { json: [PENDING] } : undefined));
  await page.goto('/admin/approvals');

  await expect(page.getByRole('heading', { name: 'Asha Kulkarni' })).toBeVisible();
  await expect(page.getByText('Senior Scientist')).toBeVisible();
  await expect(page.getByText('IMD Pune')).toBeVisible();
  await expect(page.getByText('Runs the monsoon forecasting workshop')).toBeVisible();
  await expect(page.getByText('subject-abc-123')).toBeVisible();
  await expect(page.getByText('Wants to join as Trainer')).toBeVisible();
  await expect(page.getByText(/must also be granted to the same identity-provider account/)).toBeVisible();
});

test('approving sends the decision and note, then the list refreshes', async ({ page }) => {
  await seedSession(page);
  let decided = null;
  await stubBackend(page, (path, request) => {
    if (path === '/auth/pending-registrations') return { json: decided ? [] : [PENDING] };
    if (path === '/auth/pending-registrations/b-1/decide') {
      decided = request.postDataJSON();
      return { json: { binding_id: 'b-1', requested_role: 'trainer', decision: 'approved', active: true } };
    }
    return undefined;
  });
  await page.goto('/admin/approvals');

  await page.getByLabel('Decision note (optional)').fill('Confirmed with her manager');
  await page.getByRole('button', { name: 'Approve Asha Kulkarni' }).click();

  await expect(page.getByText('No registrations are waiting for a decision.')).toBeVisible();
  await expect(page.getByText('Approved Asha Kulkarni.')).toBeVisible();
  expect(decided).toEqual({ decision: 'approved', notes: 'Confirmed with her manager' });
});

test('rejecting records a rejection', async ({ page }) => {
  await seedSession(page);
  let decided = null;
  await stubBackend(page, (path, request) => {
    if (path === '/auth/pending-registrations') return { json: decided ? [] : [PENDING] };
    if (path === '/auth/pending-registrations/b-1/decide') {
      decided = request.postDataJSON();
      return { json: { binding_id: 'b-1', requested_role: 'trainer', decision: 'rejected', active: false } };
    }
    return undefined;
  });
  await page.goto('/admin/approvals');
  await page.getByRole('button', { name: 'Reject Asha Kulkarni' }).click();
  await expect(page.getByText('Rejected Asha Kulkarni.')).toBeVisible();
  expect(decided.decision).toBe('rejected');
});

test('a non-admin is told they are not allowed rather than seeing an empty list', async ({ page }) => {
  await seedSession(page);
  await stubBackend(page, (path) =>
    path === '/auth/pending-registrations' ? { status: 403, json: { detail: 'Forbidden' } } : undefined
  );
  await page.goto('/admin/approvals');
  await expect(page.locator('main').getByRole('alert')).toContainText('organization administrator role');
});

test('a failed load offers a retry that recovers', async ({ page }) => {
  await seedSession(page);
  let calls = 0;
  await stubBackend(page, (path) => {
    if (path !== '/auth/pending-registrations') return undefined;
    calls += 1;
    return calls === 1 ? { status: 500, json: { detail: 'boom' } } : { json: [PENDING] };
  });
  await page.goto('/admin/approvals');
  await expect(page.locator('main').getByRole('alert')).toBeVisible();
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.getByRole('heading', { name: 'Asha Kulkarni' })).toBeVisible();
});

test('a stale decision (already decided elsewhere) is explained', async ({ page }) => {
  await seedSession(page);
  await stubBackend(page, (path) => {
    if (path === '/auth/pending-registrations') return { json: [PENDING] };
    if (path === '/auth/pending-registrations/b-1/decide') return { status: 404, json: { detail: 'not found' } };
    return undefined;
  });
  await page.goto('/admin/approvals');
  await page.getByRole('button', { name: 'Approve Asha Kulkarni' }).click();
  await expect(page.locator('main').getByRole('alert')).toContainText('already decided');
});
