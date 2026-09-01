# SIH26101 six-lane team orchestration

Last revised: 1 September 2026

Purpose: six parallel, disjoint human workstreams with explicit agent boundaries, contracts, merge gates and a single release rhythm.

## 1. Six-person operating model

Assign exactly one primary human to each lane. One of the six also acts as the rotating release captain; release work is a duty, not a seventh seat. This allocation does not by itself prove SIH eligibility: the college SPOC must still confirm the current 2026 same-college, gender-composition and registration rules.

| Seat | Human | Agent/task name | Independent reviewer |
|---|---|---|---|
| Lane 1 — Experience |  | `lane-1-experience` | Lane 6 |
| Lane 2 — Core/data |  | `lane-2-core-data` | Lane 5 |
| Lane 3 — Competency intelligence |  | `lane-3-competency` | Lane 4 |
| Lane 4 — Content AI |  | `lane-4-content-ai` | Lane 3 |
| Lane 5 — API/integrations/analytics |  | `lane-5-api-integrations` | Lane 2 |
| Lane 6 — Quality/release |  | `lane-6-quality-release` | Lane 1 |

The product/release decision is made collectively, with the current release captain facilitating and recording the decision. No lane approves its own release evidence.

### Branch/worktree isolation

Each person works in a separate worktree and short-lived branch:

| Lane | Branch prefix |
|---|---|
| 1 | `codex/lane-1-experience/` |
| 2 | `codex/lane-2-core-data/` |
| 3 | `codex/lane-3-competency/` |
| 4 | `codex/lane-4-content-ai/` |
| 5 | `codex/lane-5-api-integrations/` |
| 6 | `codex/lane-6-quality-release/` |

Use one issue suffix per branch, for example `codex/lane-3-competency/role-target-v1`. Nobody commits directly to `main`, shares a worktree with another editing agent, or keeps a branch open across multiple phases.

## 2. System ownership map

The lanes are disjoint by **merge authority**, not by conversation. Anyone may inspect or review any module; only its owner edits it unless a written, time-bounded handoff is recorded.

| Lane | PS ownership | Mission | Owned paths / future modules | Must deliver | Explicitly does not control |
|---|---|---|---|---|---|
| **1. Professional Experience & Accessibility** | `PS-09`, `PS-13`; UI for `PS-14` | Deliver a coherent, professional, bilingual learner/admin experience while preserving Quest as optional practice | `frontend/**` | dynamic cross-domain routing, professional shell, English/Hindi path, accessible states, typed API consumption, client telemetry | backend schemas/rules, provider truth, CI/deployment |
| **2. Core Platform, Identity & Data** | `PS-01`; data boundary of `PS-15`, `PS-16` | Own persistence, authentication, tenancy and versioned records | `backend/db/**`, `backend/models/**`, `backend/schemas/**`, `backend/main.py`, future `backend/security/**`, `backend/tests/test_core_*.py`, `docs/contracts/data-authorization.md` | profile/evidence records, Alembic/PostgreSQL, OIDC, RBAC, tenant boundary, audit/source records, backup/restore | algorithms, prompts/retrieval, product routes, frontend |
| **3. Competency & Learning Intelligence** | `PS-02`, `PS-03`, `PS-04`; behavior for `PS-07`, `PS-08`, `PS-10` | Own role/activity/competency modelling, gap policy, pathways, adaptive practice and bounded learning labs | `backend/services/curricula.py`, `learning_engine.py`, `knowledge_graph.py`, `game_logic.py`, `heroes.py`, `monsters.py`, future `backend/labs/**`, `backend/tests/test_competency_*.py`, `docs/contracts/competency-evidence.md` | sourced taxonomy, behavioural anchors, evidence-aware gaps/pathways, adaptive progression and one statistics lab | document parsing/generation, routes, database models, UI |
| **4. Content AI, RAG & Evaluation** | `PS-06`; AI/content for `PS-07`, `PS-11`, `PS-12` | Own the learner assistant and source-to-reviewed-item processing/evaluation | `backend/services/content_ingestion.py`, `quiz_generator.py`, `ai_client.py`, `backend/routes/ai_real.py`, `services/**`, future `backend/ai/**`, `backend/tests/test_content_ai_*.py`, `docs/contracts/content-ai.md` | bounded ingestion, cited retrieval/assistant, generation, abstention, review checks, grading/evaluation and gold-set metrics | competency targets, product routes, identity, provider integration |
| **5. Product API, Integrations & Analytics** | `PS-05`, event/API part of `PS-10`, `PS-14`, `PS-17`; interoperability in `PS-15` | Expose stable workflows, own provider boundaries and produce privacy-safe workforce analytics | `backend/routes/**` except `ai_real.py`, `backend/services/learning_catalog.py`, future `backend/integrations/**`, `backend/analytics/**`, `backend/tests/test_api_integration_*.py`, `docs/contracts/openapi.json`, `docs/contracts/provider-adapter.md` | route decomposition, versioned OpenAPI, iGOT simulator/adapter, reconciliation and distinct-learner/descriptive analytics | model/table definitions, AI internals, frontend, release approval, speculative prediction |
| **6. Quality, Security, Release & Evidence** | acceptance for `PS-15`, `PS-16`; evidence for `PS-18` | Keep main releasable and turn every claim into testable evidence | `.github/**`, `docs/**` except lane-owned `docs/contracts/**`, root operational Markdown, future `deploy/**`, `docker/**`, `e2e/**`, `backend/tests/conftest.py`, `backend/tests/test_release_*.py`, security/load/accessibility test configuration | CI, E2E, threat model, scans, SBOM, deployment, observability, reset/offline runbooks, evidence pack and rehearsal | feature implementation except approved test hooks; unilateral contract changes |

