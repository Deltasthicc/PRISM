# SIH26101 master checklist

Last evidence review: 1 September 2026

Historical repository baseline: commit `429df46` on `main`

Current Lane 2 evidence base: `codex/lane-2-core-data/bootstrap`; Packages A–N are accepted, Package
Q is independently accepted at `f343455`, and Package O reconciles current documentation/handoffs.
Package P/S (retention enforcement, including atomic PostgreSQL row-claiming for concurrent
`--apply`) is implemented and live-tested by Claude Code after Codex reproduced and handed off a
real concurrency defect; Codex ran out of available session budget and explicitly transferred
remaining Lane 2 work to Claude Code, so Package P/S awaits Codex's final immutable review
whenever that resumes rather than being marked Codex-accepted here.

Requirement source: `docs/SIH26101_PROBLEM_STATEMENT.md` (`PS-01`…`PS-18`)

Companion documents: `SIH26101_WINNING_PLAYBOOK.md` and `SIH26101_TEAM_ORCHESTRATION.md`

This is the single execution ledger for the project. It separates what the repository proves, what an official source proves, and what is still a proposal. A checked item means its acceptance evidence exists; it does not mean that an AI suggested it.

## Evidence labels

- **VERIFIED** — inspected or executed against this repository.
- **OFFICIAL** — supported by a primary government/standards source.
- **DECISION** — a deliberate team choice, not an external fact.
- **PROPOSED** — useful design direction that still needs implementation and validation.
- **BLOCKED-EXTERNAL** — cannot be truthfully completed without a partner, official approval, or real pilot data.

## 1. Current truth, without pitch inflation

| Area | Current state | Evidence |
|---|---|---|
| Backend | FastAPI/SQLAlchemy; SQLite zero-setup demo plus PostgreSQL 16/Alembic profile with migration-gated PostgreSQL startup | **VERIFIED** |
| Automated tests | 339/339 backend tests passed on 1 Sep 2026 after Package P/S's PostgreSQL concurrency fix (live-drilled, not yet Codex-reviewed); earlier counts (42/237/272/337) remain historical, not overwritten; 29 Aug frontend lint evidence remains historical | **VERIFIED** |
| Curricula | Four curricula and 34 competencies are seeded and usable through backend APIs | **VERIFIED** |
| Quest UI | DSA is playable; the other three domains are not currently reachable end-to-end through the browser | **VERIFIED** |
| Competency targeting | Target cap is selected only from `experience_level`; designation, department, job role, assignment, qualifications and career goal are stored but do not affect targets | **VERIFIED** |
| Assessment formula | 65% demonstrated performance + 35% self-rating when both exist; this is a transparent prototype policy, not validated psychometrics | **VERIFIED** |
| Quiz grounding | TXT/MD/PDF/DOCX extraction is bounded; generated excerpts are matched after whitespace/case normalization, not as literal byte-for-byte substrings | **VERIFIED** |
| Assistant/media scope | No learner virtual assistant; no PPTX or video/audio transcript ingestion | **VERIFIED** |
| Retrieval | Whole extracted text is supplied to generation; chunking, embeddings, retrieval and a vector store are not present | **VERIFIED** |
| Recommendations | Internal practice plus links to provider catalogues; no real enrolment, completion, or catalogue sync | **VERIFIED** |
| iGOT boundary | Authenticated iGOT/KB-iGOT interfaces exist publicly in integration documentation, but this project has no approved endpoint contract, credentials, or sandbox | **OFFICIAL + VERIFIED** |
| Identity/security | Product routes remain username/player-ID demo interfaces and are not protected. Lane 2 implements local OIDC JWT verification, issuer/sub binding, fixed RBAC/bootstrap, deployment-database tenant guards and audited security/data-rights primitives; browser SSO, row-level organization tenancy, route enforcement, approved production IdP, rate limits and secrets operations remain open | **VERIFIED** |
| Admin metrics | Aggregate-only response, but repeated historical assessments inflate `learner_count` for a gap | **VERIFIED** |
| Dashboard coverage | No provider-derived learning hours, training-effectiveness measurement, emerging-skill analysis or validated predictive analytics | **VERIFIED** |
| Guild/leaderboard | Guild backend exists; frontend lacks raid question/submit flow. UI says weekly while backend rank is lifetime XP | **VERIFIED** |
| Delivery | CI workflow and Alembic migration framework exist; no fresh remote-CI result is claimed here. Frontend tests, production deployment definition, observability stack and repository licence remain absent/unverified | **VERIFIED** |

