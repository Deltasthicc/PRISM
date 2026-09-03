# Data, subject and tenant authorization contract

Owner: Lane 2 (Core Platform, Identity & Data)

Consumers: Lanes 3, 4, 5, 6

Change approval: Lanes 5 and 6 (`SIH26101_TEAM_ORCHESTRATION.md` section 4)

Status: **v1 demo contract — storage and query semantics, internal subject-data export/deletion
primitives, and PostgreSQL backup/restore are defined and independently reviewed/accepted. A
retention-enforcement job (a real no-op today, no cited maximum exists) is implemented and has
passed its adversarial contract plus Codex's final immutable PostgreSQL re-review. Authentication
and RBAC primitives exist (`docs/contracts/identity-authorization.md`) and are now composed into
exactly two Lane 5 routes: the organization-admin overview and learner-owned latest-assessment
read. Remaining product routes, multi-tenant isolation and subject-rights HTTP APIs are not
implemented.**

This contract is deliberately explicit about the present boundary. It is safe guidance for the
local hackathon demo, not evidence of production authorization or compliance.

## 1. Tenant semantics today

A **tenant is one application deployment backed by one database**. The SQLite demo database
(`backend/app.db`, unless `DATABASE_URL` overrides it) is one tenant. A PostgreSQL database named
by one deployment's `DATABASE_URL` is likewise one tenant.

There is currently:

- no `tenant_id` column on `players`, learner records, content records, evidence records or audit
  events;
- no tenant identifier accepted in an HTTP path, query, header or body;
- no row-level tenant filter; and
- no supported way to place two organizations in the same database and isolate them.

Therefore tenant scope is the database selected by the server, never a value supplied by the
caller. Until server-derived tenant identity and `tenant_id` migrations exist, every deployed
database must contain data for at most one organization. Lanes 3-5 must not describe the current
schema as multi-tenant, add a client-selected tenant parameter, or infer an organization from
free-text profile fields such as `department`.

The future multi-tenant rule is reserved now so implementations do not diverge: an authenticated
server-side identity will resolve an immutable tenant key, and every tenant-owned query will
include `tenant_id = :server_tenant_id`. The key must not be taken from request data. Adding that
key, backfilling existing rows and defining privileged cross-tenant operations requires a reviewed
contract change and migration; it is not part of v1.

## 2. Subject and authorization semantics today

`players.player_id` is the learner-record key. It is **not an authenticated subject**. Most current
routes still take `player_id` from the URL or form data, and the username-only demo flow does not
create a server-derived session or token. Possession of a `player_id` therefore proves neither
identity nor permission. The protected latest-assessment route is the narrow exception: it resolves
an OIDC subject through an active local binding and compares the path key with the bound player.

Consequences for every lane:

- Current `/learning/profile/{player_id}`, `POST /learning/assessment/{player_id}`,
  `/learning/pathway/{player_id}` and quiz routes are local-demo interfaces only.
- `GET /learning/admin/overview` now requires organization-analytics permission and the
  deployment-database tenant check; its response remains aggregate-only.
- `GET /learning/assessment/{player_id}/latest` now requires assessment-read permission and
  own-player scope through the locally persisted binding.
- No route may be called production-secure merely because it filters on `player_id`.
- New privileged or cross-learner routes must wait for OIDC/session identity, server-derived
  subject binding and RBAC, or explicitly remain disabled outside the demo profile.
- Half A's `AuditEvent` write path supplies an append-only record shape; it does not itself grant
  access or make the existing routes audited.

The OIDC/RBAC primitives and route handoff are specified separately in
`docs/contracts/identity-authorization.md`. Lane 5 must compose token verification, active local
binding, permission and object-scope checks independently for every additional protected route;
protection of the two routes above does not transitively protect the rest of the API.

## 3. Assessment record contract

`competency_assessments` is an append-only sequence of assessment snapshots. Creating an
assessment inserts a new row; consumers must not update an older row to represent a rerun.