Unlisted legacy files are assigned before their first modification using the nearest mission owner and recorded in `CODEOWNERS`/the ownership ledger. No “shared ownership” is allowed as a default.

The three flat legacy test files remain read-only regression baselines unless Lane 6 explicitly assigns one. New backend tests use the disjoint filename prefixes in the table; shared fixtures stay in Lane 6-owned `conftest.py`. Frontend unit/component tests remain inside Lane 1's `frontend/**`; cross-lane E2E stays in Lane 6's root `e2e/**`. This avoids a large test-move PR before feature work can start.

### Fairness and feasibility check

| Lane | One foundation outcome | One vertical-slice outcome | Deferred until trust/pilot phase |
|---|---|---|---|
| 1 | cross-domain navigation fixture | professional English/Hindi learner path | full design-system polish and broader languages |
| 2 | versioned profile/evidence schema | synthetic persistence plus reviewed OIDC/RBAC/data-rights foundation | approved production IdP; row-level organization tenancy; automated retention; encryption/key ownership and operational DR |
| 3 | sourced role/competency policy | explainable gap/path plus one bounded lab | psychometric calibration and outcome ranking |
| 4 | source/chunk/citation contract | cited quiz plus bounded learner assistant | full media pipeline and large evaluation corpus |
| 5 | split monolithic learning routes by domain | simulated iGOT/NSSTA path plus honest admin analytics | live provider access and predictive models |
| 6 | CI/E2E/evidence baseline | repeatable offline release candidate | formal audit/certification and production operations |

Each lane owns one foundation outcome and one demo-visible outcome before taking deferred scope. No lane may accept a second major Phase-2 feature while another lane’s foundation outcome is blocked. Rebalancing moves a complete issue and its acceptance criteria; it never creates shared file ownership.

## 3. Controlled coding agents

Create one Codex task/agent per lane. Each human owns the agent’s instructions, reviews its diff and remains accountable for the outcome.

### Mandatory agent prompt contents

