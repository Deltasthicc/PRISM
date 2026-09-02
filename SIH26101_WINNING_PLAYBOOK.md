# SIH26101 winning playbook

Last revised: 29 August 2026

Status: evidence-backed strategy, not a promise of winning

Execution ledger: `SIH26101_MASTER_CHECKLIST.md`

Team operating model: `SIH26101_TEAM_ORCHESTRATION.md`

Canonical build scope: `docs/SIH26101_PROBLEM_STATEMENT.md` (`PS-01`…`PS-18`)

## 1. The winning thesis

Do not pitch “another learning management system” or “an AI quiz generator.” Pitch a **trustworthy competency intelligence layer for a MoSPI pilot inside India’s wider Official Statistical System**:

> It converts a versioned role target and multiple kinds of learner evidence into an explainable gap; builds an ordered learning path; recommends internal, iGOT-compatible and NSSTA/TPAC-informed options with honest source status; creates cited questions from approved material; and shows whether competency evidence improves after practice.

The differentiator is the closed, auditable loop:

`role/activity target → evidence → gap → recommendation → learning/practice → reassessment → updated evidence → aggregate decision insight`

Every arrow must be visible in the demo. “AI” is used where it helps; deterministic rules, provenance and human review make it governable.

## 2. The non-negotiable truth boundary

### Say this

- “This is a working hackathon prototype with a controlled-pilot hardening plan.”
- “The role matrix and level anchors are a versioned prototype derived from public MoSPI/CBC/NSSTA sources; MoSPI validation is pending.”
- “The current provider path is a contract-tested simulator/catalogue fallback. Live iGOT sync needs approved endpoints, credentials and partner authorization.”
- “Generated questions show their supporting source; publication into scored assessment requires reviewer approval in the target design.”
- “Quest mode is an optional engagement view; the professional workspace is the primary government-facing experience.” Not just a separate route: the default landing uses a plain, non-game visual identity, and Quest's pixel-art/dungeon skin is confined to its own opt-in routes -- a dungeon-themed screen on startup would read as off-putting to a government-official audience.

### Never say this unless runtime evidence changes

- “Government approved,” “official FRAC scoring,” “production ready,” “DPDP compliant,” or “GIGW certified.”
- “Live iGOT integration,” “automatic enrolment/completion sync,” “SSO,” or “bidirectional writeback.”
- “All four domains work end-to-end.”
- “RAG” while the whole document is merely placed in one prompt.
- “Role-aware” while only `experience_level` changes targets.
- “Exact substring” without clarifying that the present validator normalizes whitespace and case.
- Any invented course ID, schedule, user count, model accuracy, latency, availability or impact statistic.

Honest boundaries are not a weakness here: interoperability, public-sector trust and auditability are part of the product.

## 3. Compliance gate before engineering

The delivery plan now assigns six people to six disjoint lanes. The latest official senior-edition rules independently retrievable were SIH 2024, not 2026; those rules required six students including the leader, all from the same college, and at least one female member. Six work assignments therefore solve the headcount-planning issue, but they do not prove same-college, gender-composition or 2026 registration compliance.

Before relying on this playbook:

1. Ask the college SPOC to confirm the 2026 team rule and deadline inside the official portal.
2. Save a screenshot/PDF, date and URL in the evidence ledger.
3. Record all six registered students, leader, college and required gender composition; do not substitute a mentor for a student seat.
4. Confirm the official problem statement/deck template. A reproducible community snapshot reports 20 September 2026, but that date is provisional until the official portal/SPOC confirms it.

## 4. What to demonstrate

Use a single MoSPI pilot persona, not four shallow domains. A good demo persona is an official whose public role context and training needs can be cited. Do not claim the persona represents every member of India’s decentralized Official Statistical System.

### Three-minute judge path

| Time | Screen/action | Proof delivered |
|---:|---|---|
| 0:00–0:20 | Open professional dashboard; state the official’s role and task | problem clarity; public-sector fit |
| 0:20–0:45 | Show versioned target and evidence sources | FRAC/KCM alignment without claiming endorsement |
| 0:45–1:10 | Run or reveal diagnostic; open one gap’s explanation | explainability, uncertainty and why this gap exists |
| 1:10–1:35 | Show ordered pathway and provider status badges | recommendations, prerequisites, honest iGOT boundary |
| 1:35–2:05 | Upload an approved source; generate one quiz item; open its cited passage | bounded ingestion, grounded generation, provenance |
| 2:05–2:30 | Complete one short statistics practice/lab or optional Quest room | engagement plus domain relevance |
| 2:30–2:45 | Reassess and show changed evidence/admin aggregate | closed learning loop, measurable outcome |
| 2:45–3:00 | Show live/simulated integration toggle and readiness roadmap | interoperability and credible progression |

