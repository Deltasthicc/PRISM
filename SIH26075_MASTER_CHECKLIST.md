# SIH26075 master checklist — PRISM Capacity Connect

**Current target:** SIH26075, CAPACITY CONNECT (MoES / India Meteorological Department)

**Canonical requirements:** `docs/SIH26075_PROBLEM_STATEMENT.md` (`PS75-01`…`PS75-15`)
**Rule:** checked means working evidence exists in the repository or deployed demo. A model, route,
or design note alone is not a complete user workflow.

## P0 — coherent judged demonstration

- [ ] **PS75-01 / Lanes 1, 2, 5:** secure Trainee, Trainer, and Admin sign-in plus role-aware entry.
  Real: OIDC bearer verification and RBAC on 89 of 103 HTTP operations (the 14 open ones are pinned
  with reasons in `backend/tests/test_route_auth_inventory.py`); self-service registration with
  admin approval; `GET /auth/me` so a returning user is routed by real status; a work-areas bar
  that shows Learning / Teaching / Administration by token role. **Still open:** the hosted demo
  runs `DISABLE_AUTH=true`, so it is not protected; the OIDC browser routing is verified with a
  stubbed identity provider and API (Playwright), not against a live Keycloak realm; roles must be
  granted to the account in the identity provider by hand after approval.
- [x] **PS75-02 / Lanes 1, 2, 5:** complete trainee profile with structured experience, interests,
  skills, and certificates. **2026-10-05:** validated lists for qualifications, work experience,
  skills, interests and certificates earned elsewhere (migration `e1f2a3b4c5d6`), editable in the
  Academy profile form. All self-declared and unverified; not used as competency evidence.
  Platform-issued certificates are separate (PS75-12).
