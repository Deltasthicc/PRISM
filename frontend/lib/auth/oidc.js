// Real OIDC Authorization Code + PKCE browser sign-in, additive to the
// existing username-only demo login in lib/api/client.js's `auth` module.
//
// Why both exist side by side: the deployed demo runs backend
// DISABLE_AUTH=true, where the username-only flow is correct and
// sufficient (see that module's own header comment -- there is no real
// identity to attach a token to in that mode). This module is for the
// other case: a deployment with DISABLE_AUTH unset, running real OIDC/RBAC
// (backend/security/identity.py, security/rbac.py) end to end, which
// until now had no browser-reachable login at all -- confirmed by grep,
// nothing in this frontend ever attached an Authorization header (see
// backend/keycloak/README.md's own note that a real browser flow was
// "Lane 1/Lane 5's concern... not this module's", left unbuilt).
//
// lib/api/client.js's `request()` calls `getValidAccessToken()` on every
// call and attaches `Authorization: Bearer <token>` only when one exists;
// when it's null (no OIDC session, or DISABLE_AUTH deployments where no
// one ever calls `beginLogin()`), every existing request behaves exactly
// as it did before this file existed.

import { OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_REDIRECT_URI } from '../config';
import { generateCodeVerifier, generateCodeChallenge, generateState } from './pkce';

const SESSION_KEY = 'prism-oidc-session';
const PENDING_KEY = 'prism-oidc-pending';

// Refresh this far before actual expiry so a request never races a token
// that's valid when checked but expired by the time it reaches the
// backend (network latency, clock drift between browser and Keycloak).
const REFRESH_SKEW_SECONDS = 30;

function readSession() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.sessionStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeSession(session) {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  } catch {
    // Private-browsing/storage-blocked: the session simply won't persist
    // across a reload. Never let a storage failure throw out of a login.
  }
}

export function clearOidcSession() {
  if (typeof window === 'undefined') return;
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // See writeSession.
  }
}

async function discoverEndpoints() {
  const response = await fetch(`${OIDC_ISSUER}/.well-known/openid-configuration`);
  if (!response.ok) {
    throw new Error('Could not reach the identity provider’s discovery document.');
  }
  const doc = await response.json();
  return {
    authorizationEndpoint: doc.authorization_endpoint,
    tokenEndpoint: doc.token_endpoint,
    endSessionEndpoint: doc.end_session_endpoint,
  };
}

// Redirects the browser to Keycloak. Nothing returns from this call in the
// normal case -- the page navigates away.
export async function beginLogin({ returnTo } = {}) {
  const { authorizationEndpoint } = await discoverEndpoints();
  const verifier = generateCodeVerifier();
  const challenge = await generateCodeChallenge(verifier);
  const state = generateState();

  if (typeof window !== 'undefined') {
    try {
      window.sessionStorage.setItem(
        PENDING_KEY,
        JSON.stringify({ verifier, state, returnTo: returnTo || '/' })
      );
    } catch {
      // If storage is unavailable, the callback's state check will fail
      // closed below rather than silently trusting an unverifiable code.
    }
  }

  const params = new URLSearchParams({
    client_id: OIDC_CLIENT_ID,
    redirect_uri: OIDC_REDIRECT_URI,
    response_type: 'code',
    scope: 'openid',
    state,
    code_challenge: challenge,
    code_challenge_method: 'S256',
  });
  window.location.assign(`${authorizationEndpoint}?${params.toString()}`);
}

// Called from app/auth/callback/page.jsx with the `code`/`state` query
// params Keycloak redirected back with. Returns { returnTo } on success.
export async function completeLogin(searchParams) {
  const code = searchParams.get('code');
  const returnedState = searchParams.get('state');
  const errorParam = searchParams.get('error');
  if (errorParam) {
    throw new Error(searchParams.get('error_description') || errorParam);
  }
  if (!code || !returnedState) {
    throw new Error('Sign-in response is missing the expected parameters.');
  }

  let pending = null;
  if (typeof window !== 'undefined') {
    try {
      const raw = window.sessionStorage.getItem(PENDING_KEY);
      pending = raw ? JSON.parse(raw) : null;
      window.sessionStorage.removeItem(PENDING_KEY);
    } catch {
      pending = null;
    }
  }
  if (!pending || pending.state !== returnedState) {
    throw new Error('Sign-in could not be verified (state mismatch). Please try again.');
  }

  const { tokenEndpoint } = await discoverEndpoints();
  const tokens = await exchangeToken(tokenEndpoint, {
    grant_type: 'authorization_code',
    client_id: OIDC_CLIENT_ID,
    redirect_uri: OIDC_REDIRECT_URI,
    code,
    code_verifier: pending.verifier,
  });

  writeSession(tokens);
  return { returnTo: pending.returnTo || '/' };
}

async function exchangeToken(tokenEndpoint, params) {
  const response = await fetch(tokenEndpoint, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams(params).toString(),
  });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(detail.error_description || detail.error || 'Sign-in failed.');
  }
  const payload = await response.json();
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token || null,
    expiresAt: Date.now() + Math.max(0, payload.expires_in - REFRESH_SKEW_SECONDS) * 1000,
    tokenEndpoint,
  };
}

// The one function lib/api/client.js calls before every request. Returns
// null whenever there is no real OIDC session -- the normal case for any
// DISABLE_AUTH deployment, and for a signed-out visitor otherwise -- so
// every existing request path is completely unaffected.
export async function getValidAccessToken() {
  const session = readSession();
  if (!session) return null;

  if (Date.now() < session.expiresAt) {
    return session.accessToken;
  }

  if (!session.refreshToken) {
    clearOidcSession();
    return null;
  }

  try {
    const refreshed = await exchangeToken(session.tokenEndpoint, {
      grant_type: 'refresh_token',
      client_id: OIDC_CLIENT_ID,
      refresh_token: session.refreshToken,
    });
    writeSession(refreshed);
    return refreshed.accessToken;
  } catch {
    // A failed refresh (expired refresh token, revoked session) means the
    // user is effectively signed out -- fail closed to no token rather
    // than retrying indefinitely or surfacing a raw fetch error from
    // inside every unrelated request.
    clearOidcSession();
    return null;
  }
}

export function isOidcAuthenticated() {
  return readSession() !== null;
}

export async function logout() {
  const session = readSession();
  clearOidcSession();
  if (!session) return;
  try {
    const { endSessionEndpoint } = await discoverEndpoints();
    if (endSessionEndpoint) {
      const params = new URLSearchParams({ client_id: OIDC_CLIENT_ID });
      // Fire-and-forget: the local session is already cleared above, so a
      // failure here (network, IdP down) never leaves the browser stuck
      // signed in from this app's point of view.
      fetch(`${endSessionEndpoint}?${params.toString()}`).catch(() => {});
    }
  } catch {
    // discoverEndpoints() failing is the same non-blocking case as above.
  }
}