1. Owned paths and one concrete issue.
2. Read-only access to other modules and contracts.
3. Acceptance criteria and verification commands.
4. “Do not invent APIs, government approval, data or measured results.”
5. Stop rule: propose a contract change instead of editing another lane.
6. Handoff format: files, behavior, assumptions, commands/results, risks and reviewer.

### Control rules

- Agents do not merge, deploy, send partner communications, change cloud state or approve their own work.
- A read-only coordinator may summarize issue, contract and CI status; it must not edit across lanes.
- No agent receives production secrets, real learner PII, copied browser cookies or unrestricted government data.
- Agent-generated competency content, questions, translations and compliance claims require the named human/domain reviewer.
- Run one editing agent per branch/worktree. Never point two editing agents at the same checkout.
- A human reviews both the diff and attached evidence before the PR enters the queue.

### Standard lane-agent prompt

```text
You own Lane <n> and may edit only: <owned paths>.
Implement issue <id>: <outcome>.
Acceptance criteria: <Given/When/Then list>.
Read docs/contracts read-only. If a shared contract is insufficient, return a contract-change
proposal and stop before editing another lane's files.
Add the required tests, run <commands>, and report exact results.
Do not fabricate integration success, official approval, course data, benchmarks or compliance.
Return: files changed, behavior, test evidence, assumptions, risks and reviewer needed.
```

## 4. Contract-first dependency model

The following thin shared contracts coordinate the six lanes:

| Contract | Owner | Consumers | Change approval |
|---|---|---|---|
| Data, subject/tenant and migration policy | Lane 2 | Lanes 3, 4, 5, 6 | Lanes 5 and 6 |
| Competency/evidence/pathway service interface | Lane 3 | Lanes 1, 5, 6 | Lanes 2, 5 and domain reviewer |
| Content/AI service interface and evaluation fixtures | Lane 4 | Lanes 1, 5, 6 | Lanes 3, 5 and domain reviewer |
| OpenAPI, provider contract and error/idempotency conventions | Lane 5 | Lanes 1, 2, 3, 4, 6 | Lanes 1, 2 and 6 |
| Release gates, fixtures and reset contract | Lane 6 | all | release captain plus one unaffected lane |

Recommended contract locations, created when implementation begins:

```text
docs/contracts/data-authorization.md
docs/contracts/competency-evidence.md
docs/contracts/content-ai.md
docs/contracts/openapi.json
docs/contracts/provider-adapter.md
docs/contracts/release-gates.md
```

### Dependency flow

```text
Official sources + agreed demo persona
                 |
                 v
       Lane 2 data/auth contract
          |                  |
          v                  v
 Lane 3 competency      Lane 4 content AI
          \                  /
           \                /
            v              v
          Lane 5 API/integrations
                   |
                   v
          Lane 1 experience
                   |
                   v
       Lane 6 end-to-end release gate
```

Lanes 1 and 6 start immediately against frozen fixtures. They do not wait idle for backend completion. Parallelism comes from agreed examples and interfaces, not from six incompatible implementations.

## 5. Work packages

### Lane 1 — Professional Experience & Accessibility

**Immediate package**

- Fix dynamic dungeon UUID routing and remove DSA-only client filtering.
- Build the professional learner/admin navigation; make Quest an optional practice action.
- Display `LIVE`, `SIMULATED`, `CATALOGUE`, `PROVISIONAL` and `NO EVIDENCE` states.
- Deliver loading, empty, error, offline and reset states.

**Next package**

- Complete one English/Hindi path with human-reviewed strings.
- Meet keyboard, focus, reflow/zoom, contrast, reduced-motion, accessible-error and screen-reader criteria.
- Surface target/source/formula/evidence versions and recommendation explanations.

**Acceptance evidence**

- Playwright scenarios for all four domains and the canonical Official Statistics loop.
- Manual keyboard + screen-reader checklist and 200% zoom evidence.
- No icon-only unlabeled controls or color-only status.

### Lane 2 — Core Platform, Identity & Data

**Immediate package**

