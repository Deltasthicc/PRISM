# Production PostgreSQL hardening contract

Owner: Lane 2 (specification and application-side wiring)

Operational consumers/approvers: Lane 6, the deployment owner, security owner

Status: **specify-only. Nothing in this document is implemented, deployed, or dev-drilled.**
Every item below needs numbers or a decision only Lane 6 (or the accountable deployment/security
owner) can supply — a worker/process count, the target PostgreSQL server's real `max_connections`
and its own reserved-connection policy, an approved TLS certificate chain, and an accepted
role-separation rollout plan. Per the reconciled Lane 2 execution plan this package specifies
against: *"specify only, do not claim implemented ... dev-drill only after Lane 6 gives assumptions
or explicitly accepts a local reference profile."* No such profile has been given or accepted as of
this writing, so no local reference drill is included here either — a drill run against invented
numbers would prove nothing about the real target and risks being mistaken for evidence that this
is closer to done than it is.

## 0. Current reality

Today's actual configuration, read directly from the repository, not summarized from memory:

- `backend/docker-compose.dev.yml`'s `postgres` service sets `POSTGRES_USER: prism_app` with no
  other role ever created — in the Postgres Docker image, the `POSTGRES_USER` value becomes a
  **superuser**, and every consumer of this database (the running app via `DATABASE_URL`, Alembic
  migrations, `scripts/backup_restore.py`, ad hoc operator `psql` sessions) connects as that same
  superuser. There is no role separation of any kind.
- No `sslmode`, `ssl`, or `search_path` configuration exists anywhere in `backend/db/database.py`,
  `backend/.env.example`, or `backend/docker-compose.dev.yml` — confirmed by grep, not assumed.
  PostgreSQL is published from the container to `localhost:55432` with no TLS negotiated.
- `backend/db/database.py`'s `create_engine(...)` sets `pool_pre_ping=True` (dead-connection
  detection before use) and nothing else pool-related — no `pool_size`, `max_overflow`,
  `pool_recycle`, or `pool_timeout`. SQLAlchemy's own defaults apply (`pool_size=5`,
  `max_overflow=10`), which were never chosen for this project's actual concurrency shape; they are
  simply what happens when nothing is configured.
- All application tables and their governance CHECK constraints/indexes/triggers currently live in
  PostgreSQL's default `public` schema.

This mirrors `docs/contracts/encryption-key-ownership.md`'s own precedent: the local Compose stack
is acceptable **only** for synthetic local development, is not a deployment template, and must never
carry real credentials or personal data. Nothing below changes that today; it specifies what must be
true before it would be acceptable for anything else.

## 1. Three-role PostgreSQL privilege matrix

Three roles, replacing the current single superuser for every purpose:

| Role | Purpose | Used by | Login |
|---|---|---|---|
| `prism_migrate` | Owns the schema; the only role permitted to run DDL | `alembic upgrade`/`downgrade`, run once per deploy, never by the running application | yes, deploy-time only |
| `prism_runtime` | Executes the application's own queries | The running API process (`DATABASE_URL`) | yes, always-on |
| `prism_backup` | Reads data for backup/export tooling | `scripts/backup_restore.py`'s backup path (never restore, never runtime queries) | yes, scheduled/on-demand only |

Grants, as a specific, reviewable matrix rather than "least privilege" left abstract:

