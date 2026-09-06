// Central place for environment-driven config.

// The demo is run with the FastAPI service on port 8000. Deployments can
// override this in frontend/.env.local or through their hosting environment.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