The canonical stored and read shape is:

| Field | Type | Meaning |
|---|---|---|
| `assessment_id` | string UUID | Unique snapshot ID and deterministic final tie-breaker. |
| `player_id` | string | Learner-record key; must reference `players.player_id`. |
| `curriculum_slug` | string | Exact canonical curriculum slug assessed. |
| `self_ratings` | JSON object `{competency_id: number}` | Submitted 0-5 ratings for this run. |
| `measured_scores` | JSON object `{competency_id: number}` | 0-5 measurements captured when this row was created. |
| `skill_gaps` | JSON array | Gap result captured when this row was created. |
| `recommended_course_ids` | JSON array of strings | Course IDs captured when this row was created. |
| `created_at` | UTC datetime | Snapshot creation time. Legacy/null values sort older than every timestamped row. |

JSON fields return `{}` or `[]`, never `null`, at a consumer boundary. Unknown competency IDs are
not silently mapped to a different curriculum. An assessment belongs to exactly one
`(deployment tenant, player_id, curriculum_slug)` stream.

`LearnerProfile` has different semantics: there is exactly one mutable row per `player_id`,
enforced by its unique index, and `updated_at` identifies its latest edit. It is not currently a
versioned history. Learning materials and generated quizzes are separate append-only records and
must remain filtered by `player_id` within the deployment tenant.

## 4. Exact “latest assessment” rule

For one learner and one curriculum, **latest** means the single row ordered by:

1. non-null `created_at` before null `created_at`;
2. `created_at` descending; then
3. `assessment_id` descending using the database's ordinary string ordering.

The portable query contract is:

```sql
SELECT assessment_id, player_id, curriculum_slug,
       self_ratings, measured_scores, skill_gaps,
       recommended_course_ids, created_at
FROM competency_assessments
WHERE player_id = :player_id
  AND curriculum_slug = :curriculum_slug
ORDER BY CASE WHEN created_at IS NULL THEN 1 ELSE 0 END ASC,
         created_at DESC,
         assessment_id DESC
LIMIT 1;
```

The tenant predicate is implicit in v1 because the connection selects the deployment's one
database. After multi-tenant columns exist, `tenant_id = :server_tenant_id` is an additional
mandatory predicate, not a replacement for either key above.

For a set of learners, use the same ordering with
`ROW_NUMBER() OVER (PARTITION BY player_id, curriculum_slug ORDER BY ...) = 1`. Do not use
`MAX(created_at)` and join back without the `assessment_id` tie-breaker, and do not aggregate all
historical assessment rows as though they represented distinct learners.

The contracted HTTP read interface is:

```text
GET /learning/assessment/{player_id}/latest?curriculum_slug={canonical_slug}
```

It must return the eight fields in the table above, with `created_at` as an RFC 3339 UTC string, or
404 when that stream has no assessment. Lane 5 PR #2 implemented and protected the route using Lane
2's shared `get_latest_assessment()` repository function, but its current response is not yet fully
contract-conformant: it nests the row under `assessment`, omits `recommended_course_ids`, and
returns a null assessment with HTTP 200 instead of 404. That Lane 5 response-shape correction is
tracked explicitly rather than hiding the difference in this storage contract.

The existing `GET /learning/pathway/{player_id}?curriculum_slug=...` is a derived view: it takes
`self_ratings` from the latest snapshot but intentionally recomputes measured scores from current
`AccuracyHistory`. It is not a verbatim read of the stored latest assessment. Lane 5 PR #2 changed
this route to use `get_latest_assessment()`, so its stored-snapshot selection now follows the same
null and `assessment_id` tie-breakers as this contract.

### 4.1 Shared read repository interface for Lanes 3–5

`backend/db/repositories.py` is the canonical storage-read facade for ordering and validity rules
that more than one lane consumes. It now exposes these four functions:

```python
get_latest_assessment(db, player_id, curriculum_slug)
get_current_role_target(db, role, competency_id, *, as_of=None)
get_latest_evidence(db, player_id, competency_id, evidence_type)
get_latest_source_version(db, material_id)
```

