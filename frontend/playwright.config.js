import { defineConfig, devices } from '@playwright/test';

const PORT = Number(process.env.E2E_PORT || 3500);

// Browser tests run against the production build (`npm run build` first) with
// every backend and identity-provider call stubbed inside each spec, so they
// need no database, Keycloak or API process. They prove frontend behaviour;
// they are not a substitute for a live-stack round trip (see
// docs/contracts/release-gates.md).
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: `npx next start -p ${PORT}`,
    url: `http://localhost:${PORT}/login`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
