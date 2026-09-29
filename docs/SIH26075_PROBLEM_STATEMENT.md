# SIH26075 problem-statement source and requirement contract

Captured: 29 September 2026

Source: verbatim record supplied by Shashwat, independently cross-checked against a public
structured mirror of the official SIH 2026 portal dataset (`vedantchalke36/sih-2026-problem-statements`,
`data/sih2026_ps.json`, record `sno: 75`) — title, organization, theme, and full description text
matched exactly. This file is the repository's canonical statement of the current requested product
scope, superseding `docs/archive/SIH26101_PROBLEM_STATEMENT.md`.

## Problem metadata

| Field | Value |
|---|---|
| Problem Statement ID | `SIH26075` |
| Organization | Ministry of Earth Sciences (MoES) |
| Department | India Meteorological Department (IMD) — the public dataset's `department` field. Note: the portal's problem-creator record separately names "Ministry of Education's Innovation Cell (MIC)" — MIC is the hackathon's own facilitating body and appears as the administering contact on many unrelated ministries' problem statements in the same dataset, not SIH26075's owning department. Use MoES/IMD when precision about ownership matters. |
| Category | Software |
| Theme | Smart Education |
| Dataset links | None supplied |
| YouTube/contact | None supplied |
| Ideas submitted (as of capture) | 0/500 — essentially uncontested at capture time, unlike SIH26101's much higher submission count |

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
The "Current PRISM state" column is a direct result of an independent code audit performed
2026-09-29 (grep + direct file reads against `main` at `cec89f6`) — not an assumption.

| ID | Requirement (from the supplied description) | Current PRISM state |
|---|---|---|
| **PS75-01** | Secure signup/login with three roles: Trainee, Trainer, Admin | **Partial.** Real roles exist in `security/rbac.py` (`learner`, `trainer`, `department_admin`, `organization_admin`) with real permission sets, but the deployed demo runs `DISABLE_AUTH=true` (documented in every existing doc), and there is no separated three-portal *frontend* experience — today's UI is one shared app surfaced differently by feature flags, not three distinct role-specific portals. |
| **PS75-02** | Trainee profile: qualifications, work experience, interests, skills, certificates | **Partial.** `LearnerProfile` has designation, department, job role, current assignment, educational qualifications, numeric years of experience, previous trainings, career goal, preferred language. **Missing**: an `interests` field, a `certificates` field, and free-text work-experience detail beyond the numeric years count. |
| **PS75-03** | Enroll in courses | **Real.** `routes/course_enrollment.py` — a real, persisted enroll → complete lifecycle, idempotent on repeat calls. |
| **PS75-04** | Access learning resources | **Real.** Curricula, source-cited question bank, AI-generated quizzes from uploaded material, a RAG learner assistant, and two hands-on labs. |
| **PS75-05** | Attempt subject-wise MCQ assessments | **Real, and the strongest single match in this whole requirement list.** A source-cited competency quiz bank, AI-generated quizzes with independent per-option answer derivation (not a trusted model-stated index), and a two-stage adaptive diagnostic — all subject/topic-scoped. |
| **PS75-06** | Provide feedback on courses and training content | **Absent.** No course/content feedback or rating mechanism exists anywhere in the schema or routes. |
| **PS75-07** | Trainers manage their own profile | **Partial.** The same `LearnerProfile` mechanism exists for any account; there is no trainer-specific profile shape (e.g., subjects taught, qualifications-to-teach). |
| **PS75-08** | Trainers create questionnaires with deadlines | **Partial, narrower than the ask.** `routes/quiz_review.py` lets a trainer edit and approve *AI-generated* quiz items before they publish. It does not let a trainer author a fresh questionnaire from a blank page, and there is no deadline/due-date concept anywhere in the quiz or assessment schema. |
| **PS75-09** | Trainers monitor trainee participation and performance | **Absent by design today**, not just unbuilt — confirmed directly in `security/rbac.py`'s own comment: cross-learner trainer access is deliberately withheld "until a server-side trainer/cohort assignment model exists." The `trainer` role currently carries only `CONTENT_DRAFT_CREATE`. Admin-level aggregate analytics exist (`routes/learning_analytics.py`), but there is no per-trainer, per-assigned-cohort view. |
| **PS75-10** | Trainer library: upload recorded lectures/presentations/study materials, accessible to trainees | **Absent as a standalone feature.** Document upload exists today only as *input to AI quiz generation* (`ai/ingestion.py`, including a real OCR pipeline for scanned/image content) — there is no browsable materials/media library independent of that quiz-generation flow. |
| **PS75-11** | Admin: user approval, role management | **Absent (approval); partial (role management).** Any new signup is immediately active — there is no pending/approved account state anywhere. Role assignment exists at the data-model level (`identity_bindings`, `security/rbac.py`) but has no dedicated admin UI for granting/revoking a role. |
| **PS75-12** | Admin dashboards: courses, enrollments, certifications, assessments, participation | **Mostly real.** `routes/learning_analytics.py` provides real, database-derived training-effectiveness, course-completion, activity-trend, and emerging-skill-gap analytics. **Missing**: "certifications" specifically, since no certificate concept exists anywhere in the schema. |
| **PS75-13** | Homepage: notifications, announcements, achievements, newly added content | **Absent.** No announcement/notification model, route, or UI exists anywhere in the codebase (confirmed by an exhaustive grep, not inferred). |
| **PS75-14** | Competency mapping to identify suitable trainers per subject | **Absent in the direction this PS asks for.** PRISM's entire competency engine maps a *learner's* demonstrated capability against a target (the reverse direction). Finding "which trainer is qualified to teach subject X" is a genuinely different query/feature that does not exist today, even though the same underlying competency taxonomy could plausibly power it. |
| **PS75-15** | Scalable, secure, user-friendly, accessible across devices | **Real, with the same honest caveats as everywhere else in this project's docs.** Production-shaped stack (FastAPI, PostgreSQL, Next.js, Docker, real OIDC/RBAC primitives), 1,100+ automated tests, CI with dependency/secret/SAST scanning, a responsive frontend, an 11-language UI. `DISABLE_AUTH=true` on the live demo and the absence of admin-route RBAC enforcement (see `/admin`'s own on-page disclosure) remain open, disclosed gaps — see [Known limitations](../README.md#-known-limitations). |

## What transfers directly, and what does not

**Transfers with real, substantial value** (not a cosmetic reskin): the identity/RBAC primitives;
the entire assessment and quiz-generation engine, including its OCR pipeline and answer-derivation
safeguards; the real course enrollment lifecycle; the admin analytics engine; the production
deployment shape (Docker backend, Vercel frontend, real CI); the 1,100+-test discipline.

**Does not transfer, and needs to be built for SIH26075 specifically**: certificate issuance;
course/content feedback collection; a homepage announcements/notifications feed; admin
user-approval and a dedicated role-management UI; a trainer content library independent of
quiz-generation; trainer-authored questionnaires with deadlines; cohort-scoped trainer visibility
into "their" trainees; and trainer-to-subject competency matching (the reverse of PRISM's existing
gap-analysis direction).

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
- Whether MoES/IMD or MIC is the correct point of contact for any clarification request.
- Whether "certificates" in PS75-02/PS75-12 means an uploaded prior credential (trainee-side) versus
  a platform-issued completion certificate (admin/course-side) — the supplied text uses the word in
  both senses and this repository should not assume which the evaluators mean without asking.