- **PARTIAL against the original wording:** versioned role-target, evidence, assessment,
  source-version and audit records are done and cross-reviewed. Canonical competency definitions
  remain static Lane 3 service data; Lane 2 records their stable IDs in role/evidence/assessment
  records but did not add a canonical versioned competency table. Lane 3 must propose that contract
  if persistence beyond its versioned source/policy files is required.
- **DONE / live-drilled:** Alembic and PostgreSQL configuration with migration-gated PostgreSQL
  startup, while retaining deterministic SQLite local reset.
- **DONE / contracted:** latest-assessment repository semantics and the current one-deployment-
  database tenant rule consumed by Lanes 3–5. The HTTP endpoint/pathway integration belongs to
  Lane 5.

**Next package**

- **FOUNDATION DONE / cross-reviewed:** local OIDC verification, server-derived issuer/sub binding,
  fixed RBAC, deployment-database tenant guard and immutable audit events. Protected route wiring
  and real organization-row tenant filters remain open.
- **PARTIAL:** internal retention/deletion/export primitives, a dry-run-first retention enforcement
  mechanism (now with atomic `FOR UPDATE SKIP LOCKED` row-claiming for concurrent PostgreSQL
  `--apply`, live-drilled after a real race was found and fixed -- implemented/live-tested, not yet
  Codex-reviewed), and local PostgreSQL backup/restore are done and tested. The real registry has no
  approved maximum, so it currently deletes nothing; accountable durations and production
  scheduling remain open. A tested, deliberately unused application encryption envelope is Package
  Q; production KMS/HSM custody, storage/TLS/backup encryption, scheduled/offsite backup and DR
  remain open.

**Acceptance evidence**

- **DONE for local Lane 2 scope:** forward/backward migration, empty-DB bootstrap and restore drill.
- **PARTIAL:** object/function authorization matrix and function-level negatives exist. Real
  cross-organization row-tenant negatives require an authoritative organization model and schema.
- **NOT YET AN INTEGRATED PRODUCT PROPERTY:** current routes still trust caller-selected player
  identifiers. Lane 5 must compose Lane 2's verified principal, binding, tenant and object-scope
  checks before the controlled-pilot gate can pass.

### Lane 2 completion and cross-lane handoff

Lane 2 Packages A–N and Q are implemented and reciprocally reviewed on
`codex/lane-2-core-data/bootstrap`. Package P/S (retention enforcement, including a live-tested fix
for a real PostgreSQL concurrency defect Codex found and reproduced) is implemented and live-tested
by Claude Code but not yet Codex-reviewed — Codex handed remaining Lane 2 implementation work to
Claude Code after running out of session budget mid-review; exact review state remains in
`LANE2_SYNC.md`. The current full backend gate is **339 passed**. The following assignments are
copy-ready messages for the remaining owners. They are dependencies of a controlled pilot or
production claim, not reasons to reopen completed Lane 2 packages.

**Send to the Lane 5 person — Product API, Integrations & Analytics**

> Consume `docs/contracts/identity-authorization.md` and `data-authorization.md`. Attach Bearer JWT
> verification, active identity binding, permission, deployment-tenant and object-scope checks to
> every protected `backend/routes/**` operation. Never accept role, tenant or actor authority from
> request data; derive learner ownership from `BoundPrincipal`. Add consistent 401/403 responses and
> negative API tests. Implement `GET /learning/assessment/{player_id}/latest` and update pathway
> lookup to use `db.repositories.get_latest_assessment`. For admin aggregates, implement the
> contract's latest-per-`(player_id, curriculum_slug)` window semantics or propose a shared aggregate
> repository query—do not loop over the scalar helper or count historical runs. Expose identity-binding,
> export/deletion or audit-read routes only behind the documented matrix. Do not change Lane 2
> models/policy silently—propose a contract change.

**Send jointly to the Lane 1 and Lane 5 people — Browser identity**

