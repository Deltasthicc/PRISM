# SIH26075 submission draft

This is submission-ready copy grounded in the current repository and the official SIH26075
requirements. Text describing unfinished functionality deliberately uses future tense. Re-check the
live form and the final build before submission.

**Status 2026-09-29: reviewed by both agents, technology bucket and title style resolved directly
with Shashwat.** Cross-check discussion in `ClaudeCode_Codex_UwU.md`. Ready to use as-is.

## Form fields

### Idea title (77 characters; portal maximum 100)

**PRISM Capacity Connect: Secure, Role-Based Learning and Competency Management**

### Technology bucket

**AI/ML, Cloud Computing, Blockchain** — resolved with Shashwat 2026-09-29. "Smart Education" is
SIH26075's official *theme* on the national portal, but it is not an option on this specific
idea-submission form's Technology Bucket dropdown (confirmed directly from a screenshot of the real
form). Its actual option list is: `AI/ML, Cloud Computing, Blockchain` / `Big Data Analysis` /
`Coding and Programming` / `Information Security` / `IoT and Electronics` / `Mechatronics` /
`Project Management` / `Social Media Management & Digital Marketing` / `System Administration &
Networking` / `Other`. PRISM's actual implementation is genuinely AI/ML-driven and cloud-deployed,
so this is the closest real match, not just the least-wrong option.

### YouTube link

Use the team's real public/unlisted demo link only after verifying it opens without the uploader's
account. Otherwise leave this optional field blank. Do not enter a placeholder.

### Idea description

Organizations often conduct valuable training through scattered portals, documents, recordings,
spreadsheets, and one-time assessments. That makes it difficult for a trainee to understand what to
learn next, for a trainer to support the right cohort, and for administrators to see whether courses
are actually improving capability. PRISM Capacity Connect is our proposed centralized learning and
competency platform for the Ministry of Earth Sciences and India Meteorological Department. It
connects professional profiles, courses, learning resources, assessments, evidence, feedback, and
organizational insight in one responsive web application.

The platform is organized around the three roles required by SIH26075.

**Trainees** create a professional profile containing qualifications, experience, interests,
skills, training history, and certificates. They discover and enrol in courses, open lectures,
presentations, and study material from the trainer library, attempt subject-wise MCQ assessments,
track progress, and submit feedback on courses and content. Assessment and activity evidence updates
an explainable competency profile, so a recommendation can state which demonstrated gap, target,
or prerequisite led to it instead of presenting an unexplained score.

**Trainers** maintain profiles that describe their subject expertise and supporting evidence. They
publish learning resources, create or review questionnaires, set deadlines, manage assigned
cohorts, and monitor participation and performance without receiving unrestricted access to every
trainee. The system will be able to use the same versioned competency taxonomy to suggest suitable trainers
for a subject, showing the matching skills and evidence so an administrator can review the suggestion.

**Admins** approve accounts, assign roles, manage the learning catalogue, and view dashboards for
courses, enrolments, certifications, assessments, and participation. They can publish notifications,
announcements, achievements, and newly added resources to the homepage. Administrative actions and
important record changes are auditable.

PRISM's assessment and knowledge features make the portal more than a file repository. A trainer
can upload text, PDF, DOCX, PPTX, audio, video, or a scanned image. The content pipeline extracts or
transcribes the material, creates draft MCQs grounded in source passages, and sends them through a
trainer edit-and-approval step before learner use. Each approved question retains its source
provenance. A retrieval-based assistant can answer from the authorized knowledge collection with
supporting passages and decline when it cannot find sufficient evidence. These controls are intended
to reduce unsupported AI answers and keep trainers in charge of published content.

The competency layer supports a configurable hierarchy of domains, competencies, and skills rather
than hard-coding an invented “official” framework. MoES/IMD administrators can version the taxonomy,
set role or course targets, and relate assessments, certificates, resource completion, and trainer
expertise to the same skills. This supports both personalized development plans for trainees and
transparent trainer discovery for administrators.

The existing PRISM prototype already demonstrates reusable foundations: learner profiles, persisted
course enrolment and completion, subject-wise and adaptive assessments, source-cited question banks,
multiformat content ingestion, trainer review of generated questions, live group assessments,
competency-gap and pathway logic, multilingual UI, database-backed analytics, PostgreSQL migrations,
audit records, and OIDC/RBAC security primitives. For SIH26075, we are extending those foundations
into complete Trainee, Trainer, and Admin journeys, including approval, certificates, feedback,
deadline-based questionnaires, trainer libraries, cohort-scoped monitoring, announcements, and
trainer-to-subject matching. We do not present those remaining workflows as already complete.

