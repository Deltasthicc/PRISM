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
alembic upgrade head first"`). It never accepts a player ID, a free-text filter, or anything else
that could be pointed at one subject — see `backend/scripts/database_status.py`'s module docstring
and `backend/tests/test_core_database_status.py` for the exact, tested privacy boundary. If your
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

**Lane 2 provides today:**
- `models/governance.py`'s `RoleTarget` table (`framework_version`, `role`, `competency_id`,
  `target_level`, `source`, `approved_by`, `valid_from`/`valid_to`) — the versioned, sourced
  replacement for `EXPERIENCE_TARGET_CAP`/`ROLE_TARGET_OVERRIDES`.
- `models/governance.py`'s `EvidenceRecord` table (`evidence_id`, `player_id`, `competency_id`,
  `evidence_type` from `EVIDENCE_TYPES`, `value`, `detail`, `recorded_at`) for separating evidence
  by type, per `SIH26101_MASTER_CHECKLIST.md` §4.1's ask.
- **Package W-A** (Codex, in review as of this writing — check `LANE2_SYNC.md`'s Package W entry
  for its accepted commit hash before depending on it in production code) adds three read-only
  repository functions to `backend/db/repositories.py`:
  ```python
  get_current_role_target(db, role, competency_id, *, as_of=None)   # exact-role lookup, half-open validity window
  get_latest_evidence(db, player_id, competency_id, evidence_type)  # one evidence type, newest row
  get_latest_source_version(db, material_id)                        # highest version_number for one material
  ```
  `get_current_role_target` is an **exact** `(role, competency_id)` match at one instant — it does
  not normalize aliases, pick among `job_role`/`designation`/`department`, or fall back to a
  role-agnostic default. That precedence logic is explicitly left to you; see
  `docs/contracts/data-authorization.md` §4.1 once W-A lands for the exact tie-breaking rules.

**You provide:**
- The actual migration off `ROLE_TARGET_OVERRIDES`/`EXPERIENCE_TARGET_CAP` to
  `get_current_role_target()`, including your own precedence/fallback policy on top of the exact
  lookup Lane 2 provides.
- `services/learning_engine.py`'s `resolve_role_target()` currently receives `job_role`,
  `designation`, `department`, `current_assignment` from `analyse_competencies()`'s own parameters
  — but `routes/learning.py` (Lane 5-owned) never forwards them from the loaded `LearnerProfile`.
  This is Lane 5's fix, not yours, but flag it explicitly rather than assuming it's already wired —
  it currently is not, so every real user gets curriculum-default targeting today regardless of
  what your role-target code can do.
- `backend/labs/sampling_lab.py`'s `evidence_payload()` currently returns
  `{competency_id, evidence_type, value, detail}` — missing `player_id`, which
  `EvidenceRecordCreate` requires. Add it before wiring the lab to write real evidence rows, or the
  write will fail Pydantic validation.

**Route and DB usage:** call the repository functions above from your own service code
(`services/learning_engine.py`, `backend/labs/**`) with a `Session` passed in from whichever route
calls you — never open your own engine/session. These functions return raw ORM rows, not API
responses; serialize through `backend/schemas/**` (Lane 2-owned) at any HTTP boundary, never return
an ORM object directly from a route.

**Acceptance evidence Lane 2 will look for:** a test proving `analyse_competencies()` output changes
when `get_current_role_target()` returns a real row vs. `None`; the lab's evidence payload
validating against `EvidenceRecordCreate` without modification.

**Copy-ready message:**
> Lane 2 (with Codex's Package W-A, check `LANE2_SYNC.md` for its accepted commit before relying on
> it) is adding `get_current_role_target()`, `get_latest_evidence()` and `get_latest_source_version()`
> to `backend/db/repositories.py` — exact signatures and validity-window semantics are in
> `docs/contracts/data-authorization.md` §4.1. Please plan the migration off
> `ROLE_TARGET_OVERRIDES`/`EXPERIENCE_TARGET_CAP` once that lands. Separately and not blocked on
> W-A: your sampling lab's `evidence_payload()` is missing `player_id`, which
> `schemas/governance.py`'s `EvidenceRecordCreate` requires — worth fixing before wiring the lab to
> write real evidence. And please raise with Lane 5 that `routes/learning.py` never forwards
> `job_role`/`designation`/`department`/`current_assignment` into `analyse_competencies()` today —
> your role-aware targeting code is real but currently unreachable by any live user for that reason.

## Lane 4 — Content AI, RAG & Evaluation

**Lane 2 provides today:**
- `sha256` whole-file hashing on every upload (`LearningMaterial.sha256`, written in
  `routes/learning.py`) as your immutable file-level locator today.
- `models/governance.py`'s `SourceVersion` table (`material_id`, `version_number`, `sha256`,
  `locator`) plus Package W-A's `get_latest_source_version()` (see Lane 3's section above for the
  exact signature) — ready if/when you want chunk- or version-level persistence instead of
  process-memory (`InMemoryChunkStore`).

**You provide:**
- A decision on whether `SourceVersion`/a new `Chunk`/`ReviewState` table shape should replace the
  current in-memory store before a pilot. If yes, send the exact fields you need (chunk text length
  bound, locator shape, review-state enum values) as a contract-change proposal against
  `data-authorization.md` §7 and Lane 2 will add the migration.
- `routes/ai_real.py`'s Quest-mode fallback (when Gemini fails) returns a templated question with no
  flag marking it as a fallback, unlike your own quiz-path `generation_mode` tagging — worth
  aligning for the same reason you built the honest one.
