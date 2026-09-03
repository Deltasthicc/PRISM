# Lane 5 Handoff

Last updated: 3 September 2026

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

## Remaining Lane 5 work

1. Apply the auth dependency to every protected learner, privileged, identity-binding,
   export/deletion and audit-read route, with negative tests for every operation class.
2. Finish the route split of `learning.py` into profile/competency, content/quiz, integration and
   analytics modules without changing public paths.
3. Expand `openapi.json` to the full stable API, including schemas, envelopes, pagination and
   idempotency conventions; add CI compatibility checks.
4. Add provider timeout, retry/jitter, circuit breaker, sync cursor, dead-letter and reconciliation
   semantics with contract tests for timeout, 401, 429, 5xx, duplicate and partial responses.
5. Replace environment-only integration status with an authenticated capability check. Until then,
   keep provider status `CATALOGUE` or `SIMULATED`, never `LIVE`.
6. Add queued job status/cancellation endpoints when the owning content-processing contract is ready.
7. Add privacy-safe descriptive analytics for provider events, learning hours, training distribution
   and emerging needs. Predictive workforce analytics remain deferred until representative data and
   evaluation evidence exist.
8. Coordinate browser Authorization Code + PKCE with Lane 1. The username-only flow remains a
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
- Lane 3 supplies role-target/evidence semantics; Lane 5 only forwards and exposes those contracts.
- Lane 4 owns AI internals and `ai_real.py`; Lane 5 should consume its public service contract.