# Release gates, fixtures and reset contract

Owner: Lane 6 (Quality, Security, Release & Evidence)
Consumers: all lanes
Change approval: release captain plus one unaffected lane

Status: **NOT YET DEFINED** — this is a scaffold. `.github/workflows/ci.yml` (added alongside
this file) currently runs backend tests and frontend lint/build only; see its inline comments for
what CI still does not cover.

## What this contract must define once implemented

- The exact P0 exit gate from `SIH26101_MASTER_CHECKLIST.md` section 3 ("P0 exit gate"),
  expressed as CI checks.
- The offline demo reset/seed procedure, and what "five consecutive successful resets" means in
  practice (`SIH26101_TEAM_ORCHESTRATION.md` section 5, Lane 6 acceptance evidence).
- The release manifest format: commit, schema, fixture, model, prompt and retrieval versions plus
  known limitations.

## Change process

See `SIH26101_TEAM_ORCHESTRATION.md` section 8, "Cross-lane handoff". Every lane is a consumer of
this contract — raise proposals in the daily control loop (section 7) before merging a change
here.
