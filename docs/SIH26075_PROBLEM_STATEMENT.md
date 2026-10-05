# SIH26075 problem-statement source and requirement contract

Captured: 29 September 2026

Source: verbatim record supplied by Shashwat and independently cross-checked against the live
[official SIH 2026 problem-statement portal](https://sih.gov.in/sih2026PS) on 29 September 2026.
The title, description, organization, department, category, theme, capacity, and deadline below
matched the live HTML. This file is the repository's canonical statement of the current requested
product scope, superseding `docs/archive/SIH26101_PROBLEM_STATEMENT.md`.

## Problem metadata

| Field | Value |
|---|---|
| Problem Statement ID | `SIH26075` |
| Organization | Ministry of Earth Sciences (MoES) |
| Department | India Meteorological Department (IMD) |
| Category | Software |
| Theme | Smart Education |
| Dataset links | None supplied |
| YouTube/contact | None supplied |
| Ideas submitted (as of capture) | 238/500 on 29 September 2026; mutable, so re-check before submission |
| Submission deadline shown | 30 September 2026 |

## Supplied title

> Participants are invited to design and develop **CAPACITY CONNECT — A Digital Capacity Building
> and Learning Management Portal** to support organizational training, competency development, and
> knowledge sharing through a centralized web-based platform.

## Supplied description (verbatim)

> The solution should include secure signup and login functionality with three user roles: Trainee,
> Trainer, and Admin. Trainees should be able to create professional profiles with qualifications,
> work experience, interests, skills, and certificates, enroll in courses, access learning
> resources, attempt subject-wise MCQ assessments, and provide feedback on courses and training
> content. Trainers should be able to manage their profiles, create questionnaires with deadlines,
> monitor trainee participation and performance, and upload recorded lectures, presentations, and
> study materials in a trainer library accessible to trainees. The Admin module should provide user
> approval and role management features along with dashboards for monitoring courses, enrollments,
> certifications, assessments, and participation statistics. Admins should also be able to publish
> notifications, announcements, achievements, and newly added learning content on the homepage. The
> platform should support competency mapping for identifying suitable trainers for various subjects
> and should be scalable, secure, user-friendly, and accessible across devices to promote efficient
> learning and organizational capacity building.

## Product intent

Build a general-purpose organizational Learning Management Portal — not sector-specific to Official
Statistics the way SIH26101 was — with three distinct role experiences (Trainee, Trainer, Admin),
real course enrollment and subject-wise MCQ assessment, trainer-authored questionnaires with
deadlines, a trainer-owned content library, admin user-approval and role management, cross-cutting
dashboards (courses, enrollments, certifications, assessments, participation), a homepage
announcements/notifications feed, and competency mapping used specifically to match trainers to the
subjects they're qualified to teach.

## Explicit requirement contract

Numbered for use in issues/PRs/the evidence log, same convention as the superseded SIH26101 doc.
The "Current PRISM state" column was first written from an independent code audit on
2026-09-29 (against `main` at `cec89f6`) and rewritten on 2026-10-05 after the features below were
built and tested — each row names what exists and what does not.

| ID | Requirement (from the supplied description) | Current PRISM state |
|---|---|---|
| **PS75-01** | Secure signup/login with three roles: Trainee, Trainer, Admin | **Partial.** Real OIDC verification and RBAC on 89 of 103 HTTP operations (the rest pinned with reasons in `tests/test_route_auth_inventory.py`), self-service registration with admin approval, and a role-aware work-areas navigation (Learning / Teaching / Administration). The hosted demo still runs `DISABLE_AUTH=true`, so it must not be called protected; browser sign-in routing is verified with a stubbed identity provider, not a live Keycloak realm; and a role must be granted to the account in the identity provider by hand after approval. |
| **PS75-02** | Trainee profile: qualifications, work experience, interests, skills, certificates | **Real, self-declared.** Validated lists for qualifications, work experience, skills, interests and certificates earned elsewhere, editable in the Academy form. None of it is verified or used as competency evidence. Uploading a prior credential's document is not built. |
| **PS75-03** | Enroll in courses | **Real.** `routes/course_enrollment.py` — a real, persisted enroll → complete lifecycle, idempotent on repeat calls. |
| **PS75-04** | Access learning resources | **Real.** Curricula, source-cited question bank, AI-generated quizzes from uploaded material, a RAG learner assistant, and two hands-on labs. |
| **PS75-05** | Attempt subject-wise MCQ assessments | **Real, and the strongest single match in this whole requirement list.** A source-cited competency quiz bank, AI-generated quizzes with independent per-option answer derivation (not a trusted model-stated index), and a two-stage adaptive diagnostic — all subject/topic-scoped. |
| **PS75-06** | Provide feedback on courses and training content | **Real for courses.** One rating and comment per trainee per course, with an anonymized aggregate. Feedback on library items is not built. |
| **PS75-07** | Trainers manage their own profile | **Partial.** Trainers declare expertise per competency (level, basis, years) and read a combined profile, all labelled self-declared. Availability is not modelled. |
| **PS75-08** | Trainers create questionnaires with deadlines | **Real.** Trainer-authored MCQ questionnaires for a cohort or course with a server-clock deadline, one attempt per trainee, answers revealed only after submission, and trainer results for their own audience. Scores are not recorded as competency evidence (a separate, versioned policy decision). |
| **PS75-09** | Trainers monitor trainee participation and performance | **Real, scoped.** Admin-created cohorts with explicit trainer ownership; a trainer sees only their own cohorts and members' enrolment and gap data, with honest zeros where there is no activity. |
| **PS75-10** | Trainer library: upload recorded lectures/presentations/study materials, accessible to trainees | **Real, with caveats.** Upload with a type allowlist and content sniffing, a size cap enforced before parsing, attachment-only downloads, and visibility limited to enrolled trainees for course-linked items. No malware scanning or transcoding, and storage is local disk (not durable on ephemeral hosts). |
| **PS75-11** | Admin: user approval, role management | **Partial.** Approval is real, with an audit trail and an `/admin/approvals` page that shows what the applicant declared. Granting or revoking a role happens in the identity provider by hand; there is no in-app role grant, revoke or deactivation UI. |
| **PS75-12** | Admin dashboards: courses, enrollments, certifications, assessments, participation | **Real.** Database-derived training effectiveness, course completion, activity trend, emerging gaps, plus certificates issued, mean course rating, cohorts and pending approvals. Figures describing fewer than 5 learners (configurable) are withheld and counted. |
| **PS75-13** | Homepage: notifications, announcements, achievements, newly added content | **Real, in-app only.** Admin-authored announcements by audience, courses created in the last 30 days, and the viewer's own recent certificates, on the home page. No push or email notifications. |
| **PS75-14** | Competency mapping to identify suitable trainers per subject | **Partial.** A deterministic, versioned (`trainer-match-v1`) ranking from declared expertise and real teaching activity, with a visible score breakdown and an explicit NO_EVIDENCE label instead of a zero. Declared levels are self-declared. Filters and recording an administrator's decision are not built. |
| **PS75-15** | Scalable, secure, user-friendly, accessible across devices | **Real, with the same honest caveats as everywhere else in this project's docs.** Production-shaped stack (FastAPI, PostgreSQL, Next.js, Docker, real OIDC/RBAC primitives), 1,100+ automated tests, CI with dependency/secret/SAST scanning, a responsive frontend, an 11-language UI. `DISABLE_AUTH=true` on the live demo and the absence of admin-route RBAC enforcement (see `/admin`'s own on-page disclosure) remain open, disclosed gaps — see [Known limitations](../README.md#-known-limitations). |

## What transfers directly, and what does not

**Transfers with real, substantial value** (not a cosmetic reskin): the identity/RBAC primitives;
the entire assessment and quiz-generation engine, including its OCR pipeline and answer-derivation
safeguards; the real course enrollment lifecycle; the admin analytics engine; the production
deployment shape (Docker backend, Vercel frontend, real CI); the 1,100+-test discipline.

**Built for SIH26075 specifically (2026-09-30 to 2026-10-05):** certificate issuance and public
verification; course feedback; announcements and the home feed; admin approval with a review page;
a trainer content library; trainer-authored questionnaires with deadlines; cohort-scoped trainer
visibility; trainer expertise and deterministic trainer matching; structured trainee profiles; and a
role-aware work-areas navigation.

**Still not done:** a protected hosted demo (it runs with authentication bypassed); in-app role
grant/revoke; real sign-in verified end to end in a browser against a live identity provider;
push/email notifications; durable file storage and malware scanning for the library; filters and a
recorded administrator decision for trainer matching; trainer availability; native-reviewed
translations for the pages added after the original 11-language pass; a full accessibility audit;
load testing; and a single scripted seed/reset for the demo story.

## Truth and safety constraints (carried forward from the SIH26101 doc, unchanged in spirit)

- Never describe a feature in the "absent" or "partial" rows above as complete in any pitch,
  README, or demo script until it is actually built and tested.
- Never claim the three-role split is a finished product experience because the underlying RBAC
  roles exist — a role name in the database is not the same claim as a working portal.
- Do not use real personal data (real trainee/trainer identities, real certificates, real employment
  records) in the hackathon build. Synthetic data only, same standard as before.
- "Secure," "scalable," and "production ready" require the same evidence standard already documented
  in this repository's `README.md` — architecture intent is not proof.

## Known unknowns requiring external confirmation

- Current SIH 2026 team/mentor/nodal-center submission rules specific to SIH26075.
- The public official listing does not expose the problem creator's name. “Sarim Moin” is
  portal-provided but not independently verifiable from the public listing; omit it from public
  claims unless the authenticated portal confirms it.
- The correct authorized contact channel for MoES/IMD clarification; the public contact field is blank.
- Whether "certificates" in PS75-02/PS75-12 means an uploaded prior credential (trainee-side) versus
  a platform-issued completion certificate (admin/course-side) — the supplied text uses the word in
  both senses and this repository should not assume which the evaluators mean without asking.
