// Shared stubs for browser tests. Nothing here talks to a real backend or
// identity provider; every call the app makes is answered from the test.

export const PLAYER = {
  player_id: 'p-1',
  username: 'approved_user',
  xp: 0,
  level: 1,
  hint_tokens: 3,
  preferred_mode: 'professional',
  accuracy_history: [],
};

export const IDP = {
  authorization_endpoint: 'http://idp.test/auth',
  token_endpoint: 'http://idp.test/token',
  end_session_endpoint: 'http://idp.test/logout',
};

// Stubs the identity provider and the API. `api` receives the request path and
// returns `{ status?, json }` or undefined to fall through to a 404.
export async function stubBackend(page, api = () => undefined) {
  await page.route('**/.well-known/openid-configuration', (route) => route.fulfill({ json: IDP }));
  await page.route('http://idp.test/token', (route) =>
    route.fulfill({ json: { access_token: 'access-token', refresh_token: 'refresh-token', expires_in: 300 } })
  );
  await page.route('http://idp.test/logout**', (route) => route.fulfill({ status: 200, body: '' }));
  await page.route('http://localhost:8000/**', (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const answer = api(path, request);
    if (answer) return route.fulfill({ status: answer.status || 200, json: answer.json });
    if (path === `/game/player/${PLAYER.player_id}`) return route.fulfill({ json: PLAYER });
    return route.fulfill({ status: 404, json: { detail: 'not stubbed' } });
  });
}

// Pretend a sign-in was started in this tab, then land on the callback URL the
// identity provider would redirect to.
export async function arriveFromIdentityProvider(page) {
  await page.goto('/login');
  await page.evaluate(() =>
    sessionStorage.setItem(
      'prism-oidc-pending',
      JSON.stringify({ verifier: 'v'.repeat(50), state: 'state-1', returnTo: '/' })
    )
  );
  await page.goto('/auth/callback?code=abc&state=state-1');
}

// A signed-in browser session without going through sign-in, for specs that
// are about a page rather than about authentication.
export async function seedSession(page, { onboardingSeen = true } = {}) {
  await page.addInitScript(
    ({ player, onboardingSeen }) => {
      localStorage.setItem('prism-auth', JSON.stringify({ state: { player, isAuthenticated: true, roles: [] }, version: 0 }));
      if (onboardingSeen) localStorage.setItem('prism_onboarding_seen', '1');
    },
    { player: PLAYER, onboardingSeen }
  );
}
