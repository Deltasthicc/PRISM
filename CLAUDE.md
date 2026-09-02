# CLAUDE.md

Persistent project guidance for Claude Code working on `PRISM`.

## Required read order

Before implementing anything, read:

1. `docs/SIH26101_PROBLEM_STATEMENT.md` — canonical user-supplied requirements (`PS-01`…`PS-18`).
2. `SIH26101_TEAM_ORCHESTRATION.md` — six disjoint ownership lanes and contracts.
3. `SIH26101_MASTER_CHECKLIST.md` — current priority/readiness gates.
4. `README.md` — verified present behavior and known gaps.
5. Relevant source and tests.

Use `SIH26101_WINNING_PLAYBOOK.md` for demo/pitch choices. `docs/archive/**` is historical and must not be used as current implementation guidance.

The problem-statement capture is persisted at `docs/SIH26101_PROBLEM_STATEMENT.md` with attachment SHA-256 `A745A905D42A03D363875C844418D22189F00B15E8C733B7EC6453172D36D561`. Do not silently narrow the product to quizzes or the inherited RPG.

## Product definition

The project's name is finalized: **PRISM** (Personalized Readiness Intelligence & Skill Mapping). Use the short form "PRISM" in nearly all user-facing and code contexts; spell out the full name only where establishing what the acronym stands for (e.g. a README/landing first mention).

The user-supplied SIH26101 statement describes a MoSPI/DIID Skill Intelligence and Learning Platform for India’s Official Statistical System. It requires:

- comprehensive profiles using designation, department, role, assignment, qualifications, experience and prior training (`PS-01`);
- statistical, technical, digital-governance and behavioural/managerial competency frameworks (`PS-02`);
- competency assessment, gaps and personalized paths using learning history, department/future-role priorities and career progression (`PS-03`, `PS-04`);
- iGOT catalogue/recommendation/enrolment/completion/competency-update integration and NSSTA/TPAC programme recommendations (`PS-05`, `PS-17`);
- learner assistant, adaptive assessments/modules, virtual labs, multilingual resources and dynamic progress updates (`PS-06`, `PS-07`, `PS-08`, `PS-09`, `PS-10`);
- cited MCQs/quizzes from documents, presentations and videos with evaluation, explanations and feedback (`PS-11`, `PS-12`);
- learner/admin dashboards including training effectiveness and responsibly bounded workforce insight (`PS-13`, `PS-14`);
- secure, scalable, cloud-ready standard APIs, RBAC, SSO and secure data exchange (`PS-15`, `PS-16`);
- measurable improvement in competency and learning-resource utilization (`PS-18`).

The named AI/ML/NLP/LLM/semantic-search techniques are implementation options. Use deterministic logic when it is safer, more explainable or easier to validate.

## Product surfaces

- **Professional experience** — Academy, learner dashboard, admin dashboard, profile, gap, pathway, content, assistant and integration flows. This is the main SIH26101 product.
- **Quest mode** — optional adaptive-practice engagement. Keep it unless the user deliberately reverses that decision.

Quest XP, power-ups, heroes, guilds and combat never determine competency proficiency. Competency evidence stays explicit, versioned and explainable.

## Current verified baseline

- FastAPI + SQLAlchemy backend; PostgreSQL/Alembic is the migration-managed target, SQLite remains
  a documented local zero-setup demo profile only. As of the two-mode scaffold and Lane 2 test
  hardening pass (2026-09-02), `pytest -q` reports **402 passed with no PostgreSQL running** (6
  opt-in real-PostgreSQL tests in `test_core_retention_job_postgres_integration.py` skip cleanly)
  and **408 passed with the local `docker-compose.dev.yml` Postgres up** — both counts are correct,
  they are not a discrepancy; re-run before repeating either, it changes often. `pytest --cov=db
  --cov=models --cov=schemas --cov=security --cov=scripts` (requires `pytest-cov`, now in
  `requirements-dev.txt`) reports 94% line coverage across Lane 2-owned code, up from 84% before
  this pass — `db/database.py` went from 74% to 100%, and every file that was previously at 0%
  (`db/seed.py`, `schemas/accuracy.py`, `schemas/learning.py`, `schemas/question.py`) now has
  direct tests. Prior
  snapshots in this file's history (267, 299, 337, 339, 341/345, 347) were each taken mid-edit or
  before a subsequent fix, so treat any count here as a snapshot to re-verify, not a citation.
  `.github/workflows/ci.yml` exists, but no run
  against this branch is evidenced (`gh run list --branch <this-branch>` returns nothing as of this
  writing) — do not claim a green CI run without checking.