> Build the browser Authorization Code + PKCE (`S256`) flow against the selected IdP, with exact
> redirect URIs, state/nonce binding, safe token/session handling, logout and accessible loading/
> error/recovery states. The existing username flow must stay visibly demo-only until protected API
> routes are complete. Do not infer application `player_id` from username, email or OIDC `sub`.

**Send to the Lane 6 person — Quality, Security, Release & Evidence**

> Integrate the Lane 2 branch through the merge queue and run CI at the integration head. Preserve
> the distinction between local verified primitives and protected-product claims. Add route-level
> security/E2E evidence, threat model, dependency/secret/SAST/DAST checks, rate-limit requirements,
> redacted telemetry, secrets/key-rotation operations, scheduled encrypted offsite backup, restore runbook,
> RTO/RPO drill and release evidence. Update public operational docs after merge. Do not call the
> local Docker backup helper a production DR system. Coordinate route/API enforcement changes with
> Lane 5 rather than editing its files unilaterally.

**Escalate to accountable product/government/privacy/security owners**

> Supply and approve the production IdP/client/claims contract; authoritative organization,
> department, trainer/cohort relationships; retention durations/lawful basis/data-rights process;
> encryption key ownership; and independent security/privacy/go-live authorization. Until an
> organization model is approved and migrated, one deployment database is one tenant and the system
> must not be described as multi-tenant.

**Lane 2 follow-up only after the authoritative inputs above exist**

- Add organization/department/cohort persistence, migrations and row-tenant policy; coordinate
  query/route enforcement with Lane 5 and integrated negative evidence with Lane 6.
- After privacy/legal approval, add the cited maximum to the retention registry and its explicit
  table mapping, then live-test the existing enforcement mechanism; Lane 6 owns scheduling and
  operations.
- Define IdP role-change reconciliation/audit semantics with the IdP owner and Lane 5 integration.

### Lane 3 — Competency & Learning Intelligence

**Immediate package**

- Label the 65/35 method as a versioned prototype policy and expose evidence coverage.
- Replace experience-only targeting with an explicit versioned role-target selection contract.
- Build one sourced MoSPI pilot taxonomy with competency-specific L1–L5 behavioural anchors.
- Keep prerequisite-aware pathway behavior deterministic and explainable.
- Build one bounded CPI, sampling or data-quality lab with deterministic expected output.

**Next package**

- Separate self-report, diagnostic, observed-practice, reviewer and provider evidence.
- Add readiness calculation only as a transparent versioned internal metric.
- Define recommendation features and explanations without inventing provider records.
- Add override/appeal inputs with reason and audit linkage.

**Acceptance evidence**

- Golden policy fixtures produce stable gaps and pathways.
- Every competency/target has source, authoring status and version.
- “No evidence” never becomes an unsupported low-ability judgment.
- The lab has resource bounds, learning feedback and no arbitrary code execution on the API host.

### Lane 4 — Content AI, RAG & Evaluation

**Immediate package**

- Preserve bounded TXT/MD/PDF/DOCX ingestion and add immutable source locators.
- Implement source version → chunk → access-filtered retrieval → cite; stop calling context stuffing RAG.
- Add page/section citations, weak-evidence abstention and structured evaluation output.
- Add one bounded learner-assistant flow that answers from approved cited material and escalates/abstains outside scope.

**Next package**

- Add provenance-preserving PPTX/video/audio-transcript ingestion required by `PS-11`.
- Implement `draft → auto_checked → expert_review → approved → pilot → published → retired`.
- Build a gold set and report retrieval, citation, item-validity and grader-vs-human metrics.
- Test document/answer prompt injection, hidden instructions, unbounded consumption and unsafe output.

**Acceptance evidence**

- Every accepted item resolves to immutable source locator/hash.
- Every assistant answer resolves to allowed source chunks or an explicit abstention/escalation.
- Cross-tenant retrieval tests return zero foreign chunks.
- Metrics include sample size, dataset version, threshold and failures.

### Lane 5 — Product API, Integrations & Analytics

