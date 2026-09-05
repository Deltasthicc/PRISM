# Lane 5 Handoff

Last updated: 5 September 2026

## Ownership

Lane 5 owns Product API, Integrations & Analytics:

- `backend/routes/**`, except `backend/routes/ai_real.py`
- `backend/services/learning_catalog.py`
- `backend/integrations/**`
- `backend/analytics/**`
- `backend/tests/test_api_integration_*.py`
- `docs/contracts/openapi.json`
- `docs/contracts/provider-adapter.md`

Primary requirements: `PS-05`, the event/API part of `PS-10`, `PS-14`, `PS-17`, and API interoperability in `PS-15`.

## Completed in this pass

- Added `backend/routes/authorization.py`, which converts Lane 2's verified bearer subject,
  active identity binding, deployment-tenant check and permission policy into reusable FastAPI
  dependencies.
- Protected `GET /learning/admin/overview` with `organization_admin` permission.
- Added protected `GET /learning/assessment/{player_id}/latest` with learner object-scope
  enforcement through the locally bound `player_id`.
- Changed pathway lookup to use Lane 2's deterministic `get_latest_assessment()` repository
  helper, including its assessment-ID tie-breaker.
- Corrected admin aggregates to use one latest assessment per
  `(player_id, curriculum_slug)` stream. Historical assessments no longer inflate gap counts.
- Added `backend/integrations/provider.py` with the `LearningProviderAdapter` protocol,
  `ProviderResult`, and deterministic `SimulatedIGOTAdapter`.
- Updated `docs/contracts/provider-adapter.md` with the initial interface and simulator truth
  boundary. The simulator returns `SIMULATED` and never creates enrolment/completion records.
- Replaced the empty OpenAPI scaffold with version `0.2.0` entries for the two protected routes.
- Added `backend/tests/test_api_integration_lane5.py` for latest assessment behavior, distinct
  analytics, simulator behavior, and 401/403 authorization boundaries.
- Split the learning route implementation into `learning_profile.py`,
  `learning_competency.py`, `learning_content.py`, `learning_integration.py`,
  `learning_analytics.py` and `learning_common.py`; `learning.py` remains a compatibility
  aggregator and existing `/learning/*` paths are preserved.
- Protected the remaining learner-owned profile, assessment, pathway and quiz routes with the
  updated composable Lane 2 dependencies. Quiz upload keeps its existing multipart shape and
  checks the submitted `player_id` against the verified bound principal in the handler.
- Expanded `docs/contracts/openapi.json` to version `0.3.0` with the current system, game, AI and
  learning route inventory, including bearer security declarations for protected learning routes.
- Added `backend/tests/test_api_contract_lane5.py` for OpenAPI path inventory and protected-route
  security declarations.
- Added deterministic simulator tests for empty catalogue results, partial negative course lookup
  results and repeated idempotency-key preservation.
- Added `docs/contracts/lane5-execution-checklist.md` to track implementation, review and external
  gates.

## Important boundaries

- Lane 2 remains the owner of models, repositories and security primitives. Do not edit those
  paths to solve a Lane 5 route problem; submit a contract proposal instead.
- OIDC `sub` is not an application `player_id`. Route ownership must come from `BoundPrincipal`.
- A role string, request body, query parameter or environment variable is not sufficient authority.
- `SIMULATED`, `CATALOGUE`, `LIVE`, `PROVISIONAL` and `NO EVIDENCE` must remain distinct.
- There is no approved government IdP, iGOT/NSSTA partner contract, credential, sandbox or live
  provider endpoint in this repository. Do not claim live integration.
- Organization scope currently means one deployment database. Cross-organization row tenancy is
  not implemented.

## Browser PKCE/session handoff

The governing contract is `docs/contracts/identity-authorization.md`, section 1. It requires:

- Authorization Code flow with PKCE using `S256`;
- exact pre-registered redirect URIs;
- transaction-bound `state` and `nonce`;
- secure access-token/session handling and logout; and
- no implicit grant or resource-owner-password grant.

`LANE2_INTEGRATION_GUIDE.md` repeats this as the Lane 1/Lane 5 browser handoff. Lane 2 does not
implement the browser flow. Lane 1 owns the browser UI and accessible login/recovery experience;
Lane 5 supplies the protected API contract and coordinates the redirect/session handoff.

The current frontend still uses the username-only demo login and local browser session state in
`frontend/app/login/page.jsx`, `frontend/store/useAuthStore.js` and
`frontend/lib/api/client.js`. No Authorization Code + PKCE client, token exchange, state/nonce
validation or OIDC logout flow exists yet. The local Keycloak realm is development/test-only and
is not a government-approved production IdP.

For the next browser-identity handoff, Lane 1 must agree with Lane 5 and the accountable IdP owner
on the client ID, exact redirect/logout URIs, issuer, audience/claims and session error behavior.
Do not infer `player_id` from username, email or OIDC `sub`; the API resolves `(issuer, sub)` through
the active local identity binding.

## Remaining Lane 5 work

1. Apply the auth dependency to every protected learner, privileged, identity-binding,
   export/deletion and audit-read route, with negative tests for every operation class.
2. Expand `openapi.json` with endpoint-specific schemas, stable error envelopes, pagination and
  idempotency conventions; add CI compatibility checks. The current `0.3.0` document is a path
  inventory with shared response descriptions, not a complete schema-level contract.
4. Add provider timeout, retry/jitter, circuit breaker, sync cursor, dead-letter and reconciliation
   semantics with contract tests for timeout, 401, 429, 5xx, duplicate and partial responses.
5. Replace environment-only integration status with an authenticated capability check. Until then,
   keep provider status `CATALOGUE` or `SIMULATED`, never `LIVE`.
6. Add queued job status/cancellation endpoints when the owning content-processing contract is ready.
7. Add privacy-safe descriptive analytics for provider events, learning hours, training distribution
   and emerging needs. Predictive workforce analytics remain deferred until representative data and
   evaluation evidence exist.
8. Coordinate browser Authorization Code + PKCE with Lane 1 using
  `docs/contracts/identity-authorization.md` section 1. The username-only flow remains a
  visibly demo-only path.

## Verification

Expected command from a prepared checkout:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pytest -q tests/test_api_integration_lane5.py
```

This checkout did not contain `backend/.venv`, and the available system interpreter lacked the
`alembic` dependency, so the test suite could not execute here. Syntax and editor diagnostics
should be run after dependencies are installed.

## Reviewer and integration notes

- Required independent reviewer: Lane 2, per the team orchestration table.
- Lane 6 should verify route-level 401/403 evidence, OpenAPI compatibility, rate-limit policy,
  redacted telemetry and CI integration.
- Lane 1 consumes the protected API contract and must not infer `player_id` from username, email or
  OIDC subject.
- Lane 1 should read `docs/contracts/identity-authorization.md` section 1 and
  `LANE2_INTEGRATION_GUIDE.md` before implementing browser login. Lane 5 does not own the frontend
  login UI, but must review the API/session handoff and claims assumptions.
- Lane 3 supplies role-target/evidence semantics; Lane 5 only forwards and exposes those contracts.
- Lane 4 owns AI internals and `ai_real.py`; Lane 5 should consume its public service contract.