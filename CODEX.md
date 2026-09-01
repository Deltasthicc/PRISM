# CODEX.md

Persistent project guidance for Codex working in `SIHLearningTool`.

## Read order and source of truth

Before the first implementation action, read:

1. `docs/SIH26101_PROBLEM_STATEMENT.md` — canonical user-supplied requirement contract (`PS-01`…`PS-18`).
2. `SIH26101_TEAM_ORCHESTRATION.md` — six lane/file/agent ownership boundaries.
3. `SIH26101_MASTER_CHECKLIST.md` — current priorities and readiness gates.
4. `README.md` — verified present behavior versus aspirations.
5. Relevant source and tests.

Use `SIH26101_WINNING_PLAYBOOK.md` for demo/pitch decisions. Treat `docs/archive/**` only as historical context.

The problem-statement capture is preserved at `docs/SIH26101_PROBLEM_STATEMENT.md` with attachment SHA-256 `A745A905D42A03D363875C844418D22189F00B15E8C733B7EC6453172D36D561`. Do not silently reduce the project to a quiz generator or RPG.

## Product definition

This is a working-name prototype for SIH26101, supplied as a MoSPI/DIID Smart Education problem. The target is a professional skill-intelligence and learning platform for India’s Official Statistical System that:

- builds profiles from role, assignment, qualifications, experience and training;
- maps statistical, technical, digital-governance and behavioural/managerial competencies;
- assesses evidence, explains gaps and creates personalized pathways;
- recommends iGOT course modules and NSSTA/TPAC-informed programmes;
- supports adaptive assessment, interactive learning, one bounded virtual lab and a learner assistant;
- generates cited MCQs/quizzes from documents, presentations and video transcripts;
- provides learner and administrator dashboards;
- is designed for multilingual, RBAC/SSO, secure API interoperability and controlled scale.

The primary product is the Professional experience (`/academy`, `/admin` and their successors). Quest mode remains an optional adaptive-practice layer. XP, heroes and combat must never determine competency scores.

## Current verified reality

- Backend: FastAPI + SQLAlchemy with a zero-setup SQLite demo profile and an additive PostgreSQL
  16/Alembic profile; 339 backend tests passed in the latest recorded full gate.
- Frontend: Next.js; lint passed in the last verification.
- Four curricula/34 competencies exist in the backend, but the supplied problem statement names a broader competency set.
- Only the DSA Quest browser path is currently verified; three other backend dungeons are blocked by frontend route/filter assumptions.
- The current “role-aware” result is actually experience-level-capped; other stored profile fields do not select a role target.
- Quiz generation supports bounded TXT/MD/PDF/DOCX and normalized source-span checking. It is context stuffing, not retrieval RAG; PPTX/video ingestion and item review are absent.
- Recommendations are internal practice/catalogue fallback. There is no authorized live iGOT/NSSTA enrolment, completion, SSO or score-writeback integration.
- Lane 2 provides a cross-reviewed local OIDC verifier, issuer/subject binding, fixed RBAC policy,
  deployment-database tenant boundary, audited data-rights/retention primitives and PostgreSQL
  migrations/backup-restore drills. The retention-enforcement job now atomically claims its
  PostgreSQL batch (`FOR UPDATE SKIP LOCKED`, live-drilled with 4 concurrent workers after a real
  race was found and reproduced) but is implemented/live-tested only, not yet Codex-reviewed —
  Codex handed remaining Lane 2 work to Claude Code after running out of session budget. Existing
  product routes do not invoke any of this foundation; there is no browser SSO, row-level
  organization tenancy, approved production IdP, frontend test suite, observability stack or
  production authorization. A CI workflow exists, but its presence alone is not evidence of a green
  remote run.

Reinspect code and run tests before repeating any status claim; these bullets are a baseline, not permanent truth.

## Six-lane ownership

When a human assigns a lane, edit only that lane’s controlled paths:

1. Professional Experience & Accessibility — `frontend/**`.
2. Core Platform, Identity & Data — database/models/schemas/security/migrations.
3. Competency & Learning Intelligence — curricula, gap/pathway and adaptive-practice rules/labs.
4. Content AI, RAG & Evaluation — ingestion, retrieval, assistant, quiz generation/grading and AI evaluation.
5. Product API, Integrations & Analytics — domain routes, iGOT/NSSTA adapters and dashboard analytics.
6. Quality, Security, Release & Evidence — CI/E2E/security/deployment/observability/current operational docs.

