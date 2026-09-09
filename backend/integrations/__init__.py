"""Lane 5 (Product API, Integrations & Analytics) — the `LearningProviderAdapter`
interface and the simulated/live iGOT and NSSTA adapters described in
docs/internal/SIH26101_TEAM_ORCHESTRATION.md section 5 (Lane 5) and docs/SIH26101_PROBLEM_STATEMENT.md
PS-05/PS-17. Contract: docs/contracts/provider-adapter.md.

`integrations/provider.py` defines `LearningProviderAdapter` (the Protocol),
`SimulatedIGOTAdapter` (a deterministic offline fixture, `status="SIMULATED"`)
and `LiveHTTPProviderAdapter` (a real adapter shape that makes a genuine,
short-timeout HTTP health check against a configured provider base URL and
reports `LIVE` only on real success, `ERROR` otherwise). `services/
learning_catalog.py::integration_status()` selects between them based on
whether `IGOT_API_BASE_URL`/`NSSTA_API_BASE_URL` is set, and reports the
health check's genuine outcome, not the env var's mere presence (CODEX.md
"Architecture invariants": an environment variable alone is never proof that
an integration works). No approved iGOT/NSSTA endpoint contract, credentials
or sandbox exist yet, so `LiveHTTPProviderAdapter` against a real deployment
today will honestly report `ERROR` -- that boundary is tracked as
BLOCKED-EXTERNAL in SIH26101_MASTER_CHECKLIST.md section 4.3, not hidden by a
fabricated `LIVE`.
"""
