import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { clearOidcSession, completeLogin, getValidAccessToken, isOidcAuthenticated, logout } from '@/lib/auth/oidc';

const DISCOVERY = {
  authorization_endpoint: 'http://idp.test/auth',
  token_endpoint: 'http://idp.test/token',
  end_session_endpoint: 'http://idp.test/logout',
};

function mockFetch(handler) {
  const calls = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, init) => {
      calls.push({ url: String(url), init });
      return handler(String(url), init);
    })
  );
  return calls;
}

const json = (body, status = 200) => ({ ok: status < 400, status, json: async () => body });

function setPending(overrides = {}) {
  sessionStorage.setItem(
    'prism-oidc-pending',
    JSON.stringify({ verifier: 'verifier-value', state: 'state-1', returnTo: '/stats', ...overrides })
  );
}

beforeEach(() => sessionStorage.clear());
afterEach(() => vi.unstubAllGlobals());

describe('completeLogin', () => {
  it('rejects a response whose state does not match the one that was sent', async () => {
    setPending();
    mockFetch(() => json(DISCOVERY));
    await expect(completeLogin(new URLSearchParams('code=abc&state=other'))).rejects.toThrow(/state mismatch/);
    expect(isOidcAuthenticated()).toBe(false);
  });

  it('fails closed when no sign-in was started in this browser session', async () => {
    mockFetch(() => json(DISCOVERY));
    await expect(completeLogin(new URLSearchParams('code=abc&state=state-1'))).rejects.toThrow(/could not be verified/);
  });

  it('surfaces an error returned by the identity provider', async () => {
    await expect(
      completeLogin(new URLSearchParams('error=access_denied&error_description=User%20cancelled'))
    ).rejects.toThrow('User cancelled');
  });

  it('requires both code and state', async () => {
    await expect(completeLogin(new URLSearchParams('code=abc'))).rejects.toThrow(/missing the expected parameters/);
  });

  it('exchanges the code with the stored verifier, stores the session and returns returnTo', async () => {
    setPending();
    const calls = mockFetch((url) =>
      url.endsWith('/.well-known/openid-configuration')
        ? json(DISCOVERY)
        : json({ access_token: 'access-1', refresh_token: 'refresh-1', expires_in: 300 })
    );

    const result = await completeLogin(new URLSearchParams('code=abc&state=state-1'));

    expect(result).toEqual({ returnTo: '/stats' });
    const exchange = calls.find((call) => call.url === DISCOVERY.token_endpoint);
    const body = new URLSearchParams(exchange.init.body);
    expect(body.get('grant_type')).toBe('authorization_code');
    expect(body.get('code')).toBe('abc');
    expect(body.get('code_verifier')).toBe('verifier-value');
    expect(isOidcAuthenticated()).toBe(true);
    expect(await getValidAccessToken()).toBe('access-1');
  });

  it('consumes the pending state so a code cannot be replayed', async () => {
    setPending();
    mockFetch((url) =>
      url.endsWith('/.well-known/openid-configuration')
        ? json(DISCOVERY)
        : json({ access_token: 'a', expires_in: 300 })
    );
    await completeLogin(new URLSearchParams('code=abc&state=state-1'));
    await expect(completeLogin(new URLSearchParams('code=abc&state=state-1'))).rejects.toThrow(/could not be verified/);
  });
});

describe('getValidAccessToken', () => {
  it('returns null when nobody is signed in', async () => {
    expect(await getValidAccessToken()).toBeNull();
  });

  it('refreshes an expired access token with the refresh token', async () => {
    sessionStorage.setItem(
      'prism-oidc-session',
      JSON.stringify({ accessToken: 'old', refreshToken: 'r1', expiresAt: Date.now() - 1000, tokenEndpoint: DISCOVERY.token_endpoint })
    );
    mockFetch(() => json({ access_token: 'new', refresh_token: 'r2', expires_in: 300 }));
    expect(await getValidAccessToken()).toBe('new');
  });

  it('signs the user out locally when the refresh is rejected', async () => {
    sessionStorage.setItem(
      'prism-oidc-session',
      JSON.stringify({ accessToken: 'old', refreshToken: 'r1', expiresAt: Date.now() - 1000, tokenEndpoint: DISCOVERY.token_endpoint })
    );
    mockFetch(() => json({ error: 'invalid_grant' }, 400));
    expect(await getValidAccessToken()).toBeNull();
    expect(isOidcAuthenticated()).toBe(false);
  });

  it('drops an expired session that has no refresh token', async () => {
    sessionStorage.setItem(
      'prism-oidc-session',
      JSON.stringify({ accessToken: 'old', refreshToken: null, expiresAt: Date.now() - 1000, tokenEndpoint: DISCOVERY.token_endpoint })
    );
    expect(await getValidAccessToken()).toBeNull();
    expect(isOidcAuthenticated()).toBe(false);
  });
});

describe('logout', () => {
  it('clears the local session even when the identity provider is unreachable', async () => {
    sessionStorage.setItem(
      'prism-oidc-session',
      JSON.stringify({ accessToken: 'a', refreshToken: 'r', expiresAt: Date.now() + 60000, tokenEndpoint: DISCOVERY.token_endpoint })
    );
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('network down'); }));
    await logout();
    expect(isOidcAuthenticated()).toBe(false);
  });

  it('is a no-op without a session', async () => {
    const calls = mockFetch(() => json(DISCOVERY));
    await logout();
    expect(calls).toHaveLength(0);
    clearOidcSession();
  });
});