These functions return SQLAlchemy model rows or `None`; they never commit, mutate, authorize or
serialize. Callers must use the response schemas in `backend/schemas/**` at an HTTP boundary and
must not return unrestricted ORM objects directly.

`get_current_role_target` performs an **exact** `(role, competency_id)` lookup at a timezone-aware
instant. A target is eligible only during the half-open interval
`valid_from <= as_of < valid_to`; null `valid_to` means no scheduled end, while null `valid_from`
is ineligible because its effective start cannot be established. Overlaps resolve by newest
`valid_from`, then non-null/newest `created_at`, then descending `target_id`. It deliberately does
not normalize aliases, choose among profile fields or fall back to role `"*"`: those are Lane 3
policy decisions. `approved_by=None` is returned honestly rather than silently promoted to an
approved target; the consumer must display/enforce authoring status appropriate to its flow.

`get_latest_evidence` accepts only the storage vocabulary in
`models.governance.EVIDENCE_TYPES`. It isolates by exact player, competency and evidence type,
then orders non-null `recorded_at` first/newest and `evidence_id` descending. This supplies one
observation, not a blended competency score. Weighting self-report, diagnostic,
observed-practice, reviewer and provider-imported evidence remains Lane 3's versioned policy.

`get_latest_source_version` isolates by exact `material_id`, orders highest `version_number`
first, then non-null/newest `created_at`, then descending `source_version_id`. A duplicate version
number is made deterministic but is not thereby declared valid, approved or safe for retrieval.
Lane 4 remains responsible for ingestion, chunking, approval and citation policy.

**Security boundary:** accepting a `player_id`, `role` or `material_id` argument proves nothing
about the caller. Before invoking a repository read, a Lane 5 route must verify the token, resolve
an active local binding, require the relevant permission, and enforce own-player/content scope as
specified in `identity-authorization.md`. Tenant scope still comes only from the server-selected
deployment database. A browser-supplied tenant, role, reviewer or player identifier must never be
converted into authority merely because one of these queries accepts the same value as a lookup
key.

## 5. Aggregate rules for Lanes 4 and 5

“Assessments completed” may count snapshot rows when the metric is explicitly labeled as runs.
“Learners assessed”, “current gap”, “top current skill gaps” and similar current-state metrics
must first select the latest row per `(player_id, curriculum_slug)`, then aggregate. A learner may
contribute once per curriculum to a current-state curriculum breakdown. Cross-curriculum totals
must retain the curriculum dimension or explicitly document their deduplication rule.

Aggregate responses must not include learner profile text, raw self-ratings, uploaded excerpts,
individual evidence, `player_id`, or small-cell drill-downs until Lane 5 defines and enforces the
RBAC and disclosure policy.

## 6. Retention, export and deletion reality

`security.data_rights` now provides internal, database-transaction primitives for a verified
operator to inventory/export or delete one `players.player_id`. They are intentionally **not HTTP
endpoints**. The product still cannot authenticate a subject or operator, derive an actor from a
trusted session, or authorize either operation. A route must not accept `actor`, tenant or
authority from request data and pass it through. Until identity and RBAC land, callers are limited
to trusted offline/administrative code using a dedicated database session.

### 6.1 Export contract

`export_subject_data(db, player_id, actor=..., reason=...)` returns
`subject-data-export-v2`, a JSON-serializable object with:

- `generated_at`, `tenant_scope="deployment-database"`, `player_id` and the created
  `audit_event_id`;
- `records`, keyed by the exact inventory below, with rows ordered by primary key (audit rows by
  `created_at`, then `audit_id`);
- `record_counts`, including the export audit event itself; and
- `retention_classification`, using the classifications in section 6.3.