The frontend production build was not independently completed in the current restricted environment. Existing `.next` output is not release evidence. A clean CI build remains mandatory.

## 2. Decisions and corrections from the pasted 174 KB planning source

- [x] **Keep Quest mode as an optional engagement layer.** Do not execute the pasted recommendation to delete it. The primary experience must become a professional learning workspace; Quest mode is a secondary practice mode. **DECISION**
- [x] **Do not call the proposed labels “official FRAC levels.”** FRAC officially connects roles, activities and competencies. CBC now publishes the Karmayogi Competency Model (KCM) and says it is integrated with iGOT. The labels “Basic Awareness” through “National Expert” were not verified in the cited official material. **OFFICIAL**
- [x] **Treat Role Readiness Index as an internal product metric only.** Any formula and weighting must display its version, inputs and provisional status until an authorized domain owner validates it. **DECISION**
- [x] **Do not invent iGOT course IDs, URLs, completion records, NSSTA schedules, API success, or government approval.** A simulator must be visibly labelled `SIMULATED`; a live adapter must prove authenticated partner connectivity. **DECISION**
- [x] **Reject the baseline claim “JWT already exists.”** It did not exist at `429df46`; Package I
  subsequently added and live-tested local OIDC JWT verification. **VERIFIED**
- [x] **Reject “all four domains work end-to-end.”** Only backend coverage is cross-domain today; browser Quest routing is DSA-only. **VERIFIED**
- [x] **Reject the pasted 28/100 score and fixed judging weights as official.** They may be private prioritization aids only. **DECISION**
- [x] **Keep the useful additions:** item-review lifecycle, grounded RAG evaluation, bilingual path, one statistics lab, adapter/simulator boundary, privacy/security gates, and contract-first team ownership. **DECISION**

### 2.1 Requirement traceability from the new problem-statement capture

- [x] Preserve the complete supplied scope as numbered requirements `PS-01`…`PS-18` in `docs/SIH26101_PROBLEM_STATEMENT.md`.
- [x] Map every requirement to one primary lane and distinguish a synthetic demo from controlled-pilot/production evidence.
- [ ] Require every implementation issue and PR to name at least one `PS-*` requirement or explicitly state `infrastructure-only`/`defect-only`.
- [ ] Maintain a final evidence matrix with columns: requirement, implementation, test/demo proof, truth status, owner and remaining external gate.

## 3. P0 — eligibility, truth and an unbreakable vertical slice

Do these before adding new “AI” features.

### 3.1 Eligibility and source freeze

- [ ] Obtain the current SIH 2026 rule/guideline PDF or portal export from the college SPOC and store its link/hash in the evidence log.
- [ ] Confirm the six-person roster against the current official rule: all six registered students, same-college status, leader designation and required gender composition. The latest official senior-edition guideline independently retrieved is SIH 2024; the college SPOC must still confirm the 2026 rule.
- [x] Divide implementation into six parallel, disjoint ownership lanes with one controlled coding agent/task per lane; see `SIH26101_TEAM_ORCHESTRATION.md`.
- [ ] Confirm problem statement text, organization, category, submission deadline, deck template and idea cap from the official portal. Third-party SIH aggregators are discovery aids only.
- [ ] Assign one SPOC liaison and one final presenter; record backups for both.
- [ ] Add an `EVIDENCE.md` file containing official URLs, retrieval date, local hashes for downloaded rules, test commands and demo proof.
- [ ] Resolve repository licence/provenance before public release or transfer.

### 3.2 Repair the current product path

