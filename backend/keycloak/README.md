# Local Keycloak (OIDC identity, dev/test only)

Owner: Lane 2 (Core Platform, Identity & Data), Phase 2 / Package I.

This is a real, standards-compliant local OIDC provider used to test
`security/identity.py` honestly against real signed tokens and a real JWKS
endpoint. **It is not a government-approved production identity provider.**
`SIH26101_MASTER_CHECKLIST.md` section 5.1 tracks the real IdP integration
separately as `BLOCKED-EXTERNAL` — nothing here changes that.

## Start it

```powershell
cd backend
docker compose -f docker-compose.dev.yml up -d --wait
```

- Admin console: <http://localhost:8180> (`admin` / `prism_dev_local_only`)
- Realm: `prism` (auto-imported from `prism-realm-export.json` on
  first boot — re-imported from scratch every time the container recreates,
  since no volume is mounted for it; changes made by hand in the admin
  console will not survive a `--force-recreate`)
- Token endpoint: `http://localhost:8180/realms/prism/protocol/openid-connect/token`
- Discovery document: `http://localhost:8180/realms/prism/.well-known/openid-configuration`

## Test users

Every user's password is `prism_dev_local_only`. Each has exactly one realm
role, matching `SIH26101_TEAM_ORCHESTRATION.md` section 5's Lane 2 RBAC list.

| Username | Role |
|---|---|
| `demo-learner` | `learner` |
| `demo-trainer` | `trainer` |
| `demo-content-reviewer` | `content_reviewer` |
| `demo-department-admin` | `department_admin` |
| `demo-organization-admin` | `organization_admin` |
| `demo-auditor` | `auditor` |
| `demo-no-roles` | (none — for testing the no-role/forbidden path) |

## Mint a real token by hand

```powershell
curl -X POST http://localhost:8180/realms/prism/protocol/openid-connect/token `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "grant_type=password" `
  -d "client_id=prism-backend-dev" `
  -d "client_secret=prism_dev_local_only_client_secret" `
  -d "username=demo-learner" `
  -d "password=prism_dev_local_only" `
  -d "scope=openid"
```

The `prism-backend-dev` client uses the OAuth2 Resource Owner Password
Credentials grant (`directAccessGrantsEnabled`) purely so a token can be
minted from the command line for local testing. That grant type is
deprecated by RFC 9700 (OAuth 2.0 Security Best Current Practice) for real
user-facing login — a real browser flow would use authorization code + PKCE
instead, which is Lane 1/Lane 5's concern if/when a route ever needs
interactive login, not this module's.

The access token includes an explicit `aud: "prism-backend-dev"` claim (via
the client's `prism-backend-audience` protocol mapper) — Keycloak does not add
one by default, and `security/identity.py` requires it.

## What this does and doesn't prove

- Proves `security/identity.py` correctly verifies a real signed JWT via a
  real JWKS fetch, rejects tampered signatures, wrong issuers, and wrong
  audiences — see `LANE2_SYNC.md`'s Activity log for the exact live-verified
  scenarios.
- Key rotation is verified separately (Package P) against a local mock JWKS
  server using the exact `PyJWKClient` class this project ships — not
  against this specific Keycloak instance's own key-rotation UI/API, since
  both talk the same standard JWKS contract. See
  `backend/tests/test_core_identity.py`'s key-rotation tests.
- Does **not** prove anything about a real government IdP's behavior,
  claims, token format, or availability.
- Does **not** by itself authorize anything — `security/rbac.py` is what
  turns a verified subject into an application permission decision, through
  an explicit local identity binding (see `LANE2_SYNC.md`'s Phase 2 contract
  for why `sub` is never compared directly to `players.player_id`).