| Capability | `prism_migrate` | `prism_runtime` | `prism_backup` |
|---|---|---|---|
| `CREATE`/`ALTER`/`DROP` on tables, indexes, constraints, triggers | yes | **no** | no |
| `SELECT`/`INSERT`/`UPDATE`/`DELETE` on application tables | yes (for adoption-path data fixes only, see below) | yes | no |
| `SELECT` on application tables | yes | yes | yes |
| `USAGE`/`SELECT` on sequences (`nextval` for `SERIAL`/`IDENTITY` columns, e.g. `accuracy_history_id_seq`) | yes | yes (`USAGE` only — never needs to read a sequence's current value directly) | no |
| `CREATE`/`ALTER`/`DROP FUNCTION`, `CREATE`/`DROP TRIGGER` (the `audit_events` append-only trigger, `036de46dd515`) | yes | **no** | no |
| Connect to the database at all | yes | yes | yes |
| Superuser / `CREATEROLE` / `CREATEDB` | **no** | **no** | **no** |

Why exactly these three, not more or fewer: a fourth "read-only reporting" role was considered and
rejected here as premature — nothing in the current codebase issues reporting-only queries outside
`prism_runtime`'s own normal request path, and `scripts/database_status.py`/`scripts/lane2_doctor.py`
are read-only tools that run locally against whatever `DATABASE_URL` is configured for their
environment, not against a dedicated always-on reporting connection. Add one only when a real,
named consumer needs it.

`prism_migrate` keeping `INSERT`/`UPDATE`/`DELETE` (not just DDL) is deliberate, not an oversight: a
migration occasionally needs to backfill or repair data as part of a schema change (see
`migrations/versions/2baf7d4bd8a2_add_governance_tables.py`'s own legacy-table adoption path, and
`6564595b3466`'s `_reject_incompatible_existing_rows()` preflight, which would need `UPDATE` rights
to *repair* what it currently only *refuses to proceed past*). Restricting `prism_migrate` to
DDL-only would make a future data-repairing migration impossible without a fourth role; this is a
deliberate scope decision, not a gap, and should be revisited if a real need for a narrower
migration role appears.

**Rollout is explicitly out of scope for this document.** Creating these roles, generating and
storing their passwords, updating `DATABASE_URL` for the running application to use `prism_runtime`
instead of the current superuser, and updating `backup_restore.py`'s connection to use
`prism_backup`, are all deployment actions requiring Lane 6/the deployment owner's environment,
secrets management and rollout sequencing — none of that exists yet to specify against concretely.

## 2. Secure schema and `search_path`

Two independent hardening steps, both currently absent:

1. **Pin `search_path` explicitly per role, rather than leaving it at its connection-time default.**
   PostgreSQL resolves an unqualified table/function name by walking `search_path` in order; a role
   that can also `CREATE` in an earlier-resolved schema can shadow a table or function the
   application expects to resolve to something else (the classic Postgres `search_path` injection
   class). Fix, independent of whether schema consolidation (below) happens:
   `ALTER ROLE prism_runtime SET search_path = public;` (or the dedicated schema name, once it
   exists) pins it at the role level, not left to whatever a connection or a compromised/buggy
   query happens to `SET` at runtime. `prism_migrate` and `prism_backup` get the same explicit pin.
2. **Consider a dedicated non-public schema** (e.g. `prism`) instead of the default `public` schema,
   once role separation (section 1) exists. This is a genuine improvement (a fresh, unprivileged
   Postgres role has no implicit rights on a non-`public` schema the way `public` historically grants
   `CREATE` to `PUBLIC` on older PostgreSQL versions — PostgreSQL 15+ changed this default, so the
   actual current risk depends on the target server's version, another Lane 6 fact this document
   doesn't have) but is a real migration (every existing table, index, constraint, trigger and
   sequence moves schema) with its own rollback plan, not a config toggle. Not scheduled here;
   flagged as the more thorough option once role separation is live and the target PostgreSQL
   version is confirmed.

## 3. TLS verification policy

Production `DATABASE_URL` must specify `sslmode=verify-full` (psycopg 3's strictest mode): the
connection is encrypted **and** the server's certificate is validated against a trusted CA and its
hostname checked against the connection target. `sslmode=require` (encryption only, no identity
check) is explicitly **not sufficient** — it defeats a machine-in-the-middle presenting any
certificate at all, which is exactly the attack TLS on a database connection exists to prevent.

This needs, none of which this repository has today:

- An approved CA bundle for the target PostgreSQL server (`sslrootcert` in the connection string, or
  the platform's own trust store if the provider uses a publicly-trusted CA).
- Confirmation the target PostgreSQL provider actually terminates TLS with a certificate that CA
  chain validates (a self-signed or provider-internal CA needs its own root distributed to every
  deploy environment).
- A documented failure mode: `verify-full` means a connection **fails closed** if the certificate
  doesn't validate. This is correct and must not be "fixed" by silently downgrading to `require` or
  `disable` under deploy pressure — that would be exactly the regression this document exists to
  prevent.

Local development is explicitly exempt, matching `encryption-key-ownership.md`'s own precedent: the
local Compose PostgreSQL has no TLS configured and none is being added there — it never carries real
data and adding certificate management to the zero-setup local profile would work against that
profile's own purpose.

## 4. Connection pool and timeout budget

**Deliberately not specifying numbers here.** `pool_size`, `max_overflow`, `pool_recycle`, and
`pool_timeout` all require a real production concurrency shape to size correctly, and picking a
number without one (e.g. the previously-considered `pool_recycle=1800`) would just be a different
kind of unfounded default, not a fix — a Package 6 finding this document deliberately doesn't
un-fix. `pool_pre_ping=True` (already set, per section 0, and confirmed unaffected by every package
through this one) is the one setting in this area that needed no production numbers to be an
unambiguous improvement, which is exactly why it shipped already and the rest didn't.

The formula to apply once real numbers exist, so the next person doesn't have to derive it from
scratch:

```
(pool_size + max_overflow) × (number of concurrent application worker processes)
    ≤ target_postgresql_max_connections − reserved_admin_connections − other_services_reserve
```

Inputs this repository does not have and cannot invent:

- **Worker/process count** — how many application server processes/containers will hold their own
  connection pool concurrently (a single `uvicorn` worker vs. multiple, autoscaled replica count).
- **The target PostgreSQL server's actual `max_connections`**, and how much of it Lane 6/the
  deployment owner reserves for `prism_migrate` (deploy-time only, low concurrency), admin/operator
  access, and any other service sharing the same database server.
- **`pool_recycle`** should be set comfortably under whichever is shortest of: the database
  provider's own idle-connection timeout, and any intermediate connection pooler/load balancer's
  idle timeout — both are deployment-topology facts, not something this repository can assume.
- **`pool_timeout`** (how long a request waits for a pooled connection before failing) is a product
  decision about acceptable request latency under load, not a database fact at all — needs the
  deployment/product owner, not just Lane 6.

**No local reference-profile drill is included in this package.** Running one against invented
numbers would produce real-looking pass/fail output that proves nothing about the actual target and
risks being cited later as evidence this is more finished than it is. Per the reconciled plan, a
drill happens only once Lane 6 supplies real numbers or explicitly accepts a stated local reference
profile as representative enough to test against — neither has happened as of this writing.

## 5. What this document is not

Restating plainly, matching every other Lane 2 contract's own discipline about over-claiming:

- No role in section 1 has been created anywhere, in any environment.
- No `search_path` pin or schema migration in section 2 has been applied.
- No TLS certificate, CA bundle, or `sslmode` configuration in section 3 exists in any
  `DATABASE_URL` this repository ships or documents.
- No pool setting in section 4 has changed; `pool_pre_ping=True` is the only thing already true, and
  it was true before this document existed.
- This document does not authorize implementing any of the above without the specific real-world
  input each section names as missing. It is the specification those implementations must be
  reviewed against once that input exists, not a green light to guess.

## 6. Change process

Same as every other Lane 2 contract (`SIH26101_TEAM_ORCHESTRATION.md` section 8): once Lane 6 or the
accountable deployment/security owner supplies the missing input for a section, open a proposal
against that section specifically, get it reviewed, then implement and test it as its own package —
not as a silent edit to this specification.
