# Release gates, fixtures and reset contract

Owner: Lane 6 (Quality, Security, Release & Evidence)
Consumers: all lanes
Change approval: release captain plus one unaffected lane

Status: **PARTIALLY DEFINED.** The automated gates below are real and enforced on every pull
request. Browser end-to-end, accessibility, load and deployment gates are **not implemented** and
are listed as such rather than implied. Governing requirements: `docs/SIH26075_PROBLEM_STATEMENT.md`
and `SIH26075_MASTER_CHECKLIST.md`.

A change is releasable only when every gate in section 1 is green on the merge commit **and** the
manual evidence in section 2 has been recorded for anything section 1 cannot see.

## 1. Automated gates (enforced by `.github/workflows/ci.yml`)

| Gate | Job | What it proves | What it does not prove |
| --- | --- | --- | --- |
| Backend tests | `backend-tests` | `pytest` passes against a real PostgreSQL 16 service, including migration-chain, RBAC negative-authorization, and OCR tests (tesseract is installed in the job). | Production-scale behaviour; concurrency under real load. |
| Dependency audit | `backend-tests` | `pip-audit -r requirements.txt` finds no known vulnerable pin. New advisories can turn an unrelated PR red; fix by bumping the pin and re-running the affected tests. | Vulnerabilities in the frontend dependency tree. |
| API contract | `backend-tests` (`tests/test_openapi_contract.py`) | `docs/contracts/openapi.json` equals the document generated from the running app. Regenerate with `python -m scripts.export_openapi` from `backend/`. The voice and dev-login routers are excluded so the file is identical in every environment. | That a documented route behaves correctly. |
| Contract well-formedness | `contract-checks` | `openapi.json` parses as JSON. | Anything else; the drift check above is the meaningful one. |
| Frontend lint and build | `frontend-checks` | `npm run lint` and `npm run build` succeed. | Rendered behaviour, accessibility, or any user flow. |
| Secret scan | `security-checks` | `gitleaks` finds no hard-coded secret in history. | Secrets that are not pattern-detectable. |
| Static analysis | `sast` | Semgrep (`--config=auto --error`) is clean, with one documented rule exclusion (see the workflow). | Logic and authorization flaws. |

## 2. Manual evidence required before a demo or release

These cannot be inferred from CI. Record the exact command, count, date and operator.

1. **Browser round trip** of every changed user flow against a running backend and frontend
   (`CLAUDE.md` "Verification"). A build output is not evidence.
2. **Live identity check** when sign-in, registration, roles or `/auth/*` changed: sign in through
   the real Keycloak realm (`backend/keycloak/README.md`) as an approved user, a pending user and
   an admin. Stubbed identity-provider tests show routing only, not the integration.
3. **Migration check**: `alembic upgrade head` on an empty database and `alembic check` report no
   drift; `alembic downgrade` of the new revision succeeds.
4. **Known-limitations review**: `README.md` "Known limitations" matches reality for what changed.

## 3. Not implemented (do not claim)

- Automated browser end-to-end suite (the `e2e/` directory is a scaffold with no passing test).
- Frontend unit or component tests.
- Automated accessibility audit, and keyboard / screen-reader sign-off.
- Load, soak or failover testing.
- DAST and software bill of materials.
- Any deployment, rollback or environment-promotion automation.
- A scripted offline demo reset / seed procedure with a repeatability target.

## 4. Release manifest

Each release records, in `EVIDENCE.md`, at minimum: merge commit SHA, Alembic head revision,
`pytest` pass / fail / skip counts with the exact command, `pip-audit` result, lint and build
results, the manual evidence from section 2, and the known-limitations list in force. Model,
prompt and retrieval-corpus versions are recorded when any AI-assisted feature is part of the
release.

## 5. Change process

Proposals to change this contract go through the lane handoff process in
`docs/internal/SIH26075_TEAM_ORCHESTRATION.md`. Every lane consumes this contract, so raise changes
with the release captain before merging.