- Package P/S (atomic PostgreSQL row-claiming for the retention job, closing both Codex's Package R
  adversarial findings and a live-PostgreSQL concurrency defect Codex reproduced) and Package T (an
  independent audit fixing a stale pre-delete snapshot in `delete_subject_data()`'s reported counts
  and a non-injective `audit_actor` encoding) are **Codex-accepted** on independent cold immutable
  review (2026-09-01), including Codex's own reproduction of the four-worker drill. Package U (a
  second independent external audit's four DB-hardening claims, individually re-derived) rejected
  three of the four claims — RLS and legacy-ETL because there is no identified real source dataset,
  continuity requirement, approved field/identity mapping, conflict policy, reconciliation contract
  or acceptance owner (tenancy is irrelevant to whether that migration could exist); evidence
  self-hashing by the same writer role provides no tamper-evidence — and implemented the fourth in
  scoped form: a PostgreSQL trigger on `audit_events`. Codex's cold audit then found that trigger's
  unconditional `DELETE` rejection broke `scripts/retention_job.py`, whose only registered category
  is `audit_events` — the retention job would be unable to ever delete it once a maximum retention
  is cited. Package V's follow-up migration (`4631f204d4ba`) retired only the `DELETE` rejection,
  keeping the `UPDATE` rejection (named precisely: an UPDATE-only trigger is not "append-only"); the
  genuine append-only guarantee remains an application-layer property, never a database one. Codex's
  review of Package V **accepted its production migration/retention behavior outright** and raised
  two bounded test/evidence-hardening findings — a disposable-database cleanup gap (a failure
  between `CREATE DATABASE` and the fixture's `yield` used to leak the database) and a concurrency
  regression that only synchronized workers at thread-pool submission, not at genuinely overlapping
  candidate selection — both closed in a follow-up commit that also added a deterministic negative
  control proving the forced-overlap methodology is meaningful (an equivalent unlocked-select flow
  fails the same contract when forced to overlap the same way). Awaiting Codex's narrow re-review of
  exactly those four items. Full evidence and reasoning in `LANE2_SYNC.md`.
- Next.js frontend; lint passed in the last verification.
- Four backend curricula/34 competencies exist, but do not cover the full supplied competency list and have no MoSPI/CBC/NSSTA approval.
- DSA Quest works in the browser; non-DSA backend dungeons are blocked by frontend routing/filter assumptions.
- Current targeting uses `experience_level`; stored role/department/assignment fields do not select role targets.
- Current 65% demonstrated/35% self-report blend is a transparent prototype policy, not psychometrics.
- Bounded TXT/MD/PDF/DOCX ingestion and normalized source-span validation exist. Real retrieval RAG, PPTX/video ingestion, virtual assistant and review workflow do not.
- Recommendations are internal practice/catalogue fallback. Authenticated iGOT interfaces exist in public engineering documentation, but this repository has no approved endpoint contract, credentials or sandbox; no NSSTA API is verified.
- Lane 2 has implemented and reciprocally reviewed/accepted (live Keycloak + PostgreSQL, both
  agents cross-reviewing) OIDC bearer-token verification with real JWKS key-rotation handling, RBAC
  and identity-binding primitives, a controlled one-time first-admin bootstrap, PostgreSQL backup/
  restore, and a deliberately unwired versioned authenticated-encryption envelope
  (`security/encryption.py`). A bounded/validated retention-enforcement job is also implemented,
  including atomic `FOR UPDATE SKIP LOCKED` row-claiming for concurrent PostgreSQL `--apply` runs
  (live-drilled with 4 real concurrent workers after Codex reproduced a real race in the pre-fix
  version), and passes its own adversarial acceptance contract. Its final cleanup/forced-contention
  hardening at `ac5a2e7` passed Codex's narrow immutable re-review with no remaining correctness
  finding. See
  `docs/contracts/identity-authorization.md`, `docs/contracts/data-authorization.md` and
  `docs/contracts/encryption-key-ownership.md`. **None of this is wired into `backend/routes/**`
  yet** — every existing route remains an unauthenticated demo interface, and the product must not
  be described as protected until Lane 5 composes token verification, binding and permission checks
  into route code; no model currently uses the encryption envelope either. SSO (a real government
  IdP), multi-tenant isolation beyond one-database-per-deployment, production KMS/HSM key custody,
  frontend tests, observability and production authorization remain absent.

Reinspect and re-run evidence before repeating these claims. Update README/checklist in the same change when reality changes.

## Provenance and inherited code

The Quest engine/UI was forked from a differently branded DSA learning game and has been de-branded. Do not restore or invent the former brand in current code/docs/UI. `docs/archive/**` intentionally preserves historical records and should not be copied into current-facing material.

## Six-lane rule

Identify the owner in `SIH26101_TEAM_ORCHESTRATION.md` before editing:

1. Professional Experience & Accessibility
2. Core Platform, Identity & Data
3. Competency & Learning Intelligence
4. Content AI, RAG & Evaluation
5. Product API, Integrations & Analytics
6. Quality, Security, Release & Evidence

In coordinated six-person work, edit only the assigned lane’s controlled paths and test subtree. If a shared contract must change, write a contract proposal and let the owner implement it. Do not hide cross-lane changes in one PR. Claude does not merge, deploy or approve its own evidence.

## Architectural invariants

1. Browser calls go through `frontend/lib/api/client.js`; components/stores do not call `fetch` directly.
2. Routes stay thin, domain logic lives in services, persistence/contracts live in models/schemas.
3. “No evidence” never means low competency.
4. The 65/35 blend and any readiness score remain versioned prototype policies until validated.
5. Target frameworks, evidence, formulas, prompts, models, sources, chunks, provider events and overrides must be auditable/versioned.
6. Never fabricate course IDs, enrolment/completion, API health, SSO, approval or competency writeback. Environment variables alone do not prove integration.
7. Use `SIMULATED`, `CATALOGUE`, `LIVE`, `PROVISIONAL` and `NO EVIDENCE` precisely.
8. Source-span checking is a useful guardrail, not a zero-hallucination guarantee. Real RAG requires access-filtered retrieval and resolvable citations.
9. Generated questions remain drafts until automated checks and authorized review.
10. Uploaded content, transcripts, retrieved chunks and learner answers are untrusted. Never run arbitrary learner code on the API host.
11. Do not call the project’s taxonomy or proficiency labels official FRAC/KCM without authorized evidence.
12. Never place real PII, API keys, tokens or `.env` contents in code, prompts, fixtures, logs, screenshots or commits.

## Scope order

1. Truth/eligibility evidence, browser-path repair and CI/E2E.
2. One synthetic Official Statistics vertical loop.
3. Versioned role targets/evidence and one bounded statistics lab.
4. Cited retrieval, learner assistant, item review and one PPTX/transcript path.
5. Labelled provider simulator, course/progress events, learner/admin analytics and reconciliation.
6. Identity/RBAC/tenancy, migrations, accessibility, security and operations for a controlled pilot.

Do not prioritize microservices, Kubernetes, unrestricted code runners, unsupported IRT/BKT, or predictive workforce claims before the vertical loop passes.

## Coding conventions

### Python

- Python 3.11+ and Pydantic v2 APIs only.
- Type public functions; keep heavy/optional SDK imports lazy.
- Do not swallow broad exceptions or perform network work at import time.
- Bound file, decompression, page, prompt, token, time, memory, retry and external-call usage.
- Every bug fix gets a regression test; protected APIs get negative object/function/tenant authorization tests.

### Frontend

- Preserve the centralized API boundary.
- Prefer professional, accessible, responsive information design for required flows; reuse visual primitives where appropriate.
- Every async screen needs loading, empty, error, retry and offline/fallback states.
- Do not convey status by color or an unlabeled icon alone.
- Multilingual completion includes inputs, validation/errors, feedback, citations and navigation—not headings alone.

### Data and AI

- Use synthetic identities and demo data.
- Make latest-versus-history semantics explicit and retain provenance.
- Enforce access scope before retrieval and generation.
- Version evaluation datasets and report sample size, thresholds and failures with metrics.
- Provide abstention/human review for weak evidence and contested AI decisions.

## Ask versus act

Act within the assigned outcome and lane when the change is reversible and acceptance criteria are clear. Ask before choosing a final product name, removing Quest mode, introducing real personal data, claiming/activating a live government integration, changing the accepted scoring policy without versioning, or expanding into a materially different architecture.

## Verification

Run from the repository root, wherever this checkout lives (its own directory name is not part of
the product name and varies by clone -- do not assume `SIHLearningTool` or `PRISM`):

Backend:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
```

For UI/API behavior, run the services and perform an actual browser/API round trip. Existing `.next` output is not fresh build evidence. Report exact commands, counts, skipped checks and blockers.

## Definition of done

Done means acceptance and failure behavior work, relevant automated/manual evidence passes, security/privacy/accessibility effects are handled, docs match reality, an independent human reviewed the change, reset/rollback is known, and CI on the merge commit is green.

“Agent completed,” “HTTP 200,” “looks right,” or “artifact exists” is not enough.
