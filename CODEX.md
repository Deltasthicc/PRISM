# CODEX.md

Persistent project guidance for Codex working on PRISM.

## Read order and source of truth

Before implementation, read:

1. `docs/SIH26075_PROBLEM_STATEMENT.md` — canonical requirements and audited current state.
2. `SIH26075_MASTER_CHECKLIST.md` — priorities and completion gates.
3. `docs/internal/SIH26075_TEAM_ORCHESTRATION.md` — six-lane ownership and package boundaries.
4. `README.md` — verified present behaviour and known limitations.
5. Relevant contracts, source files, and tests.

Use `docs/internal/SIH26075_DELIVERY_PLAYBOOK.md` for demo/pitch decisions and
`docs/internal/SIH26075_SUBMISSION_DRAFT.md` for portal copy. `docs/archive/**`, dated evidence,
`docs/internal/LANE2_SYNC.md`, and files beginning `SIH26101_` preserve historical engineering
context; they are not current scope.

## Product definition

PRISM (Personalized Readiness Intelligence & Skill Mapping) targets SIH26075, CAPACITY CONNECT, for
the Ministry of Earth Sciences / India Meteorological Department. The objective is a centralized
learning and competency portal with three user roles:

- **Trainee:** professional profile, certificates, courses/resources, subject MCQs, progress, and
  course/content feedback.
- **Trainer:** expertise profile, resource library, questionnaire authoring/deadlines, and assigned
  cohort participation/performance.
- **Admin:** account approval, roles, catalogue/dashboard oversight, certificates, homepage
  publishing, and explainable subject-to-trainer discovery.

Existing competency, assessment, ingestion, course, analytics, database, identity, and multilingual
foundations are reusable. They are not evidence that missing SIH26075 role workflows work. The
canonical requirement table names every real, partial, and absent capability.

The professional experience is the default product surface. Quest mode is optional practice. XP,
heroes, and combat never determine competency, certification, authorization, or trainer matching.

## Six-lane ownership

1. **Role Experience & Accessibility** — `frontend/**`.
2. **Identity, Core Data & Authorization** — database, models, schemas, security, migrations.
3. **Competency & Matching Intelligence** — taxonomy, evidence/gaps/pathways, trainer matching, labs.
4. **Content, Quiz AI & Retrieval** — ingestion, trainer material processing, grounded generation,
   review, retrieval/assistant.
5. **Product API, Workflows & Analytics** — domain routes, course/cohort/questionnaire/certificate/
   feedback/announcement workflows and dashboards.
6. **Quality, Security, Release & Evidence** — CI, E2E, deployment, accessibility/load/security
   checks, current operational docs, and release evidence.

Exact boundaries and reviewers are in `docs/internal/SIH26075_TEAM_ORCHESTRATION.md`. Inspect or
review any lane, but edit another lane's files only after an explicit handoff.

## Architecture invariants

- Frontend calls the backend through `frontend/lib/api/client.js`.
- HTTP handlers stay thin; domain logic belongs in services; persistence belongs in models or
  repositories.
- “No evidence” is not low proficiency. The 65/35 demonstrated/self-report blend is a versioned
  prototype policy, not validated psychometrics.
- Competency targets, formulas, prompts, models, sources, chunks, role grants, publishing actions,
  and overrides must be versioned/auditable rather than silently mutable.
- Trainer access is server-side assignment-scoped. A client-supplied learner ID is never authority.
- Uploaded files, retrieved text, transcripts, and answers are untrusted. Never execute arbitrary
  learner code on the main API host.
- Generated items remain drafts until checks and authorized trainer review pass.
- Do not call whole-context prompting RAG or a role name a complete role workflow.
- Never fabricate a course, certificate, enrolment/completion event, API health, SSO state,
  approval, trainer qualification, or competency writeback.
- Do not place real employee data or secrets in prompts, logs, fixtures, screenshots, or the repo.
- Existing Official Statistics and iGOT/NSSTA content is legacy sample functionality, not a current
  SIH26075 requirement or official MoES/IMD integration.

## Truth boundary

Do not claim official approval, production readiness, compliance, scale, security, accessibility,
model quality, or live external integration without the exact evidence required by the master
checklist. Use **implemented**, **simulated**, **planned**, **blocked-external**, and **no evidence**
precisely. A passing unit test does not by itself prove a browser journey or deployed behaviour.

## Current implementation priority

1. Preserve a clean, repeatable demo while the problem-statement transition lands.
2. Define missing data/authorization contracts: approval, trainer expertise, cohorts, resources,
   questionnaires/deadlines, feedback, certificates, announcements.
3. Deliver one complete synthetic Admin → Trainer → Trainee golden path.
4. Add explainable subject-to-trainer matching and connected dashboards.
5. Prove role/object-scope negatives, responsive accessibility, migrations/DR, deployment smoke,
   and the final requirement evidence map.

Reinspect code and rerun relevant tests before repeating any count or completion claim; README and
evidence are snapshots, not permanent truth.