- [x] **PS75-03 / Lanes 2, 5:** persisted course enrolment and completion lifecycle.
  **2026-09-30 (Claude, PR #93):** extended, not just re-confirmed — a real trainer-authored `Course`
  table now exists (`backend/models/course.py`), enrollable via a new `internal::<course_id>`
  provider path in the pre-existing enroll/complete lifecycle, sitting alongside the untouched
  igot/nssta simulated path. Still needs a trainee-facing browse/enroll UI (PS75-04/Lane 1) and a
  trainer-facing create/publish UI (PS75-10/Lane 1) — the route contract is ready to build against.
- [x] **PS75-04 / Lanes 1, 4, 5:** trainee-browsable resource library. Trainer uploads (PS75-10) are
  listed at `/library` for trainees (course-linked items only for enrolled trainees) alongside the
  curricula and AI-quiz material. Storage is local disk, not durable on ephemeral hosts.
- [x] **PS75-05 / Lanes 3, 4, 5:** subject-scoped MCQ assessment and adaptive diagnostic.
- [x] **PS75-06 / Lanes 1, 2, 5:** course/content feedback with one submission per trainee/content
  policy, edit rules, and aggregate reporting. **2026-10-01 (PR #95):** one rating + comment per
  trainee per course (upsert), anonymized aggregate; the admin dashboard shows the mean only when
  at least the minimum group size of learners rated.
- [ ] **PS75-07 / Lanes 1, 2, 5:** trainer profile containing subjects, qualifications, experience,
  availability, and evidence. **2026-10-05 (PR #108):** declared expertise per competency (level,
  basis, detail, years teaching) and a combined profile read, all labelled self-declared.
  **Still open:** availability is not modelled.
- [x] **PS75-08 / Lanes 1, 2, 4, 5:** trainer-authored questionnaire, publish state, deadline,
  attempts, and late/submission policy. **2026-10-05 (PR #109):** MCQ questionnaires for a cohort
  or course, server-clock deadline (inclusive; a late submission is rejected and writes nothing),
  one attempt per trainee, answers hidden until submission, trainer results for their own
  audience, forward-only deadline extension. Scores are deliberately NOT written as competency
  evidence (a scoring-policy decision). A date-formatting crash found by the live-stack run was
  fixed in PR #113.
- [x] **PS75-09 / Lanes 1, 2, 5:** server-side trainer/cohort assignment and scoped participation/
  performance view. **2026-10-01 (PR #97):** admin-created cohorts with explicit trainer ownership;
  a trainer sees only their own cohorts and members' real enrolment/gap data (honest zero where
  there is no activity).
- [x] **PS75-10 / Lanes 1, 2, 4, 5:** trainer resource upload, metadata, access control, discovery,
  and trainee viewing for recordings, presentations, and study material. **2026-10-05 (PR #106):**
  type allowlist with content sniffing, size cap enforced before parsing, server-generated file
  names, attachment-only downloads. **Not implemented:** malware scanning, transcoding, durable
  storage (local disk).
- [ ] **PS75-11 / Lanes 1, 2, 5:** pending-account approval and role grant/revoke admin workflow,
  with audit events and denial tests. **Done:** approval API with audit trail, and
  `/admin/approvals` showing what the applicant declared and which identity-provider account to
  grant the role to (PR #107). **Still open:** granting or revoking a role itself happens in the
  identity provider by hand; there is no in-app role grant/revoke or deactivation UI.
- [x] **PS75-12 / Lanes 1, 2, 5:** connected admin dashboard covering courses, enrolments,
  certificates, assessments, and participation. **2026-10-05:** adds certificates, mean course
  rating (withheld below the minimum group size), cohorts and pending approvals to the existing
  analytics; figures describing fewer than 5 learners are withheld (`ANALYTICS_MIN_GROUP_SIZE`).
- [x] **PS75-13 / Lanes 1, 2, 5:** publishable homepage notifications, announcements,
  achievements, and newly added content. **2026-10-05 (PR #110):** admin-authored announcements and
  an in-app feed on the home page (announcements by audience, courses created in the last 30 days,
  and the viewer's own certificates only). No push or email notifications.
- [ ] **PS75-14 / Lanes 1, 2, 3, 5:** explainable subject-to-trainer matching using trainer evidence,
  with filters and an administrator decision rather than automatic assignment. **2026-10-05
  (PR #108):** deterministic `trainer-match-v1` ranking with a visible score breakdown and a
  NO_EVIDENCE label (never a zero). **Still open:** filters, and recording an administrator's
  decision.
- [ ] **PS75-15 / All lanes; Lane 6 acceptance:** responsive golden path, keyboard/accessibility
  checks, authorization negatives, clean-data demo reset, deployment smoke test, and evidence pack.

## P0 golden path

One seed/reset command must produce synthetic demo data for this connected story. **Status
2026-10-05:** every step now has a working page and API, and `npm run test:live` drives most of
them against a real backend, but there is no single seed/reset command and the story has not been
run end to end as one scripted flow:

1. Admin approves a pending Trainer and Trainee and assigns their roles.
2. Trainer completes expertise profile, publishes a resource, creates an MCQ questionnaire, and
   sets a deadline for an assigned cohort.
3. Trainee completes profile, enrols, opens the resource, attempts the questionnaire, and leaves
   feedback.
4. Assessment evidence updates the trainee competency view and next-learning recommendation.
5. Admin searches a subject and sees explainable trainer matches.
6. Admin dashboard reflects the course, enrolment, assessment, participation, feedback, and
   certificate state; an announcement appears on the homepage.

No step may depend on a manually edited database row or an undocumented local-only value.

## P1 — trust and usefulness

- [ ] Version the configurable competency taxonomy and clearly label demo MoES/IMD content as
  team-authored until an authorized owner validates it.
- [ ] Add certificate issue/upload/download/verification semantics after resolving whether the PS
  expects prior credentials, platform-issued course certificates, or both. Built: platform-issued
  certificates with public verification (PR #95) and self-declared prior credentials (PS75-02).
  Not built: uploading or verifying a prior credential's document.
- [ ] Add low-bandwidth media behaviour, size/type limits, resumable/background processing where
  needed, and visible failure/retry states.
- [x] Apply object-scope authorization to every new learner, cohort, questionnaire, resource,
  certificate, feedback, and announcement route. Each slice has ownership/denial tests, and
  `tests/test_route_auth_inventory.py` fails if a route ships without authentication.
- [ ] Add audit events for approvals, role changes, publishing, certificate actions, and overrides.
- [ ] Run native-speaker review for shipped translations; machine translation is not final evidence.
- [ ] Replace inherited Official Statistics/iGOT demo framing on the primary journey with truthful,
  synthetic organizational training content. Retain the old content only as a clearly labelled
  sample catalogue until new content is validated.

## P2 — release evidence

- [ ] Requirement-to-route/page/test evidence table for all PS75 IDs.
- [ ] Clean full backend, frontend, and end-to-end gates recorded at one immutable commit.
  As of 2026-10-05 on `main`: backend 1,403 passed / 25 skipped locally (3 OCR tests need tesseract,
  which CI installs); Vitest 73; Playwright 29 (stubbed backend) + 8 live-stack journeys
  (`npm run test:live`, manual). Not yet recorded at a single tagged commit.
- [ ] PostgreSQL migration/rollback and backup/restore drill for the final schema.
- [ ] Access-control matrix with positive and negative tests for all three roles.
- [ ] Responsive and keyboard checks on the golden path; automated scan plus manual screen-reader
  smoke test on the final build.
- [ ] Measured load test with documented hardware, dataset, concurrency, latency percentiles, and
  error rate. Do not convert a local test into an unsupported scale claim.
- [ ] Demo video and idea PDF verified from a signed-out/private window and below portal limits.
- [ ] README and submission copy audited so implemented, simulated, planned, and external claims
  cannot be confused.

## External decisions and inputs

- [ ] Confirm current SIH registration/team/mentor rules through the college SPOC.
- [ ] Confirm the meaning and lifecycle of “certificates.”
- [ ] Obtain approved MoES/IMD subject taxonomy, training material, and content owner where possible.
- [ ] Confirm the authorized identity provider and deployment/data-handling policy for any pilot.
- [ ] Provide registered Team ID, Team Name, final demo URL, and the portal-downloaded idea template
  before producing the final submission PDF.

## Preserved history

`docs/archive/SIH26101_MASTER_CHECKLIST.md`, `docs/internal/LANE2_SYNC.md`, and `EVIDENCE.md` remain
historical engineering evidence. Their old PS numbers are intentional and must not be mass-replaced.
