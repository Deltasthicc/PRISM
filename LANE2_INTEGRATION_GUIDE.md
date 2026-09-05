# Lane 2 integration guide

Owner: Lane 2 (Core Platform, Identity & Data). Written as Package W-B (`LANE2_SYNC.md`'s "Package
W — cross-lane database usability and accountability loop"), alongside Codex's Package W-A
(`backend/db/repositories.py`'s read facade). This is the single place every other lane should look
to answer three questions: *what can I use of Lane 2's today without asking*, *what do I still need
to build or ask for*, and *what does Lane 2 need from me before the two sides actually connect*.

This guide does not replace the contracts (`docs/contracts/data-authorization.md`,
`docs/contracts/identity-authorization.md`) — it is a map to them, plus the exact function
signatures, file paths and a copy-ready message per lane. Where this guide and a contract disagree,
the contract wins; open a correction here rather than trusting a stale summary.

`LANE2_HANDOFF_FOR_OTHER_LANES.md` remains the dated, issue-by-issue punch list raised from live
testing (Quest-mode-optional, professional theming, i18n, admin RBAC, self-assessment policy). This
guide is the standing reference for *how to integrate at all*; that file is the standing reference
for *specific defects already found*. Read both.

## How to check your own setup before asking Lane 2 anything

```powershell
cd backend
.\.venv\Scripts\python.exe -m scripts.database_status
```

This prints, in plain text, whether your local database is at the repository's Alembic head, which
of `DATABASE_URL` / `OIDC_ISSUER` / `OIDC_AUDIENCE` / `GEMINI_API_KEY` / `SEED_DEMO_DATA` are set
(booleans only — it never prints a secret's value), and a row count for every Lane-2-owned table.
Add `--json` for machine-readable output, or `--check-migrations` to get a non-zero exit code when
your database isn't current (useful in a script or CI step: `... --check-migrations || echo "run
alembic upgrade head first"`). If you're wiring `--check-migrations` into CI (Lane 6), add
`--migration-only` too: it skips every table's `COUNT(*)` and reports only the migration-head/
missing-table signal `--check-migrations` actually needs — a CI gate has no reason to pay for
counting every row of every table on each run just to answer a yes/no schema question. It never
accepts a player ID, a free-text filter, or anything else that could be pointed at one subject —
see `backend/scripts/database_status.py`'s module docstring and
`backend/tests/test_core_database_status.py` for the exact, tested privacy boundary. If your
"why isn't this working" question is "is my DB current" or "is my API key actually picked up," run
this before opening a thread.

## Lane 1 — Professional Experience & Accessibility

**Lane 2 provides today:**
- `players.preferred_mode` (`"professional"` default, `"quest"`), DB-constrained, documented in
  `docs/contracts/data-authorization.md` §8. `schemas/player.py`'s `PlayerResponse` already returns
  it read-only.
- `docs/contracts/identity-authorization.md` §1 specifies the exact browser login flow you and Lane
  5 must build (Authorization Code + PKCE, `S256`, exact redirect URIs, transaction-bound
  state/nonce) — read this before writing any login UI, so it isn't rebuilt later.

**You provide:**
- A settings control that lets a learner change `preferred_mode`, once Lane 5 exposes a write route
  for it (see Lane 5's section below) — the field exists; nothing can change it yet.
- Conditional nav/routing so "Dungeon"/"Guild"/"Ranks" hide when `preferred_mode == "professional"`.
- The actual browser Authorization Code + PKCE flow, coordinated with Lane 5, against
  `identity-authorization.md` §1 exactly — not the implicit or password grant.

**Route and DB usage:** you never query Lane 2's database directly. Everything comes from Lane
5's routes, which read `PlayerResponse.preferred_mode` and (once built) an OIDC session. Do not
infer any tenant/organization boundary from free-text profile fields like `department` —
`data-authorization.md` §1 is explicit that no real multi-tenant isolation exists yet.

**Acceptance evidence Lane 2 will look for:** a Playwright scenario showing `preferred_mode` toggled
and Quest-only nav items disappearing; no UI claim that data is organization-isolated.

**Copy-ready message:**
> Lane 2 has shipped `players.preferred_mode` (`professional`/`quest`, DB-constrained) and the exact
> browser login flow spec you need (`docs/contracts/identity-authorization.md` §1 — Authorization
> Code + PKCE, `S256`, no implicit/password grant). Once Lane 5 exposes a read/write route for
> `preferred_mode`, please add the settings control and conditional nav hiding described in
> `LANE2_HANDOFF_FOR_OTHER_LANES.md` item 1. Please build browser login against §1 exactly rather
> than a placeholder flow — it will save a rebuild later.

## Lane 3 — Competency & Learning Intelligence

**A note on scope, same reason as Lane 4's:** `main`'s `services/learning_engine.py::analyse_competencies()`
today accepts only `(curriculum_slug, self_ratings, measured_scores, experience_level)` — no
role/designation/department parameters exist yet on `main`, and `backend/services/role_targets.py`,
`behavioral_anchors.py` and `backend/labs/sampling_lab.py` do not exist on `main` at all (`backend/labs/`
is currently just an empty `__init__.py` scaffold). If your working branch has role-aware targeting,
behavioral anchors or a sampling lab already built, that's real progress not yet merged — this
section describes `main` as it stands, not your branch, specifically so it doesn't repeat the same
mistake this guide's first draft made about Lane 4 (see that section's note).

**Lane 2 provides today, ready for whenever role-aware targeting merges into `main`:**
- `models/governance.py`'s `RoleTarget` table (`framework_version`, `role`, `competency_id`,
  `target_level`, `source`, `approved_by`, `valid_from`/`valid_to`) — a versioned, sourced target
  store, independent of whatever in-memory or hardcoded target logic exists on any lane's branch.
- `models/governance.py`'s `EvidenceRecord` table (`evidence_id`, `player_id`, `competency_id`,
  `evidence_type` from `EVIDENCE_TYPES`, `value`, `detail`, `recorded_at`) for separating evidence
  by type, per `SIH26101_MASTER_CHECKLIST.md` §4.1's ask. Note `EvidenceRecordCreate`
  (`schemas/governance.py`) requires `player_id` — any evidence-writing code (a lab, a diagnostic,
  a reviewer action) needs to supply it.
- **Package W-A** (Codex, commit `3a75b28`, ACCEPTED on Claude's independent review — see
  `LANE2_SYNC.md`'s Package W entry) adds three read-only repository functions to
  `backend/db/repositories.py`:
  ```python
  get_current_role_target(db, role, competency_id, *, as_of=None)   # exact-role lookup, half-open validity window
  get_latest_evidence(db, player_id, competency_id, evidence_type)  # one evidence type, newest row
  get_latest_source_version(db, material_id)                        # highest version_number for one material
  ```
  `get_current_role_target` is an **exact** `(role, competency_id)` match at one instant — it does
  not normalize aliases, pick among `job_role`/`designation`/`department`, or fall back to a
  role-agnostic default. That precedence logic is explicitly left to you; see
  `docs/contracts/data-authorization.md` §4.1 for the exact tie-breaking rules.

**You provide:**
- Whichever role-aware targeting, behavioral-anchor and lab work exists on your own branch, merged
  through the normal PR process and built against `get_current_role_target()` rather than a
  standalone in-memory map, so there's one source of truth once it lands.
- Once `analyse_competencies()` gains role/designation/department parameters, coordinate with Lane 5
  so `routes/learning.py` actually forwards `LearnerProfile`'s corresponding fields — a new parameter
  nobody calls with real data is as unreachable as one that was never added.
- Any evidence-writing code (a lab, a diagnostic) constructing an `EvidenceRecordCreate` payload
  must include `player_id`, `competency_id`, `evidence_type` from `EVIDENCE_TYPES`, and `value`.
  **On `origin/codex/lane-3-competency/role-target-v1`** (checked directly, not assumed): that
  branch's `backend/labs/sampling_lab.py::evidence_payload(task_id)` returns only
  `{competency_id, evidence_type, value, detail}` — missing `player_id`, which
  `EvidenceRecordCreate` requires. Add it there before merging, or the write will fail Pydantic
  validation the first time the lab is actually wired to persist evidence.

**Route and DB usage:** call the repository functions above from your own service code with a
`Session` passed in from whichever route calls you — never open your own engine/session. These
functions return raw ORM rows, not API responses; serialize through `backend/schemas/**`
(Lane 2-owned) at any HTTP boundary, never return an ORM object directly from a route.

**Acceptance evidence Lane 2 will look for:** once role-aware targeting merges, a test proving
`analyse_competencies()`'s output actually changes when `get_current_role_target()` returns a real
row vs. `None` — not just that the lookup function itself is tested in isolation.

**Copy-ready message:**
> Lane 2 (with Codex's Package W-A, commit `3a75b28`, accepted) has added `get_current_role_target()`,
> `get_latest_evidence()` and `get_latest_source_version()` to `backend/db/repositories.py` — exact
> signatures and validity-window semantics are in `docs/contracts/data-authorization.md` §4.1.
> Worth checking: `main`'s `analyse_competencies()` doesn't take role/designation parameters yet, so
> if your branch has role-aware targeting built against a different in-memory structure, this is the
> moment to point it at the real `RoleTarget` table instead before merging. Also, once you do add
> role parameters, please coordinate with Lane 5 so `routes/learning.py` actually forwards them from
> `LearnerProfile` — otherwise the new parameter exists but nothing ever calls it with real data. On
> `origin/codex/lane-3-competency/role-target-v1`: `backend/labs/sampling_lab.py`'s
> `evidence_payload(task_id)` is missing `player_id`, which `EvidenceRecordCreate` requires — worth
> fixing before wiring the lab to write real evidence.

## Lane 4 — Content AI, RAG & Evaluation

**A note on scope and sourcing:** `backend/ai/` on `main` is currently just an empty `__init__.py`
scaffold — none of the ingestion/retrieval/assistant/review-lifecycle claims below describe `main`
itself. An earlier draft of this guide stated a `backend/ai/grading.py` bug as if it were a fact
about the shared codebase without saying which branch it lived on; Codex flagged the ambiguity on
review (see `LANE2_SYNC.md`'s Package W entry), and on rechecking, the finding is real — it's just
scoped to `origin/codex/lane-4-content-ai/bootstrap`, your active working branch, not `main`. Every
branch-specific claim below now names its branch explicitly so this doesn't happen again.

**Lane 2 provides today:**
- `sha256` whole-file hashing on every upload (`LearningMaterial.sha256`, written in
  `routes/learning.py`) as your immutable file-level locator today.
- `models/governance.py`'s `SourceVersion` table (`material_id`, `version_number`, `sha256`,
  `locator`) plus Package W-A's `get_latest_source_version()` (see Lane 3's section above for the
  exact signature) — ready if/when you want chunk- or version-level persistence for whatever
  ingestion/retrieval pipeline lands on `main`.

**You provide:**
- A decision on whether `SourceVersion`/a new `Chunk`/`ReviewState` table shape should back your
  pipeline once it's merged. If yes, send the exact fields you need (chunk text length bound,
  locator shape, review-state enum values) as a contract-change proposal against
  `data-authorization.md` §7 and Lane 2 will add the migration.
- `routes/ai_real.py`'s Quest-mode fallback (when Gemini fails) returns a templated question
  (`f"Explain the concept of {topic} in {domain}."`) with no flag marking it as a fallback — worth
  tagging honestly the same way `quiz_generator.py` should distinguish an AI-grounded quiz from a
  locally-generated one, if/when that distinction is merged into `main`.
- **On `origin/codex/lane-4-content-ai/bootstrap`** (checked directly, not assumed):
  `backend/ai/grading.py` calls `json.loads()` with no `import json` anywhere in the file — a live
  `NameError` on the semantic-grading path, currently dormant only because no environment here has
  a real `GEMINI_API_KEY` set (run `database_status.py`'s `configured` section to check). Fix this
  before merging or before anyone configures a real key, whichever comes first, since it currently
  fails silently into the word-overlap fallback grader with no visible error.

**Route and DB usage:** Lane 2 does not own or gate any `/ai/*` route. If you persist chunks/review
state, use a `Session` the same way as every other lane — no direct engine access, no bypassing
`backend/schemas/**` at an HTTP boundary. Once Lane 5's auth dependency exists (see Lane 5's
section), derive tenant/user/role/reviewer identity from the verified principal rather than a
request-body field.

**Acceptance evidence Lane 2 will look for:** if you persist review state, a migration and a test
proving a role/tenant value can't be spoofed once Lane 5's dependency is attached to your routes.

**Copy-ready message:**
> If you want chunk/citation/review-state persistence for your ingestion/retrieval work, propose the
> exact schema against `docs/contracts/data-authorization.md` §7 and Lane 2 will add the migration —
> `SourceVersion` and Package W-A's `get_latest_source_version()` already give you a starting point
> for version-level locators. Separately: `routes/ai_real.py`'s Quest-mode fallback returns a
> templated question with no flag marking it as a fallback when Gemini fails — worth tagging
> honestly. On `origin/codex/lane-4-content-ai/bootstrap`: `backend/ai/grading.py` has a live
> `json.loads()` NameError with no `import json` — currently dormant only because no environment
> here has `GEMINI_API_KEY` set; worth fixing before merging or before anyone configures a real key.
> And once Lane 5 ships an auth dependency, please derive tenant/user/role/reviewer identity from
> the verified principal on `/ai/*` routes rather than trusting a request-body field.

## Lane 5 — Product API, Integrations & Analytics

**Lane 2 provides today, ready to attach:**
- `security/identity.py`: `OIDCVerifier`, `get_current_subject(authorization_header, verifier=None)`
  — real token verification, live-tested against Keycloak with JWKS rotation.
- `security/rbac.py`: `resolve_bound_principal()`, `require_permission()`,
  `scoped_to_own_player()`, the fixed permission matrix in `identity-authorization.md` §3-4.
- `db/repositories.py`: `get_latest_assessment()` and, as of Package W-A (commit `3a75b28`,
  accepted), `get_current_role_target()`, `get_latest_evidence()`, `get_latest_source_version()` —
  see Lane 3's section above for signatures. None of these authorize a caller by themselves; see the
  security boundary note below.
- `backend/scripts/database_status.py` (Package W-B, this package) — run it in CI with
  `--check-migrations` to fail a deploy step before a route ever executes against a stale schema.
- `backend/routes/authorization.py` (Lane 5 PR #2 plus Lane 2 Package 3 review/fix): stable,
  sanitized HTTP adapters for verified principals, deployment-tenant scope, fixed permissions and
  own-player object scope. `require_own_player_dependency(permission)` is the exact dependency for
  a route whose path parameter is named `player_id`.

**What is now attached:** Lane 5 PR #2 protects `GET /learning/admin/overview` with organization
analytics permission and `GET /learning/assessment/{player_id}/latest` with assessment-read
permission. Package 3 makes the latter use the composed own-player dependency rather than a manual
handler check, and proves dependency overrides cannot bypass the separately composable
deployment-tenant layer. This protects exactly those two routes, not the rest of the API.

**You provide:**
- Attach `require_permission_dependency()` or `require_own_player_dependency()` to every remaining
  protected route with a route-specific permission/object contract; protection does not propagate
  from the two routes already wired.
- Bring `GET /learning/assessment/{player_id}/latest` fully into conformance with
  `data-authorization.md` §4: the current route uses the correct repository and authorization but
  still nests the row, omits `recommended_course_ids`, and returns HTTP 200/null rather than the
  contracted 404 for an empty stream.
- If/when Lane 3 merges role-aware targeting into `analyse_competencies()`, forward the
  corresponding `LearnerProfile` fields from `routes/learning.py`'s assessment/pathway handlers —
  today that function only accepts `experience_level`, so there's nothing to forward yet, but this
  is exactly the kind of wiring step that's easy to silently skip once the parameter exists.
- Never accept `tenant_id`, `role`, `reviewer_id` or `actor` from a request body once a verified
  principal exists — derive them, per `identity-authorization.md` §4's object/function
  authorization table. This applies to any new route you or Lane 4 add, since there is no auth
  layer wired into any existing route yet either.

**Route and DB usage:** every repository function above takes a `Session` from your route's own
`Depends(get_db)` — you already do this correctly in existing routes. The security boundary is
explicit in every one of these functions' docstrings: accepting a `player_id`/`role`/`material_id`
argument proves nothing about the caller. You must verify the token, resolve the bound principal,
check the permission, and enforce object/tenant scope **before** calling any repository function —
the function itself will happily return data for whatever key you pass it.

**Acceptance evidence Lane 2 will look for:** negative tests (401 with no/invalid token, 403 with a
valid token lacking permission) on every newly protected route; `database_status.py
--check-migrations` wired into your deploy/CI step exits 0.

**Copy-ready message:**
> The composed route dependencies now exist in `backend/routes/authorization.py`, and the first two
> routes are attached: organization-admin `GET /learning/admin/overview` and learner-owned
> `GET /learning/assessment/{player_id}/latest`. For every remaining route, use
> `require_permission_dependency()` or `require_own_player_dependency()` rather than hand-mapping
> policy errors. Please also align the latest-assessment response with
> `docs/contracts/data-authorization.md` §4: include all eight fields, return 404 for an empty
> stream, and use the contracted response shape. Whenever Lane 3 merges role-aware targeting into
> `analyse_competencies()`, please make sure `routes/learning.py`'s assessment/pathway handlers
> actually forward the new parameters from `LearnerProfile` — that's the kind of wiring step that's
> easy to silently skip. Run `backend/scripts/database_status.py --check-migrations` in your deploy
> step so a stale schema fails before a route runs against it.

## Lane 6 — Quality, Security, Release & Evidence

**Lane 2 provides today:**
- `backend/scripts/backup_restore.py` (drilled and passing), a retention-enforcement job that's a
  provable no-op today (no cited maximum retention exists yet) but is tested against a real
  concurrency race and fixed, and `security/encryption.py` (ready, unused since no field needs it
  yet). None of this is a production DR plan.
- `backend/scripts/database_status.py` (this package) — a fast, privacy-safe way to confirm a fresh
  clone/CI runner's database is at head and which optional integrations are configured, without
  writing a throwaway script per lane every time someone asks "is the DB set up right."

**You provide:**
- A CI step running the full backend suite against both SQLite and the Compose PostgreSQL container
  on every PR, not per-lane locally.
- `database_status.py --check-migrations` wired into that CI step (or an equivalent gate) so a
  migration drift fails loudly instead of surfacing later as a confusing runtime error.
- A merge-queue rule that a PR adding a protected route without a 401/403 test doesn't merge, once
  Lane 5 starts attaching real auth (see Lane 5's section).
- A decision (or an escalation to whoever's accountable) on whether the CERT-In 180-day audit-event
  retention citation applies to this specific deployment — flagged `BLOCKED-EXTERNAL/LEGAL` in
  `SIH26101_MASTER_CHECKLIST.md`; nothing in the retention job can move until this resolves.

**Route and DB usage:** none directly — your interface into Lane 2 is the test suite and
`database_status.py`, not the models/routes themselves.

**Acceptance evidence Lane 2 will look for:** a CI run log showing `database_status.py
--check-migrations` as a named step, not just "tests passed."

**Copy-ready message:**
> `backend/scripts/database_status.py --json` gives you a privacy-safe, single-command way to check
> any environment's migration state and which optional integrations (`OIDC_ISSUER`,
> `GEMINI_API_KEY`, etc.) are configured, without ever printing a secret value — worth wiring into
> CI with `--check-migrations` so schema drift fails the build instead of surfacing as a confusing
> runtime error later. Please also add the merge-queue rule that a new protected route needs a
> 401/403 test once Lane 5 starts attaching real auth, and escalate the CERT-In retention-citation
> question — it's the one thing blocking Lane 2's retention job from ever doing more than a
> documented no-op.

## Summary table

| Lane | Lane 2 already provides | Biggest single unblock |
|---|---|---|
| 1 | `preferred_mode` field; exact browser-login spec | A route to read/write `preferred_mode` (Lane 5) |
| 3 | `RoleTarget`/`EvidenceRecord` tables; Package W-A's read facade | Merge role-aware targeting against the real table, then coordinate the `routes/learning.py` wiring with Lane 5 |
| 4 | `SourceVersion` table; whole-file `sha256` | A schema proposal if persistence beyond process-memory is wanted |
| 5 | `OIDCVerifier`, RBAC functions, `get_latest_assessment` | A single composed auth `Depends(...)` (ask Lane 2 to prioritize) |
| 6 | Backup/restore, retention job, `database_status.py` | CI wiring `--check-migrations` as a named, gating step |
