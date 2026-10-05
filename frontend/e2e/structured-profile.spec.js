import { expect, test } from '@playwright/test';
import { PLAYER, seedSession, stubBackend } from './support';

const SAVED_PROFILE = {
  profile_id: 'prof-1',
  player_id: PLAYER.player_id,
  full_name: 'Asha',
  designation: 'Scientist',
  department: 'IMD',
  job_role: '',
  current_assignment: '',
  educational_qualifications: '',
  years_experience: 5,
  previous_trainings: [],
  career_goal: '',
  preferred_language: 'English',
  experience_level: 'intermediate',
  target_domains: [],
  qualifications: [{ degree: 'M.Sc. Meteorology', institution: 'IITM', year: 2014 }],
  work_experience: [],
  interests: [],
  skills: ['Python'],
  external_certificates: [],
};

async function openAcademy(page, onSave) {
  await seedSession(page);
  await stubBackend(page, (path, request) => {
    if (path === '/learning/curricula') return { json: { curricula: [] } };
    if (path === '/game/dungeons') return { json: [] };
    if (path === '/learning/integrations/status') return { json: { igot: { mode: 'CATALOGUE' }, nssta: { mode: 'CATALOGUE' } } };
    if (path === `/learning/profile/${PLAYER.player_id}`) {
      if (request.method() === 'PUT') {
        const body = request.postDataJSON();
        onSave(body);
        return { json: { profile: { ...SAVED_PROFILE, ...body } } };
      }
      return { json: { profile: SAVED_PROFILE } };
    }
    return undefined;
  });
  await page.goto('/academy');
  await expect(page.getByRole('group', { name: 'Qualifications' })).toBeVisible();
}

test('saved structured entries are shown for editing', async ({ page }) => {
  await openAcademy(page, () => {});
  await expect(page.getByLabel('Degree or diploma for qualification 1')).toHaveValue('M.Sc. Meteorology');
  await expect(page.getByLabel('Skills (comma separated)')).toHaveValue('Python');
});

test('tags can be typed with commas and spaces and are saved as a clean list', async ({ page }) => {
  let saved = null;
  await openAcademy(page, (body) => { saved = body; });

  const skills = page.getByLabel('Skills (comma separated)');
  await skills.fill('');
  await skills.pressSequentially('Python, GIS, ');
  await expect(skills).toHaveValue('Python, GIS, ');

  await page.getByRole('button', { name: /update profile/i }).click();
  await expect.poll(() => saved).not.toBeNull();
  expect(saved.skills).toEqual(['Python', 'GIS']);
});

test('adding and removing a qualification row, and blank rows are not sent', async ({ page }) => {
  let saved = null;
  await openAcademy(page, (body) => { saved = body; });

  await page.getByRole('button', { name: 'Add qualification' }).click();
  await expect(page.getByLabel('Degree or diploma for qualification 2')).toBeVisible();
  await page.getByLabel('Degree or diploma for qualification 2').fill('B.Sc. Physics');
  await page.getByLabel('Year for qualification 2').fill('2011');
  await page.getByRole('button', { name: 'Add qualification' }).click(); // left blank on purpose

  await page.getByRole('button', { name: /update profile/i }).click();
  await expect.poll(() => saved).not.toBeNull();
  expect(saved.qualifications).toEqual([
    { degree: 'M.Sc. Meteorology', institution: 'IITM', year: 2014 },
    { degree: 'B.Sc. Physics', institution: '', year: 2011 },
  ]);

  await page.getByRole('button', { name: 'Remove qualification 1' }).click();
  await expect(page.getByLabel('Degree or diploma for qualification 1')).toHaveValue('B.Sc. Physics');
});

test('an end year before the start year is explained and nothing is sent', async ({ page }) => {
  let saved = null;
  await openAcademy(page, (body) => { saved = body; });

  await page.getByRole('button', { name: 'Add role' }).click();
  await page.getByLabel('Title for role 1').fill('Forecaster');
  await page.getByLabel('Start year for role 1').fill('2020');
  await page.getByLabel('End year for role 1').fill('2010');
  await page.getByRole('button', { name: /update profile/i }).click();

  await expect(page.locator('main').getByRole('alert')).toContainText('end year is before the start year');
  expect(saved).toBeNull();
});