**Immediate package**

- Split the monolithic `backend/routes/learning.py` by behavior into thin profile/competency, content/quiz, integration and analytics route modules without changing the public API.
- Publish versioned OpenAPI and stable error/idempotency conventions.
- Implement a deterministic, conspicuously labelled iGOT fixture behind a provider interface.
- Require an authenticated capability check before any `live/configured` status.
- Correct admin analytics to count latest distinct learners; align leaderboard period/copy.

**Next package**

- Add provider timeout, retry/jitter, circuit breaker, cursor, dead-letter and reconciliation.
- Add queued job status/cancellation APIs and privacy-safe aggregate endpoints.
- Implement a live adapter only after written endpoint/auth/data contract and sandbox access.
- Keep workforce outputs descriptive until a versioned representative dataset and prediction evaluation exist.

**Acceptance evidence**

- Contract tests for healthy, timeout, 401, 429, 5xx, duplicate and partial provider responses.
- API tests for idempotency, pagination and consistent error envelopes.
- Existing public endpoints remain compatible across the behavior-preserving route split.

### Lane 6 — Quality, Security, Release & Evidence

**Immediate package**

- Create CI: backend tests, frontend lint/build, contract checks and cross-domain Playwright smoke.
- Create clean setup/reset/seed commands and offline demo fixtures.
- Maintain claim-to-evidence ledger and release checklist.

**Next package**

- Add secret/dependency/SAST/DAST scans, SBOM, OWASP API/LLM cases and load smoke.
- Add structured redacted logs, metrics, traces, health/readiness and alert/runbook ownership.
- Coordinate GIGW/IS 17802/WCAG evidence, security assessment and deployment/DR plan.

**Acceptance evidence**

- No merge on red CI or missing migration/contract review.
- Five consecutive offline demo runs after reset and one recorded recovery drill.
- Release manifest includes commit, schema, fixture, model, prompt and retrieval versions plus known limitations.

## 6. Phased execution with all six lanes active

Do not attach calendar dates until the SPOC confirms the official deadline. Each phase is an exit gate.

| Phase | Lane 1 | Lane 2 | Lane 3 | Lane 4 | Lane 5 | Lane 6 | Exit condition |
|---|---|---|---|---|---|---|---|
| **0. Truth freeze** | click-path fixture | schema/auth audit | competency-policy audit | content/AI audit | API/provider audit | baseline CI/evidence | eligibility and claims classified |
| **1. Repair** | cross-domain routing | constraints/migration skeleton | versioned policy output | grounding corrections | route split + admin/link/status fixes | browser/build gates | code and docs agree |
| **2. Vertical slice** | professional UI | role/evidence records | sourced role pathway + lab | cited quiz + assistant | canonical API/simulator/analytics | E2E/offline/reset | three-minute loop passes |
| **3. Trust** | Hindi/accessibility | OIDC/RBAC/tenant | evidence/override policy | retrieval/review/gold set | reconciliation/jobs/analytics | abuse/security/a11y | synthetic pilot gate passes |
| **4. Release** | recovery/polish | backup/restore | frozen policy version | frozen model/prompt/retrieval | provider failure drills | deploy/observe/rehearse | release candidate signed |

If a phase exit fails, repair it before adding scope. Parallel feature count cannot compensate for a broken vertical loop.

Current Lane 2 status does not make the Phase 3 or Phase 4 row green by itself: its local identity,
policy and backup/restore foundations are complete, while protected routes, organization tenancy,
approved identity/privacy inputs and Lane 6 production operations remain explicit exit blockers.

## 7. Daily rhythm and merge queue

### Daily 24-minute control loop

1. **Six minutes:** one minute per lane—evidence produced, today’s outcome, blocking contract.
2. **Six minutes:** review dependency/contract proposals.
3. **Six minutes:** release captain reads CI, demo and official-source changes.
4. **Six minutes:** presenter rehearses one segment while another teammate runs a failure case.

