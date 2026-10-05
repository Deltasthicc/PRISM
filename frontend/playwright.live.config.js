import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { defineConfig, devices } from '@playwright/test';

// Live-stack journey: a real FastAPI backend (SQLite, authentication bypassed
// as in the hosted demo) plus the production frontend build. Nothing is
// stubbed. Run manually or before a demo:
//
//   npm run build && PRISM_PYTHON=<path to backend venv python> npm run test:live
//
// It proves the pages and the API agree with each other. It does not exercise
// real sign-in (Keycloak) or PostgreSQL.
const WEB_PORT = Number(process.env.LIVE_WEB_PORT || 3000); // the backend's CORS allows :3000
const API_PORT = Number(process.env.LIVE_API_PORT || 8000); // the frontend build targets :8000
const workDir = path.join(os.tmpdir(), `prism-live-${process.pid}`);
fs.mkdirSync(workDir, { recursive: true });

export default defineConfig({
  testDir: './e2e-live',
  workers: 1,
  fullyParallel: false,
  retries: 0,
  reporter: 'list',
  use: { baseURL: `http://localhost:${WEB_PORT}`, acceptDownloads: true },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${process.env.PRISM_PYTHON || 'python'} -m uvicorn main:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://localhost:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: {
        DISABLE_AUTH: 'true',
        DATABASE_URL: `sqlite:///${path.join(workDir, 'live.db').split(path.sep).join('/')}`,
        CONTENT_LIBRARY_DIR: path.join(workDir, 'library'),
      },
    },
    {
      command: `npx next start -p ${WEB_PORT}`,
      url: `http://localhost:${WEB_PORT}/login`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
