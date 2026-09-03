# Learning provider adapter contract (iGOT / NSSTA)

Owner: Lane 5 (Product API, Integrations & Analytics)
Consumers: Lanes 1, 2, 3, 4, 6
Change approval: Lanes 1, 2 and 6

Status: **INITIAL INTERFACE IMPLEMENTED** — `backend/integrations/provider.py` defines the
replaceable protocol and deterministic `SimulatedIGOTAdapter`. Live provider access remains
blocked until an approved endpoint, authentication, data-sharing contract and sandbox exist.

## What this contract must define once implemented

- The `LearningProviderAdapter` interface: catalogue search, course details, enrolment request,
  completion import, health check and reconciliation (`SIH26101_TEAM_ORCHESTRATION.md` section 5,
  Lane 5 immediate/next package).
- The exact meaning of each integration status — `LIVE`, `SIMULATED`, `CATALOGUE`, `PROVISIONAL`,
  `NO EVIDENCE` (`CODEX.md` "Architecture invariants"). An environment variable alone must never
  imply `LIVE`; that requires a successful authenticated capability check.
- The deterministic `SimulatedIGOTAdapter` fixture contract and its test data.
- Timeout, retry/jitter, circuit-breaker, idempotency-key and dead-letter behavior expected of any
  real adapter.

The initial implementation returns `ProviderResult(status="SIMULATED", ...)` for every simulator
operation. It never creates course, enrolment, completion or health records and uses empty fixed
fixtures, making it suitable for contract tests without implying provider connectivity.

## Change process

See `SIH26101_TEAM_ORCHESTRATION.md` section 8, "Cross-lane handoff". A live adapter additionally
requires the external authorization tracked as BLOCKED-EXTERNAL in
`SIH26101_MASTER_CHECKLIST.md` section 4.3 before this contract may claim `LIVE` status.