- [ ] Add a real dynamic dungeon route such as `frontend/app/dungeon/[dungeonId]/page.jsx`.
- [ ] Remove the fake `dsa-dungeon-01` constant and pass the selected UUID end-to-end.
- [ ] Stop filtering every dungeon through the DSA-only `TOPIC_GRAPH`.
- [ ] Add generic/domain-specific room labels and visuals for non-DSA topics.
- [ ] Fix internal recommendation links so they target the selected dungeon/competency, not `/dungeon#...` without a resolvable dungeon.
- [ ] Add an end-to-end browser test covering Academy → each of four domains → room renders → one answer submits → progress returns.
- [ ] Add browser tests for refresh, back navigation, double submit, missing API, empty data and a second learner.
- [ ] Finish a clean frontend production build in CI; do not use old `.next` output as evidence.

### 3.3 Make one problem-statement vertical slice undeniable

- [ ] Choose **Official Statistics** as the canonical demo domain; keep DSA as an engineering sample, not the pitch centre.
- [ ] Define one real role persona and target matrix using sourceable MoSPI/CBC material; label any team-authored target as `PROVISIONAL`.
- [ ] Complete: profile → diagnostic → competency evidence → gap explanation → ordered pathway → provider-labelled recommendation → practice → re-assessment → admin change.
- [ ] Make every result expose `why`, `evidence`, target version, formula version and timestamp.
- [ ] Correct admin gap counts to count distinct learners from their latest relevant assessment.
- [ ] Replace “weekly leaderboard” copy or implement a real weekly time window.
- [ ] Either complete the guild raid interaction or remove it from the official demo path.

### P0 exit gate

- [ ] One clean checkout starts from documented commands.
- [ ] Backend tests, frontend lint, frontend build and cross-domain browser smoke all pass in CI.
- [ ] The three-minute demo succeeds offline five consecutive times after a data reset.
- [ ] Every slide claim maps to a working screen, test, source, or explicitly labelled roadmap item.

## 4. P1 — trustworthy differentiation

### 4.1 Competency model

- [ ] Model `framework_version`, `role`, `activity`, `competency`, `target_level`, `source`, `approved_by`, `valid_from` and `valid_to`.
- [ ] Use designation/job role/department/assignment to choose an explicit versioned role target; stop calling experience-cap targeting “role-aware.”
- [ ] Separate self-report, diagnostic, observed practice, reviewer evidence and imported provider evidence.
- [ ] Display evidence coverage and uncertainty; “no evidence” must never become “low ability.”
- [ ] Add human override with reason, actor and immutable audit event.
- [ ] Map the current curriculum to KCM/FRAC only where an official mapping can be cited; do not imply CBC approval.
- [ ] Seek MoSPI/NSSTA/CBC/domain-expert validation. **BLOCKED-EXTERNAL**

### 4.2 Grounded content and quiz governance

- [ ] Create immutable source, source-version and chunk records with page/section locators and hashes.
- [ ] Add provenance-preserving PPTX and video/audio-transcript ingestion for `PS-11`; retain slide/timecode locators and bounded media-processing jobs.
- [ ] Implement parser → semantic chunk → embedding → access-filtered retrieval → generation → verification.
- [ ] Show page/section citations and source preview for every generated item.
- [ ] Add abstention when retrieved evidence is insufficient or contradictory.
- [ ] Treat uploaded/retrieved text as untrusted data; defend against embedded prompt instructions.
- [ ] Add item lifecycle: `draft → auto_checked → expert_review → approved → pilot → published → retired`.
- [ ] Auto-check one defensible answer, unique options, answer leakage, unsupported numbers, duplicates and unsafe content.
- [ ] Require an authorized reviewer before generated items enter scored assessments.
- [ ] Build a gold set with domain-expert labels; measure citation correctness, groundedness, answer validity, Recall@K and cross-tenant leakage.
- [ ] Version prompts, models, retrieval configuration and evaluation results.
- [ ] Add a bounded learner assistant for `PS-06`: answer only from authorized cited sources, expose limitations, abstain/escalate outside scope, and test prompt injection/data leakage.

### 4.3 Integration that is honest and replaceable

- [ ] Define `LearningProviderAdapter` for catalogue search, course details, enrolment request, completion import, health and reconciliation.
- [ ] Implement a deterministic `SimulatedIGOTAdapter` with conspicuous simulated badges, fixed fixtures and contract tests.
- [ ] Rename current “configured” status: an environment variable alone must not prove integration; require a successful authenticated health/capability check.
- [ ] Keep provider record IDs, timestamps, source environment and raw response hash for imported evidence.
- [ ] Add timeouts, retry with jitter, circuit breaker, idempotency key, sync cursor, dead-letter handling and reconciliation report.
- [ ] Obtain approved iGOT endpoint scope, credentials, sandbox, data-sharing basis and owner. **BLOCKED-EXTERNAL**

