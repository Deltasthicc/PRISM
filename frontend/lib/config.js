// Central place for environment-driven config.

// Defaults to the team's shared backend (see /deploy/README.md) so a fresh
// clone points at the same database/auth everyone else is using without any
// extra setup. Override in your own frontend/.env.local (not committed) --
// NEXT_PUBLIC_API_URL=http://localhost:8000 -- to point at a backend running
// on your own laptop instead.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'https://prism-backend-2voe.onrender.com';

export const DOMAIN = 'Data Structures & Algorithms';

export const DUNGEON_ID = 'dsa-dungeon-01';