Use issue IDs and evidence links, not general status monologues.

### Merge protocol

- Merge small PRs twice daily through one queue; rebase and run full CI at queue head.
- Contract and migration PRs merge before consumers.
- Every PR has one lane owner and one reviewer from the table in §1.
- Release captain rotates among all six and cannot approve their own lane.
- Main remains releasable; do not create a long-lived integration branch.
- Freeze features at least one complete rehearsal cycle before submission/demo.

## 8. Issue, PR and handoff contract

### Issue template

```text
Outcome:
Owner lane:
User/problem-statement link:
In scope / out of scope:
Contract used or change proposed:
Given/When/Then acceptance criteria:
Security/privacy/accessibility considerations:
Required automated and manual evidence:
Demo impact and rollback:
```

### Definition of Done

A task is done only when:

- acceptance and failure behavior are implemented;
- automated tests pass and relevant manual evidence is attached;
- authorization/tenant, privacy, accessibility and observability impacts are handled;
- API/data/policy/prompt/provider versions are updated where applicable;
- documentation and fixtures tell the truth;
- an independent human reviewed it;
- reset/rollback is known;
- CI on the merge commit is green.

“Agent finished,” “works locally,” “UI done,” or “API returned 200” are not completion states.

### Cross-lane handoff

When an owner needs another lane:

1. Open a contract proposal containing old/new examples and compatibility impact.
2. The contract owner and named approvers accept or reject it.
3. Merge the contract/producer change first with compatibility tests.
4. Consumers update in separate PRs.
5. Lane 6 verifies the integrated story.

Never solve a dependency by editing another lane’s files inside the same feature PR.

## 9. Decision rights

| Decision | Accountable lane/person | Required consultation |
|---|---|---|
| Problem scope and demo claim | release captain + six-person sign-off | official-source/domain owner |
| Data/auth/retention | Lane 2 | Lanes 5 and 6; privacy owner |
| Competency/learning policy | Lane 3 | Lane 2, domain reviewer, Lane 6 |
| Content/AI/evaluation policy | Lane 4 | Lane 3, domain reviewer, Lane 6 |
| API/provider contract | Lane 5 | Lanes 1–4 and 6 |
| UX/accessibility acceptance | Lane 1 | Lane 6 and representative user |
| Release/deploy/rollback | Lane 6 | release captain and all feature owners |
| Live iGOT claim | Lane 5 + release captain | authorized partner owner |
| Production-ready claim | accountable government/product/security/privacy owners | independent evidence; never agent-only |

Escalate immediately when a contract must break, personal data is introduced, a security boundary changes, sources conflict, live integration is proposed, or a phase exit cannot pass. Freeze the affected path until its accountable owner decides.

## 10. Six-person demo roles

| Person/role | Primary action |
|---|---|
| Presenter | drives the rehearsed story and truth labels |
| Product navigator | prepares personas/data, handles UI recovery and backup click path |
| Domain defender | answers FRAC/KCM/MoSPI/NSSTA/TPAC and content-validity questions |
| AI/architecture defender | answers competency, RAG, evaluation and architecture questions |
| Security/integration defender | answers identity, privacy, accessibility, iGOT boundary and scale questions |
| System operator/timekeeper | monitors health/logs, controls time, offline fixture and reset |

Demo roles need not match lane numbers, but every role has one primary and one named backup before rehearsal.

## 11. Production authorization remains external

Six parallel engineering lanes can produce a strong prototype and controlled-pilot candidate. A real government launch additionally needs accountable owners for:

- MoSPI/CBC/NSSTA competency and content approval;
- iGOT endpoint/auth/data-sharing contract;
- Data Fiduciary/Processor obligations and grievance contact;
- CISO/CERT-In contact and incident process;
- GIGW/IS 17802/accessibility evidence and authorized security clearance;
- hosting/procurement, DR, operations, budget and support;
- representative pilot and learning-outcome evaluation.

No lane or coding agent may self-certify those gates.
