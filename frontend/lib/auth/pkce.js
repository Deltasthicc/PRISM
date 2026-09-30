// RFC 7636 (PKCE) primitives, Web Crypto only -- no dependency, since this
// is exactly the kind of security-relevant code this project's own
// conventions (CLAUDE.md: "never fabricate", "bound... usage") say to keep
// small, real, and auditable rather than reach for a library.

function base64UrlEncode(bytes) {
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// 32 random bytes -> 43-character base64url string, comfortably inside
// RFC 7636's required 43-128 character range for a code_verifier.
export function generateCodeVerifier() {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}

export async function generateCodeChallenge(verifier) {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier));
  return base64UrlEncode(new Uint8Array(digest));
}

// CSRF/mix-up protection for the redirect round trip -- compared verbatim
// against the `state` Keycloak echoes back on /auth/callback.
export function generateState() {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return base64UrlEncode(bytes);
}
