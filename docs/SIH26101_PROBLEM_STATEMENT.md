# SIH26101 problem-statement source and requirement contract

Captured: 29 August 2026

Source: user-provided paste of the SIH problem-statement details

Attachment SHA-256: `A745A905D42A03D363875C844418D22189F00B15E8C733B7EC6453172D36D561`

This file is the repository's canonical statement of the requested product scope. It preserves the supplied content as a structured requirement contract so it remains available to human and coding agents. The team must still archive the official SIH 2026 portal/PDF evidence through the college SPOC; this capture is authoritative for the user’s requested build scope but is not, by itself, proof of current competition rules or partner API access.

## Problem metadata

| Field | Supplied value |
|---|---|
| Problem Statement ID | `26101` |
| Organization | Ministry of Statistics and Programme Implementation (MoSPI) |
| Department | Data Informatics & Innovation Division (DIID) |
| Category | Software |
| Theme | Smart Education |
| Dataset links | `nssta.gov.in`, `mospi.gov.in` |
| YouTube/contact | No value supplied |

## Supplied title

> Develop an AI enabled learning platform that identifies competency gaps, recommends personalized training through integration with the iGOT Karmayogi ecosystem, and capable of generating Quizzes and Multiple choice questions (MCQs) from uploaded learning materials to strengthen capacity building in India's Official Statistical System.

## Product intent

Build an AI-enabled Skill Intelligence and Learning Platform for officials across India’s Official Statistical System. It must construct comprehensive competency profiles, assess gaps against defined frameworks, recommend personalized learning through iGOT Karmayogi and NSSTA/TPAC-informed programmes, support continuous/adaptive learning, generate assessments from uploaded materials, and provide workforce insight through learner and administrator dashboards.

The supplied statement names AI/ML, NLP, LLMs, semantic search and competency mapping as possible techniques. These are means, not permission to fabricate accuracy or use AI where deterministic rules are safer.

## Explicit competency scope

The platform must be capable of representing these four categories and named examples:

| Category | Named competencies |
|---|---|
| Statistical | Survey Design, Sampling, National Accounts, Price Statistics, Labour Statistics, Agricultural Statistics, Industrial Statistics, SDG Indicators, Metadata Standards, Data Quality Frameworks |
| Technical | Python, R, SQL, Stata, SPSS, SAS, GIS, Data Visualization, AI/ML, Cloud Computing, APIs, Open Data |
| Digital Governance | Cybersecurity, Data Privacy, Digital Signatures, Government Cloud, Digital Public Infrastructure |
| Behavioural and Managerial | Leadership, Communication, Project Management, Ethics, Decision Making, Change Management |

The current repository’s four curricula/34 competencies do not yet cover this complete list and are not an MoSPI-approved framework.

## Numbered requirement contract

These identifiers must be used in issues, PRs, acceptance tests and the final evidence matrix.