Maintain 90-second and five-minute variants. Use all six deliberately: presenter, product navigator, domain defender, AI/architecture defender, security/integration defender, and system operator/timekeeper. Give every role a backup before rehearsal.

### The four strongest judge moments

1. **Trace one decision:** click from a gap to raw evidence, target source, formula version and recommendation reason.
2. **Catch an unsafe item:** show automatic rejection/abstention or reviewer hold when evidence is insufficient.
3. **Change state visibly:** one practice result updates the learner view and aggregate admin view.
4. **Prove the boundary:** switch between `SIMULATED` and `LIVE-NOT-CONFIGURED`; show that the system never fabricates enrolment.

## 5. Score against the latest official criteria we could verify

The SIH 2024 official guideline lists these criteria without weights. Treat them as a rehearsal checklist, not confirmed 2026 scoring.

| Criterion | Evidence the demo must show |
|---|---|
| Novelty | evidence-driven closed loop; cited question generation; auditable integration boundary |
| Complexity | role/competency graph, multiple evidence types, grounded generation and contract adapters—not a collection of unrelated features |
| Clarity/detail | one persona, one problem, one traceable journey, one architecture diagram |
| Feasibility | local/offline fixture, bounded files, deterministic fallback, documented setup and five successful resets |
| Practicability | professional UX, human review, provider reconciliation and realistic data ownership |
| Sustainability | modular monolith, open interfaces, operating owner, cost envelope and staged rollout |
| Scale of impact | MoSPI pilot that can extend across the decentralized Official Statistical System; no unsupported headcount claims |
| User experience | fast professional path, Hindi path, accessible forms/errors, optional Quest practice |
| Future work | controlled pilot → partner integration → production authorization with measurable gates |

## 6. Product and architecture choice

Keep a **modular monolith** for the hackathon:

- Next.js professional frontend with optional Quest surface.
- One FastAPI application with explicit modules for identity/profile, competency, evidence, content, recommendations, integrations and admin.
- PostgreSQL + migrations for a controlled pilot; SQLite only as a local demo profile.
- One background worker for parsing/embedding/generation jobs.
- `pgvector` or a replaceable vector adapter only when real retrieval is implemented.
- Typed provider ports with a deterministic simulator and an authenticated live adapter behind the same contract.
- Object storage for source versions; immutable hashes and locators in the database.

Do not spend hackathon time splitting this into microservices, Kafka, Kubernetes or dozens of speculative tables. Those add failure modes without improving the demo loop.

### Contract boundaries

| Boundary | Required contract |
|---|---|
| Frontend ↔ API | versioned OpenAPI, generated types, error envelope, auth expectations |
| Competency ↔ evidence | immutable evidence type/source/time; versioned target and scoring policy |
| Content ↔ AI | source version, chunk locator, access scope, prompt/model/retrieval version |
| Recommendation ↔ provider | provider status, source record ID, score reasons, last sync, idempotency |
| Learner ↔ admin | tenant-safe aggregates; small-group/PII policy; audit event |

## 7. What to build first

### Sprint A — truth and repair

- Confirm eligibility, deadline and official prompt through the SPOC.
- Fix dynamic dungeon routing, UUID flow and non-DSA filtering.
- Add the cross-domain browser smoke and clean CI build.
- Correct admin distinct-learner counting and misleading leaderboard copy.
- Freeze the demo persona, evidence sources and exact click path.

### Sprint B — one coherent Official Statistics loop

- Professional learner/admin shell -- its own plain, non-game visual identity as the default landing, separate from Quest mode's pixel-art skin, which stays opt-in only.
- Versioned prototype role target with competency-specific behavioural anchors.
- Evidence-aware gap explanation and pathway.
- One deterministic lab.
- One full Hindi journey.
- Explicit simulated provider status and contract tests.

### Sprint C — trust layer

- Real chunk/retrieve/cite pipeline, not context stuffing.
- Item state/reviewer queue and abstention.
- Prompt-injection and cross-tenant retrieval tests.
- Auth/RBAC/tenant minimum for a controlled pilot.
- Accessibility and security acceptance evidence.

### Sprint D — release and pitch

- Clean deployment, reset script, offline fallback and seeded fixture.
- Full regression, accessibility/manual keyboard pass, dependency/secret scan and load smoke.
- Pitch deck mapped to criteria and every claim tagged `LIVE`, `SIMULATED`, `MEASURED`, `PROPOSED` or `BLOCKED`.
- Five consecutive rehearsals with a different teammate acting as an adversarial judge.

Use relative sprints until the 2026 submission deadline is officially confirmed. Do not plan against the community-reported 20 September date as if it were guaranteed.

