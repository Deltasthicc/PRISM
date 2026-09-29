# SIH26075 transition analysis

**Status:** decision support and implementation gap analysis

**Verified against:** the live SIH 2026 problem-statement page on 29 September 2026

**Recommended target:** SIH26075 — CAPACITY CONNECT

**Category/theme:** Software / Smart Education

**Owner:** Ministry of Earth Sciences (MoES), India Meteorological Department (IMD)
**Current portal count at verification:** 238/500; deadline 30 September 2026

This document is current planning guidance. It does not rewrite historical evidence under
`docs/archive/**` or the Lane 2 activity record.

## Decision

Move PRISM to SIH26075. It is the closest open problem statement to the product that already
exists. The competency engine, assessments, learning pathways, content ingestion, trainer review,
course enrolment, analytics, multilingual UI, and identity/RBAC foundations are reusable. The
transition is nevertheless more than a rebrand: SIH26075 explicitly requires several role and LMS
workflows that are not implemented yet.

The live SIH page showed SIH26101 at 500/500. Older community mirrors contain stale submission
counts and must not be used to decide availability.

## Exact SIH26075 requirement contract

The official prose has been separated into testable obligations. These identifiers should be used
in the replacement master checklist.

| ID | Required outcome |
|---|---|
| CC-01 | Secure signup and login with Trainee, Trainer, and Admin roles. |
| CC-02 | Trainee professional profiles covering qualifications, work experience, interests, skills, and certificates. |
| CC-03 | Trainees can discover and enrol in courses and access learning resources. |
| CC-04 | Trainees can attempt subject-wise MCQ assessments. |
| CC-05 | Trainees can provide feedback on courses and training content. |
| CC-06 | Trainers can manage their own professional profiles. |
| CC-07 | Trainers can create questionnaires with deadlines. |
| CC-08 | Trainers can monitor assigned trainees' participation and performance. |
| CC-09 | Trainers can upload recorded lectures, presentations, and study materials to a library accessible to trainees. |
| CC-10 | Admins can approve users and manage roles. |
| CC-11 | Admin dashboards monitor courses, enrolments, certifications, assessments, and participation. |
| CC-12 | Admins can publish notifications, announcements, achievements, and newly added learning content on the homepage. |
| CC-13 | Competency mapping can identify suitable trainers for subjects. |
| CC-14 | The experience is scalable, secure, user-friendly, and accessible across devices. |
| CC-15 | The portal centralizes organizational learning and knowledge sharing. |

## Honest PRISM fit map

### Substantial reusable implementation

- OIDC token validation, role/permission primitives, audit records, and a PostgreSQL-capable data
  layer exist. The current public demo can bypass authentication, so this is a foundation rather
  than proof of a production login deployment.
- Learner profiles already store designation, department, job role, assignment, qualifications,
  years of experience, previous training, career goal, language, and target domains.
- Course enrolment and completion have a persisted lifecycle.
- Subject MCQs, source-cited question banks, generated quizzes, and adaptive diagnostics exist.
- Uploaded text, PDF, DOCX, PPTX, audio, video, and images can feed the content/quiz pipeline,
  including OCR where configured.
- Trainers can review and edit generated quiz items before approval.
- Live assessment sessions and learner/admin analytics provide useful building blocks.
- Competency profiles, gap calculations, learning pathways, multilingual UI, and responsive web
  pages are reusable.

### Partial matches that must not be overstated

- A numeric `years_experience` value is not a structured work-history section.
- Content ingestion for quiz generation is not yet a browsable trainer resource library.
- Quiz review is not a complete author-questionnaire-and-deadline workflow.
- Learner gap mapping is not trainer-to-subject suitability matching.
- General analytics do not prove every SIH26075 dashboard metric, especially certifications.
- Backend RBAC primitives are not three complete, role-specific browser portals.

### Confirmed missing SIH26075 workflows

- Interests, structured employment history, and certificate storage/verification in trainee profiles.
- Admin approval of new users and a complete role-management interface.
- Course and content feedback.
- Trainer profiles and explicit subject expertise.
- Trainer-authored questionnaires with due dates.
- Server-side trainer/cohort assignments and scoped monitoring of trainee participation/performance.
- A trainee-facing trainer library for lectures, presentations, and study resources.
- Certification issuance and tracking.
- Homepage notifications, announcements, achievements, and new-content publishing.
- Explainable trainer matching by subject competency.
- Evidence for the intended production hosting, load, backup, accessibility, and security posture.

The practical conclusion is that roughly half of the technical foundation is reusable, while fewer
than half of SIH26075's exact end-user workflows are complete. Percentages should be treated only as
planning estimates, not as measured compliance.

## Ranked alternatives

The ranking weighs direct requirement overlap, reusable implementation, domain-specific rebuild,
category fit, and dependence on unavailable external data. Counts below are the live official-page
values observed on 29 September 2026 and will change as teams submit.