| ID | Requirement extracted from the supplied statement | Demo interpretation | Production/pilot boundary | Primary lane |
|---|---|---|---|---|
| **PS-01** | Build a comprehensive official profile from designation, department, role, assignment, qualifications, experience and prior training | One complete synthetic MoSPI persona | Real personnel data needs approved identity/privacy basis | Lane 2 |
| **PS-02** | Represent predefined Official Statistics competency frameworks across statistical, technical, digital-governance and behavioural/managerial domains | Versioned prototype taxonomy with source/status labels | Authorized MoSPI/CBC/NSSTA validation | Lane 3 |
| **PS-03** | Assess current competencies and identify knowledge/skill gaps | Transparent diagnostic plus evidence-aware gap | Psychometric/domain validation and appeal process | Lane 3 |
| **PS-04** | Personalize pathways using level, history, department priorities, future role, emerging technology and career progression | Deterministic explainable scoring over available synthetic inputs | Outcome-based calibration after a real pilot | Lane 3 |
| **PS-05** | Integrate iGOT APIs for catalogue, recommendations, enrolment/completion status and automatic competency updates | Contract-tested, visibly simulated provider fixture | Live functions require authorized endpoints, credentials and data contract | Lane 5 |
| **PS-06** | Provide an AI-powered virtual assistant for learner support | Bounded cited assistant over approved content or a clearly scoped help flow | Safety evaluation, privacy controls, escalation and monitoring | Lane 4 |
| **PS-07** | Provide adaptive assessments, interactive modules and real-time/personalized feedback | One adaptive assessment loop with deterministic state changes | Validated item bank, reviewer workflow and reliable event processing | Lanes 3–4 |
| **PS-08** | Provide virtual labs for AI, Data Science, Cloud, Cybersecurity and Automation | One bounded Official Statistics-relevant CPI/sampling/data-quality lab | Additional isolated labs; no arbitrary code on the API host | Lane 3 |
| **PS-09** | Provide multilingual learning resources | One end-to-end English/Hindi journey | Human-reviewed translations and broader language operations | Lane 1 |
| **PS-10** | Continuously monitor progress and dynamically update recommendations | Practice result visibly changes evidence/pathway using documented rules | Event-driven/reconciled updates with rollback and audit | Lanes 3 and 5 |
| **PS-11** | Generate MCQs/quizzes from documents, presentations and videos | Bounded TXT/MD/PDF/DOCX plus one PPTX or timecoded transcript path | Scalable media jobs, malware scanning, storage/retention and review | Lane 4 |
| **PS-12** | Give instant evaluation, correct-answer explanations and personalized feedback; support trainer assessment creation | One cited quiz with explanation/feedback and draft/review status | Approved reviewer roles, item lifecycle, gold-set quality evidence | Lane 4 |
| **PS-13** | Learner dashboard: levels, gaps, paths, learning hours and progress | Professional dashboard with honest missing-data states | Provider/event-derived hours and accessible multilingual operation | Lane 1 |
| **PS-14** | Admin dashboard: workforce competency, training effectiveness/distribution, emerging needs and predictive analytics | Latest-distinct-learner aggregates and descriptive trends on synthetic data | Prediction only after adequate representative data and validation | Lane 5 |
| **PS-15** | Secure, scalable, cloud-ready and interoperable web platform using standard APIs | Versioned API, CI build, bounded resources, deployable demo | Authorized security audit, tested SLOs, compliant hosting/DR/operations | Lanes 2, 5 and 6 |
| **PS-16** | RBAC, SSO, secure data exchange and government cybersecurity/privacy alignment | Truthfully show these as incomplete unless implemented and tested | Government-approved IdP, tenant/object authorization and legal/security sign-off | Lanes 2 and 6 |
| **PS-17** | Recommend both iGOT course modules and NSSTA TPAC-recommended programmes | Sourced catalogue fixtures/links with `SIMULATED` or `CATALOGUE` status | Live synchronized records need authorized provider contracts | Lane 5 |
| **PS-18** | Improve competency, iGOT utilization and workforce readiness | Demonstrate a closed synthetic before/after loop | Impact claims require representative pilot evidence | Lane 6 verifies |

Where two lanes are named, the first owns product behavior and the second owns its boundary or acceptance evidence. A single issue still has one owner.

## Mandatory end-to-end demonstration

The primary demo must prove this traceable loop using synthetic data:

1. Create/select a role-aware learner profile.
2. Show the versioned role target and its provisional/validated status.
3. Complete a diagnostic or load demonstrated evidence.
4. Explain one gap using target, evidence, formula and uncertainty.
5. Generate an ordered, personalized pathway.
6. Show internal, iGOT and NSSTA/TPAC options with truthful integration status.
7. Generate a cited assessment from approved material and show explanation/feedback.
8. Complete one adaptive practice/lab action.
9. Show updated learner progress and privacy-safe administrator aggregate.
10. Show the simulated/live integration boundary and readiness roadmap.

Quest mode may support step 8, but it is not a substitute for the professional workflow.

## Truth and safety constraints

- Never label the prototype taxonomy, target levels or scoring formula “official” without authorized evidence.
- Never present fixtures, catalogue links or environment variables as live iGOT/NSSTA integration.
- Never claim enrolment, completion, SSO, competency writeback or predictive accuracy until exercised and measured in the authorized environment.
- Treat uploaded documents, presentations, transcripts and learner answers as untrusted input.
- Do not use real official/employee personal data in the hackathon demo.
- Generated assessment items are drafts until automated checks and an authorized human review pass.
- “Secure,” “scalable,” “compliant” and “production ready” require evidence defined in the master checklist; architecture intent is not proof.

## Known unknowns requiring external confirmation

- Current SIH 2026 team, mentor, deadline and submission-format rules.
- The official downloadable problem-statement artifact and any clarifications from MoSPI/DIID.
- Approved MoSPI role/competency framework and target owners.
- iGOT partner onboarding, endpoint scope, sandbox, credentials and permitted data exchange.
- Current NSSTA/TPAC structured catalogue/API availability.
- Government IdP/SSO, hosting, security, accessibility, privacy and operational acceptance owners.