- The live `ai/grading.py` bug independent of anything Lane 2 owns: it calls `json.loads()` with no
  `import json` in the file. It's dormant only because no `GEMINI_API_KEY` is configured in most
  local environments — run `database_status.py` (see the "How to check your own setup" section
  above) to see at a glance whether a given environment has that key set, since that's exactly the
  condition under which this bug goes live.

**Route and DB usage:** Lane 2 does not own or gate any `/ai/*` route. If you persist chunks/review
state, use a `Session` the same way as every other lane — no direct engine access, no bypassing
`backend/schemas/**` at an HTTP boundary. Several `/ai/*` routes currently accept `tenant_id`,
`user_id`, `roles`, and `reviewer_id` directly from the request body — once Lane 5's auth dependency
(see Lane 5's section) exists, derive these from the verified principal instead; don't keep trusting
client-supplied identity once there's something better to call.

**Acceptance evidence Lane 2 will look for:** if you persist review state, a migration and a test
proving a role/tenant value can't be spoofed once Lane 5's dependency is attached to your routes.

**Copy-ready message:**
> If you want chunk/citation/review-state persistence instead of process-memory, propose the exact
> schema against `docs/contracts/data-authorization.md` §7 and Lane 2 will add the migration —
> `SourceVersion` and Package W-A's `get_latest_source_version()` already give you a starting point
> for version-level locators. Separately: `ai/grading.py` has a live `json.loads()` NameError with
> no `import json` — currently dormant only because no environment here has `GEMINI_API_KEY` set;
> worth fixing before anyone configures a real key. And once Lane 5 ships an auth dependency, please
> stop accepting `tenant_id`/`user_id`/`roles`/`reviewer_id` from request bodies on `/ai/*` routes —
> right now any caller can self-declare any of them.

## Lane 5 — Product API, Integrations & Analytics

**Lane 2 provides today, ready to attach:**
- `security/identity.py`: `OIDCVerifier`, `get_current_subject(authorization_header, verifier=None)`
  — real token verification, live-tested against Keycloak with JWKS rotation.
- `security/rbac.py`: `resolve_bound_principal()`, `require_permission()`,
  `scoped_to_own_player()`, the fixed permission matrix in `identity-authorization.md` §3-4.
- `db/repositories.py`: `get_latest_assessment()` (implemented) and, pending Package W-A's review,
  `get_current_role_target()`, `get_latest_evidence()`, `get_latest_source_version()` — see Lane 3's
  section above for signatures. None of these authorize a caller by themselves; see the security
  boundary note below.
- `backend/scripts/database_status.py` (Package W-B, this package) — run it in CI with
  `--check-migrations` to fail a deploy step before a route ever executes against a stale schema.

**What Lane 2 still needs to build for you (flagging, not yet shipped):** a single composed
FastAPI dependency chaining token-verify → resolve-principal → permission-check into one
`Depends(...)`, so protecting a route doesn't require hand-chaining four function calls per route.
This does not exist yet — today you would have to chain `get_current_subject` →
`resolve_bound_principal` → `require_permission` manually in every route. If this would unblock you
sooner, say so and Lane 2 will prioritize it; otherwise treat the three functions above as the
current building blocks.

**You provide:**
- Attach real auth to `GET /learning/admin/overview` first — its "not production-secure" banner is
  accurate today; it depends only on `get_db`, no identity or permission check.
- Implement `GET /learning/assessment/{player_id}/latest` per `data-authorization.md` §4 — the
  query is already written (`get_latest_assessment()`); this is route wiring only, not new logic.
- Fix `routes/learning.py`'s assessment/pathway handlers to forward `job_role`/`designation`/
  `department`/`current_assignment` (already loaded from `profile` in the same function) into
  `analyse_competencies()` — currently only `experience_level` is passed, silently making Lane 3's
  role-aware targeting inert for every real user.
- Never accept `tenant_id`, `role`, `reviewer_id` or `actor` from a request body once a verified
  principal exists — derive them, per `identity-authorization.md` §4's object/function
  authorization table. Several `/ai/*` routes (Lane 4-owned, flagged in their section above) and
  none of your own currently do this correctly either way, since there is no auth layer at all yet.

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
> Everything you need to protect a route already exists as separate functions:
> `security.identity.get_current_subject`, `security.rbac.resolve_bound_principal`,
> `security.rbac.require_permission` — chain them in a dependency and attach it to
> `GET /learning/admin/overview` first, since its "not production-secure" banner is currently
> accurate. If hand-chaining three functions per route is the blocker, tell Lane 2 and a single
> composed dependency will get prioritized. Please also implement
> `GET /learning/assessment/{player_id}/latest` — the query is already written
> (`db.repositories.get_latest_assessment`) — and fix `routes/learning.py`'s assessment/pathway
> handlers to forward the profile's role fields into `analyse_competencies()`, which today silently
> makes Lane 3's role-aware targeting dead code for every real user. Run
> `backend/scripts/database_status.py --check-migrations` in your deploy step so a stale schema
> fails before a route runs against it.

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
| 3 | `RoleTarget`/`EvidenceRecord` tables; Package W-A's read facade | Role fields never reach `analyse_competencies()` (Lane 5's fix) |
| 4 | `SourceVersion` table; whole-file `sha256` | A schema proposal if persistence beyond process-memory is wanted |
| 5 | `OIDCVerifier`, RBAC functions, `get_latest_assessment` | A single composed auth `Depends(...)` (ask Lane 2 to prioritize) |
| 6 | Backup/restore, retention job, `database_status.py` | CI wiring `--check-migrations` as a named, gating step |
