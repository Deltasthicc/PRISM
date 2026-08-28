# Archive — pre-rename planning documents

Everything in this folder was written before the project was de-branded from its former working
name. It's kept as a historical record, not edited to erase that name, because these are dated
audits describing what was actually examined at the time — rewriting them would misrepresent that
history rather than correct it. Nothing in this folder describes the project's current state;
start at the root [`README.md`](../../README.md) for that.

## What's here

- **`SIH26101_FEASIBILITY_AND_ROADMAP.md`** — a full ten-plus-section audit of the SIH26101
  problem statement against the codebase as it existed at the time: pain points, feasibility,
  competitor/academic research, a judge Q&A stress test, and a prioritized roadmap.
- **`SIH26101_ORCHESTRATION_PLAN.md`** — a later, more detailed pass: a weighted completion ledger,
  a six-lane orchestration model, a P0–P3 backlog with effort estimates, acceptance gates, and a
  timeline. Also contains an explicit reconciliation of where it disagreed with earlier AI-authored
  analyses of the same problem statement (a factual-error correction on the database engine, a
  disputed TPAC acronym expansion, and an overstated reuse percentage among them).

Both documents were produced by a separate AI-assisted session working against an isolated copy of
the codebase, and neither was originally connected to this repository's git history. The work they
describe — a cross-domain competency model, an explainable gap-analysis engine, source-grounded
quiz generation, and an honest iGOT/NSSTA integration boundary — was reconstructed from the small
set of files that session did export, completed against the missing pieces those files implied,
integrated into this actual repository, and verified here (a real `pytest` run, a live server boot,
and live HTTP calls through the full profile → assessment → quiz → admin loop) rather than taken on
faith. The root README's "what's real right now" section reflects that verification, not this
archive's claims.

## What changed since these were written

- The project was de-branded: its former name and every reference to the original source
  repository have been removed from the active codebase and docs.
- The ~9 files these documents describe as missing (`models/learning.py`, `schemas/learning.py`,
  `services/content_ingestion.py`, `services/learning_catalog.py`, the `/academy` and `/admin`
  frontend routes, the `learning` API-client export, cross-domain dungeon seeding, and a new test
  file) were written and are now part of the live codebase, not aspirational.
- A real bug neither document caught — the DSA-only room-unlock check would have permanently
  locked every non-DSA competency room — was found and fixed during integration.
- Everything both documents flag as still missing (live iGOT/NSSTA integration, real identity and
  RBAC, official competency ownership, PostgreSQL migrations, a content-review workflow) is still
  missing today. That part of their analysis stands.
