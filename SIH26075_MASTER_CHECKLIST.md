# SIH26075 master checklist — PRISM Capacity Connect

**Current target:** SIH26075, CAPACITY CONNECT (MoES / India Meteorological Department)

**Canonical requirements:** `docs/SIH26075_PROBLEM_STATEMENT.md` (`PS75-01`…`PS75-15`)
**Rule:** checked means working evidence exists in the repository or deployed demo. A model, route,
or design note alone is not a complete user workflow.

## P0 — coherent judged demonstration

- [ ] **PS75-01 / Lanes 1, 2, 5:** secure Trainee, Trainer, and Admin sign-in plus role-aware entry.
  Backend OIDC/RBAC primitives exist; demo auth bypass and role-specific browser journeys remain.
- [ ] **PS75-02 / Lanes 1, 2, 5:** complete trainee profile with structured experience, interests,
  skills, and certificates. Current learner profile is partial.
- [x] **PS75-03 / Lanes 2, 5:** persisted course enrolment and completion lifecycle.
- [ ] **PS75-04 / Lanes 1, 4, 5:** trainee-browsable resource library. Existing ingestion and
  curricula are reusable, but a trainer-owned library is not yet present.
- [x] **PS75-05 / Lanes 3, 4, 5:** subject-scoped MCQ assessment and adaptive diagnostic.
- [ ] **PS75-06 / Lanes 1, 2, 5:** course/content feedback with one submission per trainee/content
  policy, edit rules, and aggregate reporting.
- [ ] **PS75-07 / Lanes 1, 2, 5:** trainer profile containing subjects, qualifications, experience,
  availability, and evidence.
- [ ] **PS75-08 / Lanes 1, 2, 4, 5:** trainer-authored questionnaire, publish state, deadline,
  attempts, and late/submission policy. Existing AI-item review is only a building block.
- [ ] **PS75-09 / Lanes 1, 2, 5:** server-side trainer/cohort assignment and scoped participation/
  performance view. Do not grant trainers global learner access.
- [ ] **PS75-10 / Lanes 1, 2, 4, 5:** trainer resource upload, metadata, access control, discovery,
  and trainee viewing for recordings, presentations, and study material.
- [ ] **PS75-11 / Lanes 1, 2, 5:** pending-account approval and role grant/revoke admin workflow,
  with audit events and denial tests.
- [ ] **PS75-12 / Lanes 1, 2, 5:** connected admin dashboard covering courses, enrolments,
  certificates, assessments, and participation. Existing analytics cover only part of this.
- [ ] **PS75-13 / Lanes 1, 2, 5:** publishable homepage notifications, announcements,
  achievements, and newly added content.
- [ ] **PS75-14 / Lanes 1, 2, 3, 5:** explainable subject-to-trainer matching using trainer evidence,
  with filters and an administrator decision rather than automatic assignment.
- [ ] **PS75-15 / All lanes; Lane 6 acceptance:** responsive golden path, keyboard/accessibility
  checks, authorization negatives, clean-data demo reset, deployment smoke test, and evidence pack.

## P0 golden path

One seed/reset command must produce synthetic demo data for this connected story:

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
  expects prior credentials, platform-issued course certificates, or both.
- [ ] Add low-bandwidth media behaviour, size/type limits, resumable/background processing where
  needed, and visible failure/retry states.
- [ ] Apply object-scope authorization to every new learner, cohort, questionnaire, resource,
  certificate, feedback, and announcement route.
- [ ] Add audit events for approvals, role changes, publishing, certificate actions, and overrides.
- [ ] Run native-speaker review for shipped translations; machine translation is not final evidence.
- [ ] Replace inherited Official Statistics/iGOT demo framing on the primary journey with truthful,
  synthetic organizational training content. Retain the old content only as a clearly labelled
  sample catalogue until new content is validated.

## P2 — release evidence

- [ ] Requirement-to-route/page/test evidence table for all PS75 IDs.
- [ ] Clean full backend, frontend, and end-to-end gates recorded at one immutable commit.
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
