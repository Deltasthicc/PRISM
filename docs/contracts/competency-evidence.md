# Competency, evidence and pathway service interface contract

Owner: Lane 3 (Competency & Learning Intelligence)
Consumers: Lanes 1, 5, 6
Change approval: Lane 2, Lane 5 and a named domain reviewer

Status: **NOT YET DEFINED** — this is a scaffold. The current implementation
(`backend/services/learning_engine.py`) is real and tested, but its interface is not yet frozen
as a versioned contract other lanes can depend on without reading the source.

## What this contract must define once implemented

- The evidence types Lane 3 accepts (self-report, diagnostic, observed-practice, reviewer,
  provider-imported) and how they are weighted, blended, or kept separate.
- The exact shape of a "gap" and a "pathway step" handed to Lane 1/5 (fields, versions, units).
- What "no evidence" means and how it is distinguished from a low score — it must never become an
  unsupported low-ability judgment (`CODEX.md` "Architecture invariants").
- The versioned role-target selection contract referenced in
  `SIH26101_TEAM_ORCHESTRATION.md` section 5 (Lane 3 immediate package), replacing the current
  experience-level-only cap.
- The bounded lab's input/output contract for `docs/SIH26101_PROBLEM_STATEMENT.md` PS-08.

## Change process

See `SIH26101_TEAM_ORCHESTRATION.md` section 8, "Cross-lane handoff".
