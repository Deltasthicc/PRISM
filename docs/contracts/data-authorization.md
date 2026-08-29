# Data, subject and tenant authorization contract

Owner: Lane 2 (Core Platform, Identity & Data)
Consumers: Lanes 3, 4, 5, 6
Change approval: Lanes 5 and 6 (`SIH26101_TEAM_ORCHESTRATION.md` section 4)

Status: **NOT YET DEFINED** — this is a scaffold, not a working contract.

## What this contract must define once implemented

- The identity/subject model: how a request's caller is authenticated and how that identity
  reaches request handlers. Today there is none — see `CODEX.md` "Current verified reality"
  (username-only, no password, no server-derived session).
- Tenant/organization scoping: what a "tenant" means in this product and how every
  personal/content/evidence query is filtered by it.
- The versioned schema for `LearnerProfile`, `CompetencyAssessment` and related records,
  including what "latest assessment" means for a learner (`docs/SIH26101_PROBLEM_STATEMENT.md`
  PS-01).
- Retention, export and deletion primitives consumed by Lanes 5 and 6.
- The append-only audit-event shape for privileged reads/writes, role changes, content approval
  and exports.

## Change process

Any lane needing a new field, semantic, or authorization rule opens a contract-change proposal
against this file (`SIH26101_TEAM_ORCHESTRATION.md` section 8, "Cross-lane handoff") instead of
editing Lane 2's code directly.