The subject-owned inventory is `players`, `learner_profiles`, `competency_assessments`,
`evidence_records`, `accuracy_history`, `game_sessions`, `submissions`, `learning_materials`,
`generated_quizzes`, `source_versions` linked through the subject's materials, and the local
`identity_bindings` row linked to that player. The export also
contains the subject's entries from `guilds.raid_topic_assignments` as
`guild_topic_assignments`, and related `audit_events` where the subject is the actor or the event's
`entity_type="player"` / `entity_id` matches. Shared curriculum/game content (`dungeons`, `rooms`,
`questions`, guild definitions and `role_targets`) is not subject-owned and is not exported.

Version 2 adds `identity_bindings`; consumers of the earlier internal v1 draft must not assume the
record inventory is unchanged.

A successful export appends `subject_data.export` to `audit_events` in the same transaction. An
unknown player or invalid actor/reason writes no event. This is a machine-readable portability
primitive, not a claim that a legally sufficient access/portability workflow exists.

### 6.2 Verified deletion contract

`delete_subject_data(db, player_id, actor=..., reason=..., confirmation=...)` requires
`confirmation` to equal `player_id` exactly. It deletes the eleven subject-owned table groups listed
above, scrubs the player's keys from every `guilds.raid_topic_assignments` JSON object, and retains
shared content and other players' rows. It also retains all `audit_events` as the explicit
append-only security-log exception and appends `subject_data.delete` atomically with the deletion.

The operation first rejects an unknown subject and rejects a corrupt/cross-owner graph where
another player's generated quiz references material owned by the deletion subject. Any error
rolls back the audit event, JSON scrubs and row deletions together. `deleted_counts` is built from
each `DELETE` statement's own returned rowcount, not a pre-delete snapshot — a snapshot taken
before the deletes run could under-report if a row for this player (e.g. their own in-flight game
activity) is written concurrently; every `DELETE` still filters by `player_id`, so the row is
correctly removed either way, but a snapshot-based count would have misreported it. The result
reports exact deleted counts, guild assignments scrubbed, retained related-audit count and the
deletion audit ID. Database backups or external replicas are outside this primitive and are not
erased by it.

### 6.3 Retention classification and policy (Package L)

The code classifies the eleven subject-owned table groups as
`delete_with_verified_subject_request`, guild assignment entries as
`scrub_with_verified_subject_request`, and audit events as
`retain_append_only_security_log_duration_policy_pending`. `security.retention.RETENTION_POLICIES`
adds, for each classification, whatever is actually known about a **minimum** retention floor (a
cited reason not to delete too early) and a **maximum** retention ceiling (a cited reason not to
keep forever). Today that is exactly one fact, not a full schedule:

- **Audit events** have a cited 180-day *minimum* — CERT-In Directions under section 70B — which
  `delete_subject_data()` already satisfies trivially by never deleting an audit row at all. No
  maximum retention for audit events is cited from any source; do not add an expiry job that
  deletes them after any duration until a real maximum is sourced and approved. The CERT-In
  citation's applicability to *this specific deployment* is not itself confirmed — see
  `SIH26101_MASTER_CHECKLIST.md` line 181, `BLOCKED-EXTERNAL/LEGAL`.
- **Subject-owned and guild-scrub categories** have no cited minimum or maximum. "Retention" for
  them today is the verified-subject-request boundary itself (`export_subject_data`/
  `delete_subject_data`), not a schedule.

