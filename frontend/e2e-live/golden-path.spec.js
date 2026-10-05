import fs from 'node:fs';
import { expect, test } from '@playwright/test';

// Journeys across the three roles against a real backend and the real
// frontend (see playwright.live.config.js). Setup that is not under test is
// done through the API; each journey is then driven through the UI.
const API = `http://localhost:${process.env.LIVE_API_PORT || 8000}`;
const stamp = Date.now().toString(36);
const names = { trainer: `trainer_${stamp}`, learner: `learner_${stamp}`, admin: `admin_${stamp}` };
const ids = {};

async function api(request, path, { method = 'GET', data } = {}) {
  const response = await request.fetch(`${API}${path}`, { method, data });
  const body = await response.json().catch(() => ({}));
  if (!response.ok()) throw new Error(`${method} ${path} -> ${response.status()} ${JSON.stringify(body).slice(0, 200)}`);
  return body;
}

async function signIn(browser, username) {
  const context = await browser.newContext({ acceptDownloads: true, baseURL: `http://localhost:${process.env.LIVE_WEB_PORT || 3000}` });
  await context.addInitScript(() => localStorage.setItem('prism_onboarding_seen', '1'));
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  await page.goto('/login');
  await page.locator('input').first().fill(username);
  await page.getByRole('button', { name: /^sign in$/i }).click();
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
  return { context, page, errors };
}