The exact path map, test subtrees, contracts and reviewers live in `SIH26101_TEAM_ORCHESTRATION.md`. If another lane must change, return a contract proposal; do not edit its files opportunistically. If the user explicitly assigns a cross-lane task, state the contract impacts and keep edits grouped by owner.

## Architecture invariants

- Frontend calls the backend only through `frontend/lib/api/client.js`.
- HTTP handlers stay thin; domain logic belongs in services; persistence belongs in models/repositories.
- The 65/35 demonstrated/self-report blend is a versioned prototype policy, not validated psychometrics.
- “No evidence” is not equivalent to low proficiency.
- Competency targets, formulas, prompts, models, sources, chunks, provider events and human overrides must become versioned/auditable rather than silently mutable.
- Never fabricate a course ID, enrolment/completion event, API health, SSO state, approval or competency writeback.
- An environment variable is not proof that an integration works. Use `SIMULATED`, `CATALOGUE`, `LIVE`, `PROVISIONAL` and `NO EVIDENCE` states precisely.
- Uploaded files, retrieved text, transcripts and learner answers are untrusted input.
- Never execute arbitrary learner code on the main API host.
- Generated items remain drafts until checks and authorized review pass.
- Do not describe whole-context prompting as RAG.
- Do not call the prototype framework or five proficiency levels official FRAC/KCM.
- Do not place real personal data or secrets in prompts, logs, fixtures, screenshots or the repository.
- Preserve Quest mode unless the user deliberately reverses that decision.

## Implementation priority

1. Confirm official rules and keep requirements/claims truthful.
2. Repair the existing browser path and establish CI/E2E.
3. Deliver one complete synthetic Official Statistics vertical loop.
4. Add versioned role targets/evidence and one bounded statistics lab.
5. Add cited retrieval, assistant, quiz review and one PPTX/transcript path.
6. Add labelled provider simulator, analytics and reconciliation.
7. Wire the existing identity/RBAC foundation into product routes, add authoritative organization
   tenancy and browser login, and complete accessibility/security/operational gates for a
   controlled pilot.

Do not build microservices, unrestricted code execution, speculative psychometric models or predictive workforce claims before the verified vertical loop works.

## Coding standards

### Python

- Python 3.11+; Pydantic v2 APIs only; type public functions.
- Avoid broad exception swallowing and network work at import time.
- Keep optional/heavy SDK imports lazy.
- Bound file, prompt, token, time, memory, retry and external-call usage.
- Add a regression test for every bug and negative authorization tests for protected data.

### Frontend

- Keep browser API calls centralized.
- Build professional, keyboard-accessible and responsive states before visual spectacle.
- Every async screen needs loading, empty, error, retry and offline/fallback behavior.
- Status must never be conveyed only by color or an unlabeled icon.
- Hindi/multilingual work includes navigation, inputs, errors, feedback and source display—not translated headings only.

### Data and AI

- Use synthetic demo identities/data.
- Store provenance and immutable identifiers; make latest-versus-historical semantics explicit.
- Require access filtering before retrieval, not after generation.
- Evaluate with versioned datasets and report sample size/failures alongside percentages.
- Prefer deterministic policy where an LLM adds no defensible value.

## Verification

Run the smallest relevant checks during implementation and the full gate before handoff:

```powershell
cd C:\Users\shash\Downloads\SIHLearningTool\backend
& .\.venv\Scripts\python.exe -m pytest
```

```powershell
cd C:\Users\shash\Downloads\SIHLearningTool\frontend
npm run lint
npm run build
```

For behavior crossing the UI/API boundary, run the documented service pair and an actual browser/API round trip. Do not use existing `.next` output as fresh build evidence. Report exact commands, pass/fail counts, skipped checks and environmental blockers.

## Definition of done

A change is done only when behavior and failure behavior satisfy acceptance criteria, tests/evidence pass, relevant security/privacy/accessibility impacts are handled, documentation tells the current truth, an independent human reviews it, and reset/rollback is understood.

Never equate “agent completed,” “HTTP 200,” “build artifact exists,” or “looks correct” with this definition.