On PostgreSQL, `audit_events` rows are additionally protected against in-place mutation at the
database level, but the genuine append-only guarantee — rows are never removed except through the
dedicated retention job — remains an application-layer property, not a database one. Migration
`036de46dd515` (Package U) originally added a trigger rejecting both `UPDATE` and `DELETE`
unconditionally; Codex's cold immutable audit (`LANE2_SYNC.md`, 2026-09-01) found this directly
broke `scripts/retention_job.py`, whose only registered category is `audit_events` — the moment any
maximum retention is ever cited for that category, the retention job's own `DELETE` would be
rejected by its own project's trigger. Follow-up migration `4631f204d4ba` (Package V) retired only
the `DELETE` rejection: PostgreSQL now rejects `UPDATE` against `audit_events` (naming this
precisely — an UPDATE-only trigger is not "append-only"; nothing in this project ever needs to
update an existing audit row, so this closes a real gap with no cost), while `DELETE` remains
possible and is governed entirely by `scripts/retention_job.py` under a cited, minimum-retention-
checked maximum, exactly like every other category. The database owner role can still
`ALTER TABLE ... DISABLE TRIGGER` to bypass the `UPDATE` rejection (live-verified, and re-enabled,
only to clean up a test drill's own synthetic rows) — this remains a bug-catching safety net for
the application's own connection role, not a security boundary against someone holding those same
credentials, and not a compliance claim. A second external audit proposed a broader version (full
audit triggers across tables with captured actor/purpose context); that version was rejected
because it would need session-context plumbing that does not exist and would misrepresent what a
trigger the app's own role can disable actually proves — see `LANE2_SYNC.md` for the full technical
reasoning on both the original scoping (Package U) and the cross-package conflict/fix (Package V).

`security.retention.assert_minimum_retention_satisfied()` is a guard for whatever automated
deletion is built *next* (an expiry job, a cleanup script) — it refuses to let such code delete a
row younger than its cited floor. It is not itself a job, a schedule, or a claim that automated
retention enforcement exists.

`backend/scripts/retention_job.py` (Package P) is that job. It is dry-run by default (`--apply`
required to actually delete), only ever acts on a category with a cited **maximum**, and calls
`assert_minimum_retention_satisfied()` on every candidate row as a defense-in-depth check before
deleting. Run against the real registry today it is a **provable no-op** — no category has a cited
maximum, so `enforce_maximum_retention()` returns zero candidates and deletes nothing; this was
confirmed both by a dedicated unit test and by running the CLI live against the real PostgreSQL
container with `--apply` and confirming zero rows were touched and zero
`retention_job.enforce_maximum` audit events were written. The deletion mechanism itself is proven
separately against a synthetic, clearly-labelled test-only policy — never against the real
registry — so this document is not claiming a real ceiling exists anywhere it doesn't.
`delete_with_verified_subject_request` and `scrub_with_verified_subject_request` are intentionally
excluded from this job's table mapping: those categories are defined as request-only deletion, and
this job must refuse rather than start silently applying an age-based schedule to them.

Concurrent PostgreSQL `--apply` runs atomically claim their own batch via `FOR UPDATE SKIP LOCKED`
(never locking a lookahead row beyond the batch actually being processed), so N workers partition
real work into disjoint row sets instead of colliding on the same unlocked candidates. This closes a
real defect an independent live drill reproduced: without locking, 4 concurrent workers against 11
expired rows all read the same batch and only 3 rows were ever actually deleted, leaving 8
unprocessed. A follow-up live drill under the identical scenario (11 expired + 2 young rows, 4
concurrent workers, batch size 3) confirmed the fix: disjoint per-worker deletions, a union of
exactly the 11 expired IDs, a durable audit-event deleted-count sum of 11, both young rows
untouched, and a clean `0/0` final rerun with no misleading audit event. See `LANE2_SYNC.md`'s
Activity log for exact evidence. The production fix and its forced-contention/cleanup regression
contract are independently accepted; this remains local PostgreSQL evidence, not a production
operations or compliance claim.

### 6.4 PostgreSQL backup/restore (Package L)

`backend/scripts/backup_restore.py` provides `create_backup()`/`restore_backup()`, both shelling
out to `docker exec`/`docker cp` against the named running Postgres container (this host has no
local `pg_dump`/`pg_restore`; the container does). A full drill — insert marker rows, back up,
delete the rows to simulate loss, restore, confirm the rows and the rest of the schema (18 tables,
Alembic head unchanged) came back exactly — was run and passed; see `LANE2_SYNC.md`'s Activity log
for the exact evidence. This proves the mechanism works against the current local dev container. It
is **not** a disaster-recovery plan: there is no backup schedule, no offsite/encrypted storage, no
retention policy for backup files themselves, and no restore runbook for a real incident. Those
remain Lane 6 deployment/DR work.

Deleting the local SQLite demo database remains a whole-tenant reset, not a subject workflow.
Replica handling remains an unverified backlog item. `backend/security/encryption.py` (Package Q,
`docs/contracts/encryption-key-ownership.md`) is a real, tested, versioned authenticated-encryption
envelope — not KMS-style per-record data-key wrapping. As of this update no field in `models/**`
stores a password, API key or client secret, so no current model uses it; it exists ready for the
day one is needed. Local HTTP/PostgreSQL traffic and storage/backups are not encrypted by this
module, Python key bytes cannot be reliably zeroized, and production KMS/HSM key custody remains
external and unimplemented. Lanes must not claim compliance or production subject-rights/DR
controls based on these internal primitives alone.

## 7. Change process

Any lane needing a new field, alternate latest-record ordering, tenant representation or
authorization rule opens a contract-change proposal against this file
(`SIH26101_TEAM_ORCHESTRATION.md` section 8, “Cross-lane handoff”) instead of editing Lane 2's
models or silently inventing query semantics. The proposal must identify required migrations,
backfill behavior, consumers, tests and rollback impact.

## 8. Learning mode scaffold (professional vs. quest)

`players.preferred_mode` (migration `640603a37f2f`, `models/enums.py`'s `LearningMode`) records
which experience surface a learner is currently associated with: `"professional"` (the default —
the non-gamified, KCM/Mission Karmayogi-oriented base product for government-official learners) or
`"quest"` (the existing optional dungeon/XP/combat layer, an explicit opt-in per the team's own
recorded decision — see `SIH26101_MASTER_CHECKLIST.md` and `SIH26101_WINNING_PLAYBOOK.md` — never
the default a learner lands in). New rows default to `"professional"` at both the ORM (`default=`)
and database (`server_default`) level; a `CHECK` constraint (`ck_players_preferred_mode_known_value`,
declared identically in the model's `__table_args__` and the migration so `alembic check` and a
fresh `Base.metadata.create_all()` SQLite database agree) rejects any other value.

**This is a presentation/audience discriminator only, never an authorization boundary.** RBAC
(`docs/contracts/identity-authorization.md`) and the deployment-database tenant boundary (section 1
above) remain the only real access-control axes; no route, permission or the competency engine
itself may be gated on this value — gap analysis, adaptive assessment and recommendations run
identically regardless of mode, only the presenting surface differs.

**What this scaffold deliberately does not do**, so the boundary with other lanes' ownership stays
explicit:

- It does not decide which curricula/competencies are offered per mode — that is Lane 3's decision
  (`services/curricula.py`), not encoded in this column or this migration.
- It does not route or render anything — that is Lane 1 (`frontend/**`) and Lane 5's decision.
- No route currently reads or writes this field. `schemas/player.py`'s `PlayerCreate` intentionally
  does not accept it yet, since `routes/game.py`'s `create_player()` (Lane 5-owned) does not read
  it — every new player gets the model default regardless of what a client might send. Accepting a
  field a route can't yet honor would misrepresent what is actually implemented. `PlayerResponse`
  does expose the stored value (read-only), since that reflects real state.
- A pre-existing SQLite demo database file (upgraded only through `db/database.py`'s
  `ensure_columns()`, a plain `ALTER TABLE ADD COLUMN`, called from `main.py`'s startup) gets the
  column but not the `CHECK` constraint — SQLite cannot `ALTER` a constraint onto an existing table
  outside Alembic's batch/copy-and-move mode. This matches the existing, accepted precedent that
  `ensure_columns()` is best-effort compatibility for every other column it adds, not enforcement.

Any lane building the next layer on this (Lane 3's per-mode curriculum policy, Lane 1/5's routing,
a route that lets a learner actually change their own mode) follows the normal section 7 change
process for anything that isn't purely additive to what's declared here.