### 4.4 Adaptive lab, dashboards and one bilingual path

- [ ] Build one bounded Official Statistics learning lab—prefer data quality, sampling, or AI-assisted statistics—with deterministic expected outputs and a learning explanation (`PS-08`).
- [ ] Do not execute arbitrary learner code on the API host. If code execution becomes necessary, use an isolated short-lived sandbox with CPU/memory/time/network limits.
- [ ] Deliver one complete English/Hindi journey: navigation, profile, questions, feedback, errors and citations.
- [ ] Keep internal IDs language-neutral and test mixed-script input, font rendering and screen-reader output.
- [ ] Have translations reviewed by a fluent human; machine translation alone is not acceptance evidence.
- [ ] Add honest learner-dashboard learning hours: derive them from real internal/provider events or show `not available`; never invent time (`PS-13`).
- [ ] Limit the demo admin dashboard to latest-distinct-learner aggregates and descriptive trends. Defer predictive workforce claims until representative data, baselines and validation exist (`PS-14`).

## 5. P2 — controlled-pilot engineering

### 5.1 Identity, privacy and authorization

- [x] Implement and live-test a local standards-based OIDC resource-server verifier against
  Keycloak, including issuer/audience/signature/time validation and fail-closed JWKS behavior.
  This is development evidence, not an approved production/government IdP. **VERIFIED**
- [ ] Integrate the approved production identity provider, browser Authorization Code + PKCE
  session/logout flow, and accountable key-rotation/outage operations. **BLOCKED-EXTERNAL/SHARED**
- [x] Implement the Lane 2 server-side matrix recognizing learner, trainer, content reviewer,
  department admin, organization admin and auditor; add issuer/sub identity binding, first-admin
  bootstrap, learner-own-record scope and deployment-tenant guards. Trainer/cohort and department
  object scope remain absent/fail-closed until authoritative relationships exist. **VERIFIED**
- [ ] Attach the Lane 2 identity/RBAC boundary to every protected product route with 401/403 and
  negative API tests; this is Lane 5-owned integration work.
- [ ] Add organization/tenant scope to every personal/content/evidence query and negative authorization tests.
- [x] Create the current subject-data inventory plus transactional internal export/deletion
  primitives, retention classification/policy guard and audited execution boundary. **VERIFIED**
- [ ] Approve lawful purpose, notice/consent where applicable, minimization, retention durations,
  correction/subject-rights HTTP workflow and processor register; automate expiry only after the
  accountable privacy/legal owner approves the policy. **BLOCKED-EXTERNAL/SHARED**
- [ ] Never expose model prompts, API keys, tokens or learner PII in client code, logs, analytics or screenshots.
- [x] Implement a bounded, versioned AES-256-GCM envelope/key-rotation primitive and explicit
  adoption contract for a future reviewed sensitive field. No current model uses it. **VERIFIED**
- [ ] Configure production TLS/storage/backup encryption and approved KMS/HSM custody, access,
  rotation, recovery and compromise procedures. **BLOCKED-EXTERNAL/OPERATIONAL**
- [x] Provide an append-only audit model/write path and atomic events for identity bootstrap,
  binding lifecycle and internal export/deletion operations. **VERIFIED**
- [ ] Integrate audited privileged route reads/writes, IdP role reconciliation, content approval
  and model decisions across their owning lanes.
- [ ] Track the staged DPDP commencement accurately: the Gazette notifications phase most Data Fiduciary duties in on 14 May 2027 (with Rule 4 on 14 November 2026). Build to the final Rules now, but do not call every duty legally operative on 29 August 2026.
- [ ] Obtain legal review of the operating entity and transitional IT Act section 43A/SPDI applicability before processing real personnel data. **BLOCKED-EXTERNAL**

### 5.2 Persistence and API contracts

- [x] Add PostgreSQL and Alembic migrations with migration-gated PostgreSQL startup while retaining
  SQLite as the documented zero-setup local-demo profile. **VERIFIED**
