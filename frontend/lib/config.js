// Central place for environment-driven config.

// The demo is run with the FastAPI service on port 8000. Deployments can
// override this in frontend/.env.local or through their hosting environment.
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Real OIDC Authorization Code + PKCE sign-in (lib/auth/oidc.js), additive
// to the existing username-only demo login -- see that module's header for
// why both exist side by side. Matches backend/keycloak/README.md's local
// dev realm (`prism`) and the public `prism-frontend` client
// (backend/keycloak/prism-realm-export.json) by default; override every
// value together for a non-local Keycloak, never just the issuer alone --
// a mismatched client id or redirect URI fails at Keycloak's authorization
// endpoint, not silently.
export const OIDC_ISSUER =
  process.env.NEXT_PUBLIC_OIDC_ISSUER || 'http://localhost:8180/realms/prism';
export const OIDC_CLIENT_ID =
  process.env.NEXT_PUBLIC_OIDC_CLIENT_ID || 'prism-frontend';
export const OIDC_REDIRECT_URI =
  process.env.NEXT_PUBLIC_OIDC_REDIRECT_URI ||
  (typeof window !== 'undefined' ? `${window.location.origin}/auth/callback` : '');
