# SIH26075 six-lane team orchestration

Purpose: six parallel, disjoint workstreams for the CAPACITY CONNECT transition. This replaces the
SIH26101-specific scope in `SIH26101_TEAM_ORCHESTRATION.md`; the old file remains historical.

## Ownership

| Lane | Mission | Primary paths | SIH26075 deliverables |
|---|---|---|---|
| **1 — Role experience & accessibility** | Complete coherent Trainee, Trainer, and Admin journeys | `frontend/**` | role-aware navigation; trainee/trainer profiles; library, questionnaire, feedback, certificate, announcement, matching and dashboard UI; responsive/keyboard/localized states |
| **2 — Identity, core data & authorization** | Define durable entities and authorization boundaries | `backend/db/**`, `backend/models/**`, `backend/schemas/**`, `backend/security/**`, migrations, `test_core_*` | account approval state; profiles; cohorts/assignments; resources; questionnaires/deadlines; certificates; feedback; announcements; trainer expertise; audit/object-scope contracts |
| **3 — Competency & matching intelligence** | Own transparent skills, evidence, gaps, pathways, and trainer matching | competency/learning-engine services, labs, `test_competency_*`, `competency-evidence.md` | configurable taxonomy; assessment-to-evidence rules; explainable subject-to-trainer scoring; deterministic fixtures and no-evidence behaviour |
| **4 — Content, quiz AI & knowledge retrieval** | Turn approved trainer material into accessible resources and reviewed learning content | ingestion, retrieval, assistant, quiz generation/review, `test_content_ai_*`, `content-ai.md` | bounded media/document ingestion; resource processing states; source-grounded draft questions; reviewer workflow; cited/abstaining assistant |
| **5 — Product API, workflows & analytics** | Expose complete role workflows and aggregate metrics | `backend/routes/**` except AI-owned routes, catalogue/analytics services, `test_api_integration_*`, OpenAPI | approval/role APIs; courses/resources; questionnaires/attempts; cohort monitoring; feedback; certificates; announcements; trainer-search endpoint; connected dashboards |
| **6 — Quality, security, release & evidence** | Prove the final system and protect truth boundaries | `.github/**`, `e2e/**`, `deploy/**`, `docker/**`, release tests/docs | CI/E2E; security/accessibility/load checks; migrations/DR; observable deployment; clean reset; requirement evidence and final rehearsal |

Only a lane's owner edits its primary paths unless an explicit handoff is recorded. Anyone may
review another lane. Cross-lane interfaces are agreed in `docs/contracts/**` before parallel code
depends on them.

## Dependency order without file collisions

1. Lane 2 publishes schemas/migrations and scope rules; Lane 3 publishes matching inputs/outputs.
2. Lane 5 builds routes against those contracts; Lane 4 builds resource processing and quiz hooks.
3. Lane 1 consumes stable API shapes through `frontend/lib/api/client.js`.
4. Lane 6 owns integration/E2E evidence and rejects unsupported claims.

During contract work, use examples and fixtures rather than editing another lane's implementation.
Merge vertical slices in dependency order, but lanes can build against agreed fixtures in parallel.

## Package split

| Package | Owner | Review partner | Exit evidence |
|---|---|---|---|
| A. Accounts, approval, roles, profiles | Lane 2 | Lane 5 | migrations + object-scope tests + admin API contract |
| B. Courses, cohorts, enrolment and monitoring | Lane 5 | Lane 2 | route tests proving trainer sees only assigned cohort |
| C. Resource library and processing | Lane 4 | Lane 5 | upload/process/publish/view flow with failure states |
| D. Questionnaire deadlines and attempts | Lane 5 | Lane 4 | timing/status tests and one connected learner attempt |
| E. Competency evidence and trainer matching | Lane 3 | Lane 2 | explainable deterministic ranking with no-evidence case |
| F. Feedback, certificates and homepage publishing | Lanes 2 + 5 by path ownership | Lane 6 | persistence, permissions, routes, aggregate metrics |
| G. Three role experiences | Lane 1 | Lane 6 | responsive golden path and error/empty/loading states |
| H. Release candidate and submission evidence | Lane 6 | Lane 1 | clean setup, E2E, deployment smoke, evidence map |

## Non-negotiable boundaries

- Trainer access is assignment-scoped, not organization-wide by default.
- Admin approval and role grants are audited and deny-by-default.
- Trainer matching is explainable decision support, never an opaque automatic appointment.
- Uploaded content and learner input are untrusted; media is never executed by the API host.
- Generated items remain drafts until an authorized trainer approves them.
- Demo MoES/IMD competencies are labelled synthetic/team-authored until validated.
- Existing Official Statistics and iGOT/NSSTA modules may remain as legacy sample content, but they
  are not SIH26075 requirements and must not lead the primary demo or submission claim.
- Quest mode remains optional and cannot determine competency or certification.
- No lane may claim production readiness, compliance, official approval, or scale without the
  evidence named in `SIH26075_MASTER_CHECKLIST.md`.

## Completion definition

SIH26075 is demo-complete only when the P0 golden path runs from a clean database and each step has
a visible UI, authorized API, persisted state, failure handling, and automated acceptance evidence.
Backend primitives or disconnected screens alone do not close a requirement.