- [ ] Add uniqueness, foreign keys, tenant keys, version fields and indexes based on measured queries.
- [ ] Publish versioned OpenAPI and typed frontend client; add schema compatibility checks in CI.
- [ ] Add pagination, idempotency and consistent error envelopes.
- [ ] Queue document processing and AI work outside request threads; expose job state and cancellation.
- [x] Complete local PostgreSQL backup/restore plus forward/backward migration drills, including
  adversarial restore-copy cleanup and concurrent temporary-path evidence. This does not imply a
  scheduled, encrypted, offsite production DR capability. **VERIFIED**

### 5.3 Security, accessibility and reliability

- [ ] Use OWASP ASVS 5.0 as the web verification baseline and add dependency, secret, SAST and DAST scans.
- [ ] Threat-model upload parsing, prompt injection, cross-tenant retrieval, evaluator manipulation, broken access control and provider callbacks.
- [ ] Add bounded rate limits, malware/file-type validation, egress allow-listing, CSP/security headers and TLS.
- [ ] Treat applicable GIGW 3.0 `MUST` checkpoints and notified IS 17802 requirements as government acceptance controls; retain WCAG 2.1 AA evidence and use WCAG 2.2 AA as the forward-compatible engineering target.
- [ ] Test keyboard-only operation, visible focus, zoom/reflow, contrast, reduced motion, screen readers and accessible errors manually as well as automatically.
- [ ] Add structured redacted logs, request IDs, metrics, traces, health/readiness checks, alert owners and incident runbooks.
- [ ] Define and load-test measurable SLOs before claiming scale.
- [ ] For a government deployment, establish the CERT-In point of contact, synchronized clocks, six-hour report workflow for specified incidents, and an India-resident copy of required ICT logs retained for a rolling 180 days. Confirm exact ownership with MoSPI/CERT-In. **BLOCKED-EXTERNAL/LEGAL**

## 6. P3 — production authorization, not a hackathon checkbox

- [ ] Independent application-security assessment and remediation sign-off.
- [ ] STQC/GIGW assessment where required by the sponsoring organization.
- [ ] MoSPI/CBC/NSSTA competency and content governance ownership.
- [ ] iGOT production contract, credentials, security review and reconciliation owner.
- [ ] DPDP roles, notices, grievance contact, processor agreements and retention/deletion operation approved.
- [ ] Disaster-recovery exercise, capacity test, operational on-call and cost budget accepted.
- [ ] Real pilot with representative officials; accessibility, fairness, usefulness and learning-outcome results reviewed.
- [ ] Formal go-live decision by the accountable government/product/security/privacy owners.

Passing P0 makes a credible hackathon prototype. Passing P1 makes a strong demonstrator. Passing P2 makes a controlled-pilot candidate. Only P3 can support a production-ready claim.

## 7. Authoritative source register