The solution uses a Next.js/React frontend, FastAPI services, PostgreSQL with versioned migrations,
and containerized deployment. The intended secured deployment uses standards-based OpenID Connect,
role and object-scope authorization, audit events, encrypted transport, controlled retention, and
backups. The web interface is designed for desktop and mobile use, with English as the default and
additional Indian-language interface support. Media storage and background processing can be scaled
independently from the application and database as usage grows.

Our demonstration follows one connected evidence trail: an admin approves a trainer and trainee;
the trainer publishes a resource and a deadline-based subject assessment; the trainee enrols,
studies, attempts the assessment, and gives feedback; the result updates the trainee's competency
evidence; the system recommends the next learning action and an appropriate trainer; and the admin
dashboard reflects the enrolment, participation, result, and certificate state. This makes every
headline capability inspectable rather than a disconnected mock-up.

PRISM Capacity Connect aims to help MoES/IMD make organizational learning easier to access, easier
to manage, and easier to evaluate. Its central principle is simple: profiles, recommendations, and
dashboards should be backed by visible evidence, while trainers and administrators retain control
over published learning content and decisions.

### Abstract / summary

PRISM Capacity Connect is a proposed centralized learning and competency-management portal for the
Ministry of Earth Sciences and India Meteorological Department. It brings professional profiles,
courses, trainer resources, subject assessments, certificates, feedback, announcements, and
organizational analytics into one responsive platform for Trainees, Trainers, and Admins.

Trainees will create evidence-backed profiles, enrol in courses, access lectures and study material,
take subject-wise MCQs, track competency development, and submit feedback. Trainers will maintain
expertise profiles, publish resources, create or review questionnaires with deadlines, and monitor
only their assigned cohorts. Admins will approve users, manage roles, publish homepage updates, and
track courses, enrolments, certifications, assessments, and participation. A shared, versioned
competency taxonomy will support explainable learning recommendations and transparent matching of
qualified trainers to subjects.

PRISM's existing prototype already demonstrates learner profiles, persisted enrolment/completion,
adaptive assessments, source-cited quiz banks, multiformat content ingestion, trainer review of
AI-generated questions, live assessments, multilingual interfaces, PostgreSQL-backed analytics,
audit records, and OIDC/RBAC foundations. The SIH26075 transition adds the role-specific LMS
workflows that are not yet complete: account approval, certificate and feedback records,
deadline-based questionnaires, a trainee-facing trainer library, cohort-scoped monitoring,
homepage publishing, and trainer-to-subject matching.

Uploaded text, documents, presentations, audio, video, or scanned material can be converted into
trainer-reviewed draft assessments with source provenance. A retrieval-based assistant is designed
to answer from authorized material with citations and abstain when evidence is insufficient. The
solution uses Next.js/React, FastAPI, PostgreSQL, containerized deployment, and standards-based
identity primitives. Its goal is a secure, accessible, and auditable capacity-building system where
recommendations and dashboards can be traced back to real learning evidence rather than opaque
claims.

## Six-slide idea-template plan

Use the template downloaded from the submission portal. Public copies of the current template show
the following six retained slides; the separate instruction slide is deleted before upload. Confirm
the headings against the portal download before authoring and do not replace its visual structure.

1. **Title Page** — PS ID 26075; exact PS title; Smart Education; Software; registered Team ID and
   Team Name; solution title “PRISM Capacity Connect.”
2. **Idea Title / Proposed Solution** — one role-aware portal; the connected Admin → Trainer →
   Trainee evidence flow; 4–5 concise differentiators. Use a workflow graphic, not paragraphs.
3. **Technical Approach** — Next.js/React, FastAPI, PostgreSQL, content pipeline, storage/background
   processing, OIDC/RBAC/audit boundaries; show one readable architecture and flow diagram.
4. **Feasibility and Viability** — separate implemented, in-progress, and planned capabilities;
   show the working prototype evidence, major risks, and concrete mitigations.
5. **Impact and Benefits** — easier access to learning, transparent competency development, trainer
   reuse, administrator visibility, multilingual/device accessibility, and organization-wide
   knowledge retention. Avoid invented impact numbers.
6. **Research and References** — official SIH26075 page, relevant MoES/IMD public training or
   capacity-building sources actually consulted, identity/accessibility standards used, and any
   technical sources. Do not cite sources the team has not read.

## Pre-submission checks

- Download and use the portal's current official template; export to PDF under 10 MB.
- Confirm the idea title is within 100 characters and field text within displayed limits.
- Verify the selected technology bucket is Smart Education.
- Test the YouTube URL in a private browser window or leave it blank.
- Remove any MoSPI, NSSTA, iGOT, SIH26101, or government-statistics-specific claim that is not
  explicitly relevant to the new demonstration.
- Label prototype screenshots accurately; do not display planned screens as implemented.
- Confirm every claimed flow runs against the build submitted to judges.
- Have a teammate perform a final proofread against the live SIH26075 wording before Save as Draft
  and again before final submission.