**Independent re-verification (Claude, later same day, 29 September 2026):** requested by
Shashwat directly ("check again fully and properly"), not a routine pass. Re-fetched the complete
live portal HTML (not a community mirror) and parsed all 240 listed problem statements with a
custom extractor, since the page's nested modal markup breaks `pandas.read_html()`. Cross-checked
every entry against this ranking three ways: (1) all 12 `Smart Education`-theme entries read in
full, (2) all 15 `Miscellaneous`-theme entries read in full (the theme that already produced two
ranked alternatives here), (3) a 23-term keyword sweep — training, learning, competency, skill,
LMS, capacity building, certification, curriculum, workforce, upskill, vocational, etc. — run
against title and description text across all 240 records, yielding 136 raw hits, individually
read. Result: no problem statement outside the nine already ranked below matches PRISM's
LMS/competency shape. Live counts had moved slightly upward for every open PS in the table
(consistent with real submission activity ahead of the 30 September deadline) but the fit
assessment and ranking order are unchanged: SIH26075 → 242/500, SIH26134 → 268/500,
SIH26135 → 234/500, SIH26087 → 46/500, SIH26097 → 102/500, SIH26239 → 170/500,
SIH26063 → 84/500, SIH26140 → 128/500, SIH26041 → 111/500. SIH26101 confirmed still 500/500.
SIH26075 remains the only alternative rated above a 6/10 fit; every other open PS still requires a
near-total rebuild of core product surfaces PRISM does not have. **Conclusion: SIH26075 stands.**

| Rank | PS | Live count | Fit / migration ease | Assessment |
|---:|---|---:|---|---|
| 1 | **SIH26075 — CAPACITY CONNECT** | 238/500 | **9/10 fit; moderate migration** | Direct match for LMS, assessments, roles, competency development, profiles, content, and analytics. Clear product gaps remain, but the core is reusable. |
| 2 | **SIH26134 — skill programmes aligned to industry demand** | 262/500 | **6.5/10; major migration** | Reuses skill mapping, pathways, assessments, and dashboards. Requires labour-market ingestion, employer input, district planning, and outcome alignment not present today. |
| 3 | **SIH26135 — skilling outcomes and impact tracking** | 230/500 | **5.5/10; major migration** | Reuses enrolments and analytics. Requires longitudinal employment/wage/retention follow-up, consent, employer validation, and impact methodology. |
| 4 | **SIH26087 — AI/LMS cooperative capacity ecosystem** | 45/500 | **6/10 concept fit; very high migration risk** | LMS overlap is real, but it is a Hardware-category statement with a much broader ERP, employment, logistics, offline, and biometric scope. Poor fit for this software-first team. |
| 5 | **SIH26097 — multilingual livelihood and NSQF assistant** | 98/500 | **5.5/10; major migration** | Reuses multilingual profiles, skill gaps, and recommendations. Needs voice/IVR or WhatsApp channels, local job intelligence, NSQF mapping, offline access, and a different beneficiary model. |
| 6 | **SIH26239 — scholarship and fellowship management system** | 165/500 | **5/10 component overlap; major product migration** | Reuses login, profiles, document/OCR ingestion, approvals, and dashboards. Its core is eligibility, scrutiny, selection, deficiency, and resubmission—not learning or competency development. |
| 7 | **SIH26063 — polar science outreach and knowledge repository** | 82/500 | **4.5/10; major migration** | Reuses ingestion, OCR, RAG, and multilingual delivery, but discards most competency/LMS value and needs a new scientific media/outreach product. |
| 8 | **SIH26140 — quantum algorithm learning platform** | 126/500 | **4/10; near-rebuild** | Reuses assessment, assistant, editor, and pathway ideas. Requires quantum circuit authoring, simulators, visualization, and quantum-specific content/toolchains. |
| 9 | **SIH26041 — AR vocational safety training** | 107/500 | **3/10; near-rebuild** | Training/certification concepts overlap, but the required mobile AR, offline delivery, safety simulations, language/domain content, and QR certification substantially replace the present product. |

SIH26044 would have been a strong conceptual alternative for academia–industry skill mapping, but
the live portal showed 500/500, so it is not an actionable fallback.

## Recommended transition sequence

1. Freeze SIH26101-specific claims as historical evidence; do not erase audit history.
2. Replace the current canonical problem-statement and checklist documents with SIH26075 versions.
3. Reframe the demo around Trainee, Trainer, and Admin journeys before adding speculative AI.
4. Model courses, resources, trainer expertise, assignments, certificates, feedback, and homepage
   posts as first-class persisted entities.
5. Wire permissions to those entities and prove object-scope isolation with negative tests.
6. Add the missing role pages and one connected golden path.
7. Adapt demo content to MoES/IMD training without presenting a made-up taxonomy as official.
8. Run a requirement-by-requirement evidence audit before the final submission.

## Truth and terminology rules

- Use **MoES / India Meteorological Department** as the owning organization/department.
- The public official listing does not expose a problem-creator name. Do not publish “Sarim Moin”
  as verified unless the authenticated portal displays it to the team.
- Treat “CAPACITY CONNECT” as the official challenge name and “PRISM Capacity Connect” as the
  proposed solution name.
- Say “configurable competency taxonomy” until MoES/IMD supplies an approved framework.
- Say “prototype demonstrates” only for flows that run end to end; use “will provide” for planned
  SIH26075 features.
- Do not claim production readiness, compliance, official integration, scale, or model quality
  from local tests.
- Do not invent a YouTube link, dataset, official course catalogue, or MoES endorsement.

## Sources used for this decision

- [Official SIH 2026 problem-statement portal](https://sih.gov.in/sih2026PS) — canonical metadata,
  wording, current capacities, and deadline.
- [Rajkumar Porandla SIH 2026 structured mirror](https://github.com/Rajkumar-Porandla/SIH-2026-Problem-Statements)
  — full-description search across 231 entries; treated as a convenience snapshot, not authority.
- [Sea Deep SIH 2026 240-entry mirror](https://github.com/sea-deep/sih2026-problem-statements)
  — cross-check of the later catalogue size; live official counts take precedence.