## 8. Judge defence sheet

### “Is this really integrated with iGOT?”

“Not in this environment. We implemented the provider contract and a deterministic simulator so the entire workflow is testable without inventing records. Public KB-iGOT engineering material confirms authenticated interfaces, but production use requires approved endpoint scope, user/gateway tokens and partner authorization. The same adapter can be switched only after those gates pass.”

### “Is this FRAC/KCM official?”

“The data model follows the official role → activity → competency approach. Our MoSPI pilot taxonomy and L1–L5 behavioural anchors are versioned prototypes derived from public role and training sources, pending authorized validation. We do not present them as an official government dictionary.”

### “How do you stop hallucinated questions?”

“The current prototype bounds uploads and rejects unsupported source excerpts after normalization. The target trust path stores source versions and chunks, retrieves access-filtered evidence, requires page/section citations, abstains on weak evidence, runs item checks and routes scored items through human review. We report measured gold-set performance, not a claimed zero-hallucination rate.”

### “Why use AI at all?”

“AI helps draft questions, interpret evidence and retrieve relevant learning material. Deterministic rules own authorization, target selection, status, provenance and workflow. Human reviewers own publication and contested decisions.”

### “Are you production ready?”

“This is a verified prototype. We have separate gates for controlled pilot and production authorization: identity/RBAC/tenancy, migrations, privacy/legal review, security assessment, accessibility validation, partner contracts, backup/restore, load evidence and accountable owner sign-off.”

### “How will you measure success?”

Use a small outcome tree:

- Product: pathway start/completion, time to relevant recommendation, reviewer turnaround.
- Learning: pre/post competency evidence with confidence and item-quality controls.
- Trust: citation correctness, abstention precision, override rate, authorization failures and accessibility defects.
- Operations: job failure/retry, reconciliation mismatch, latency and cost per completed learning loop.

Do not use clicks, XP or quiz count as proof of competency improvement.

## 9. Failure modes to rehearse

- API unavailable, AI provider unavailable and no network.
- Empty, corrupt, encrypted, oversized or hostile uploaded file.
- Prompt injection inside a document and inside a learner answer.
- Duplicate submit, refresh during mutation, stale browser state and reset.
- Learner tries another learner’s URL; admin crosses tenant boundary.
- Retrieved evidence is missing, contradictory or wrong language.
- Provider times out or returns the same completion event twice.
- Screen reader, keyboard-only, 200% zoom and reduced-motion use.
- A judge asks for a real iGOT enrolment or official approval proof.

Every failure needs a graceful screen, a log/request ID, a recovery action and an honest explanation.

## 10. Stop list

- Do not rebuild everything from the pasted 60-table proposal before the vertical slice works.
- Do not enable the separate embedding service merely because it sounds more advanced; it is currently DSA-bound and must pass the same domain, security and reliability gates first.
- Do not add a generic unrestricted code runner.
- Do not scrape private/provider data and call it integration.
- Do not train an IRT/BKT model without sufficient real response data and psychometric review.
- Do not optimize vanity visuals before eligibility, broken routing, CI and the core MoSPI loop.
- Do not let six parallel branches change shared contracts independently.

## 11. Source basis

- [SIH 2024 College SPOC Guidelines](https://www.sih.gov.in/letters/Guidelines-College-SPOC.pdf) — latest official senior team and selection criteria independently retrieved; current 2026 confirmation still required.
- [Press Information Bureau: Mission Karmayogi](https://www.pib.gov.in/Pressreleaseshare.aspx?PRID=1650633&lang=2&reg=48) and [DoPT FRAC](https://trgdiv.dopt.gov.in/igotmk/FRAC.html) — official role/activity/competency basis.
- [CBC Karmayogi Competency Model](https://www.cbc.gov.in/karmayogi-competency-model-kcm) — current competency direction and iGOT mapping.
- [MoSPI Annual Report 2023–24](https://www.mospi.gov.in/sites/default/files/publication_reports/AnnualReport_2023-24.pdf) and [NSSTA offerings](https://nssta.gov.in/offerings) — TPAC/NSSTA scope.
- [KB-iGOT integration contract](https://github.com/KB-iGOT/deterministic-chatbot/blob/main/docs/INTEGRATION_CONTRACT.md) — authenticated integration evidence; not an open partner entitlement.
- [GIGW 3.0](https://guidelines.india.gov.in/new-features-of-gigw-3-0/), [OWASP ASVS 5.0](https://owasp.org/www-project-application-security-verification-standard/), [NIST AI RMF GenAI Profile](https://www.nist.gov/publications/artificial-intelligence-risk-management-framework-generative-artificial-intelligence) and [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) — quality, security, AI-risk and accessibility engineering baselines.