| Claim used in this checklist | Primary source |
|---|---|
| SIH 2024 team formation and official idea-selection criteria | [Smart India Hackathon 2024 College SPOC Guidelines](https://www.sih.gov.in/letters/Guidelines-College-SPOC.pdf) |
| FRAC links positions to roles, activities and competencies | [CBC, Mission Karmayogi: A Silent Revolution](https://cbc.gov.in/sites/default/files/2026-01/Mission-Karmayogi-A-silent-revolution-May-2023.pdf) |
| Current KCM direction and iGOT competency mapping | [Capacity Building Commission: Karmayogi Competency Model](https://www.cbc.gov.in/karmayogi-competency-model-kcm) |
| TPAC reviews and approves NSSTA training calendar, syllabi, duration and method | [MoSPI Annual Report 2023–24](https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_2023-24.pdf) |
| Authenticated KB-iGOT interfaces exist; tokens/environment access are required | [KB-iGOT integration contract](https://github.com/KB-iGOT/deterministic-chatbot/blob/main/docs/INTEGRATION_CONTRACT.md) |
| DPDP Rules 2025 and enforcement material | [MeitY: Digital Personal Data Protection Rules 2025](https://www.meity.gov.in/documents/act-and-policies/digital-personal-data-protection-rules-2025-gDOxUjMtQWa) |
| Staged commencement of DPDP Act duties | [MeitY: Enforcement Timeline for the DPDP Act](https://www.meity.gov.in/static/uploads/2025/11/c56ceae6c383460ca69577428d36828b.pdf) |
| Government web/app quality and WCAG 2.1 AA baseline | [GIGW 3.0 new features](https://guidelines.india.gov.in/new-features-of-gigw-3-0/) |
| Government accessibility applicability and mandatory checkpoints | [GIGW 3.0 scope and objective](https://guidelines.india.gov.in/scope-and-objective/) |
| Current web application verification baseline | [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/) |
| Generative-AI risk lifecycle guidance | [NIST AI RMF Generative AI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) |
| Current general accessibility recommendation | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| CERT-In government ICT log direction | [CERT-In Directions under section 70B](https://cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf) |

## 8. Evidence log

| Date | Evidence | Result | Owner |
|---|---|---|---|
| 2026-08-29 | `python -m pytest backend/tests` | 42 passed | Repository audit |
| 2026-08-29 | frontend lint | passed | Repository audit |
| 2026-08-29 | route/config/client inspection | three non-DSA Quest paths blocked in browser | Repository audit |
| 2026-08-29 | 174 KB pasted planning source reconciled with repository and primary sources | useful proposals retained; unsupported claims removed | Research pass |
| 2026-09-01 | `backend/.venv/Scripts/python.exe -m pytest -q` | 237 passed; 2 pytest-cache permission warnings | Lane 2 Packages A–N closure |
| 2026-09-01 | PostgreSQL 16 Alembic forward/backward/startup drills | baseline and follow-up migrations, stale-revision refusal and empty/head startup verified | Lane 2 + reciprocal review |
| 2026-09-01 | Local Keycloak 26.7.2 OIDC verification and RBAC/bootstrap negatives | verifier/binding/policy foundation accepted; product routes explicitly still unprotected | Lane 2 + reciprocal review |
| 2026-09-01 | Concurrent PostgreSQL backup/restore and adversarial regression contract | accepted; no container temp residue in recorded live drill | Lane 2 + reciprocal review |
| 2026-09-01 | Full backend gate after immutable Package P and reviewed Package Q | 272 passed; 2 pytest-cache permission warnings; Package P review findings remain open | Lane 2 closure pass |
| 2026-09-01 | Live PostgreSQL 4-worker concurrency drill (pre-fix, Codex-run) | `deleted_sets=[set(), set(), {'1','2','3'}, set()]`; 3 of 11 expired rows deleted, 8 abandoned; 2 young rows correctly untouched | Confirmed real defect: unlocked candidate SELECT, reproduced by Codex; not overwritten by the fix below |
| 2026-09-01 | Full backend gate after Package P/S (atomic PostgreSQL row-claiming fix) | 339 passed; 2 pytest-cache permission warnings; 0 failures | Claude Code, live-tested, awaiting Codex final review |
| 2026-09-01 | Live PostgreSQL 4-worker concurrency drill (post-fix, same scenario) | 11 expired + 2 young rows; per-worker deletions pairwise-disjoint; union = all 11 expired IDs; deleted-count sum = 11; durable audit deleted-count sum = 11; young rows untouched; clean `0/0` final rerun, zero misleading audit events | Claude Code; exact opposite result to the pre-fix row above under the identical scenario |
| 2026-09-01 | Full independent Lane 2 audit (security/rbac.py, security/data_rights.py, security/identity_bootstrap.py, models/identity.py, security/audit.py, migrations re-read fresh) plus full backend gate | 341 passed, 0 failures; exact warning count/type varies by run (2 SQLite datetime-adapter deprecations on this run; Codex separately observed 4, including 2 `.pytest_cache` warnings, on a concurrent run — both accurate for their own run, not a code discrepancy) | Claude Code (Codex ran out of session credits mid-review); fixed `delete_subject_data()`'s stale pre-delete-snapshot `deleted_counts` (now real DELETE rowcounts, live-verified against PostgreSQL) and `BoundPrincipal.audit_actor`'s non-injective `\|`-joined encoding (now canonical JSON, matching the identical fix already applied to `identity_bootstrap.py`) |

Append future entries; never overwrite failed evidence with a later success.
