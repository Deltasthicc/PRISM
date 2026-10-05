import { describe, expect, it } from 'vitest';
import { generateCodeChallenge, generateCodeVerifier, generateState } from '@/lib/auth/pkce';

describe('PKCE primitives (RFC 7636)', () => {
  it('derives the S256 challenge from the RFC 7636 appendix B test vector', async () => {
    const verifier = 'dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk';
    expect(await generateCodeChallenge(verifier)).toBe('E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
  });

  it('produces verifiers inside the required 43-128 unreserved-character range', () => {
    const verifier = generateCodeVerifier();
    expect(verifier).toMatch(/^[A-Za-z0-9_-]{43,128}$/);
  });

  it('never repeats a verifier or a state value', () => {
    const verifiers = new Set(Array.from({ length: 50 }, generateCodeVerifier));
    const states = new Set(Array.from({ length: 50 }, generateState));
    expect(verifiers.size).toBe(50);
    expect(states.size).toBe(50);
  });

  it('produces url-safe state values with no padding', () => {
    expect(generateState()).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});