test.describe.serial('trainee, trainer and admin journeys on the live stack', () => {
  const actors = {};

  test.beforeAll(async ({ browser, playwright }) => {
    const request = await playwright.request.newContext();
    for (const [role, username] of Object.entries(names)) {
      const created = await api(request, '/game/player/create', { method: 'POST', data: { username } });
      ids[role] = created.player_id ?? created.player?.player_id;
    }
    const curricula = (await api(request, '/learning/curricula')).curricula;
    const withCompetencies = curricula.find((c) => c.competencies?.length);
    ids.competency = withCompetencies.competencies[0].id;
    ids.competencyLabel = withCompetencies.competencies[0].label;

    const cohort = await api(request, '/learning/cohorts', { method: 'POST', data: { name: `Batch ${stamp}`, trainer_id: ids.trainer } });
    await api(request, `/learning/cohorts/${cohort.cohort_id}/members?player_id=${ids.learner}`, { method: 'POST' });
    const questionnaire = await api(request, '/learning/questionnaires', {
      method: 'POST',
      data: {
        trainer_id: ids.trainer,
        title: `Quiz ${stamp}`,
        description: 'two questions',
        audience_type: 'cohort',
        audience_id: cohort.cohort_id,
        due_at: new Date(Date.now() + 2 * 86400000).toISOString(),
        questions: [
          { prompt: 'Capital of India?', options: ['Mumbai', 'New Delhi', 'Pune'], correct_index: 1 },
          { prompt: '2 + 2?', options: ['3', '4'], correct_index: 1 },
        ],
      },
    });
    ids.questionnaire = questionnaire.questionnaire_id;
    await api(request, `/learning/questionnaires/${ids.questionnaire}/publish`, { method: 'POST', data: { trainer_id: ids.trainer } });
    await api(request, '/learning/announcements', {
      method: 'POST',
      data: { title: `Notice ${stamp}`, body: `Announcement body ${stamp}`, kind: 'announcement', audience: 'all', publish: true },
    });

    actors.learner = await signIn(browser, names.learner);
    actors.trainer = await signIn(browser, names.trainer);
    actors.admin = await signIn(browser, names.admin);
  });

  test.afterAll(async () => {
    for (const actor of Object.values(actors)) await actor.context?.close();
  });

  test('the home feed shows the published announcement and the work-areas bar is present', async () => {
    const { page } = actors.learner;
    await page.goto('/');
    await expect(page.getByText(`Notice ${stamp}`)).toBeVisible();
    await expect(page.getByText(`Announcement body ${stamp}`)).toBeVisible();
    await expect(page.getByRole('navigation', { name: 'Work areas' })).toBeVisible();
  });

  test('a trainee finds a questionnaire, answers it once and sees the score', async () => {
    const { page } = actors.learner;
    await page.goto('/questionnaires');
    await page.getByRole('link', { name: `Start questionnaire for Quiz ${stamp}` }).click();
    await page.getByLabel('New Delhi').check();
    await page.getByLabel('4', { exact: true }).check();
    await page.getByRole('button', { name: /submit/i }).click();
    await expect(page.getByText(/2\s*(\/|of|out of)\s*2/i).first()).toBeVisible();
  });

  test('a trainee saves structured profile entries and they survive a reload', async () => {
    const { page } = actors.learner;
    await page.goto('/academy');
    await page.getByRole('button', { name: 'Add qualification' }).click();
    await page.getByLabel('Degree or diploma for qualification 1').fill('M.Sc. Meteorology');
    await page.getByLabel('Skills (comma separated)').pressSequentially('Python, GIS, ');
    await page.getByRole('button', { name: /create profile|update profile/i }).click();
    await expect(page.getByRole('button', { name: /update profile/i })).toBeVisible();
    await page.reload();
    await expect(page.getByLabel('Degree or diploma for qualification 1')).toHaveValue('M.Sc. Meteorology');
    await expect(page.getByLabel('Skills (comma separated)')).toHaveValue(/^Python, GIS/);
  });

  test('a trainer uploads and publishes a file; the trainee downloads identical bytes', async () => {
    const { page } = actors.trainer;
    await page.goto('/trainer/library');
    await page.getByLabel('Title').first().fill(`Notes ${stamp}`);
    await page.locator('#library-file').setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('hello from the live stack\n') });
    await page.getByRole('button', { name: /upload/i }).click();
    await expect(page.getByText(`Notes ${stamp}`).first()).toBeVisible();
    await page.getByRole('button', { name: /^publish/i }).first().click();
    await expect(page.getByText(/^published$/i).first()).toBeVisible();

    const learner = actors.learner.page;
    await learner.goto('/library');
    const [download] = await Promise.all([
      learner.waitForEvent('download'),
      learner.getByRole('button', { name: `Download Notes ${stamp}` }).click(),
    ]);
    expect(fs.readFileSync(await download.path(), 'utf8')).toBe('hello from the live stack\n');
  });

  test('a trainer declares expertise and an admin sees them ranked with an evidence label', async () => {
    const trainer = actors.trainer.page;
    await trainer.goto('/trainer/expertise');
    await trainer.locator('#expertise-competency').selectOption(ids.competency);
    await trainer.getByRole('button', { name: /save|add|update/i }).first().click();
    await expect(
      trainer.locator('section[aria-labelledby="declared-heading"]').getByText(ids.competencyLabel).first()
    ).toBeVisible();

    const admin = actors.admin.page;
    await admin.goto('/admin/trainer-matching');
    await admin.locator('#match-competency').selectOption(ids.competency);
    await expect(admin.getByText(names.trainer).first()).toBeVisible();
    await expect(admin.getByText(/declared/i).first()).toBeVisible();
  });

  test('a trainer sees the trainee as having submitted', async () => {
    const { page } = actors.trainer;
    await page.goto('/trainer/questionnaires');
    await page.getByRole('button', { name: /results/i }).first().click();
    await expect(page.getByText(names.learner).first()).toBeVisible();
  });

  test('the admin dashboard, announcements and approvals pages load without errors', async () => {
    const { page } = actors.admin;
    await page.goto('/admin');
    await expect(page.getByText(/Certificates issued/)).toBeVisible();
    await expect(page.getByText(/Registrations awaiting approval/)).toBeVisible();
    await page.goto('/admin/announcements');
    await expect(page.getByText(`Notice ${stamp}`).first()).toBeVisible();
    await page.goto('/admin/approvals');
    await expect(page.getByText('No registrations are waiting for a decision.')).toBeVisible();
  });

  test('no page raised an uncaught error during the whole session', async () => {
    for (const [role, actor] of Object.entries(actors)) {
      expect(actor.errors, `${role} page errors`).toEqual([]);
    }
  });
});
