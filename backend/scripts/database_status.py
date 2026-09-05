"""Privacy-safe, read-only database status/introspection tool -- Package W-B.

Built so any lane (or an operator) can answer "is the schema current, and
roughly how much of what kind of data exists" without writing raw SQL
against Lane 2's models, and without ever seeing a row's own content.

Design constraints (all load-bearing, not stylistic):

- Every value this module reports is a count, a boolean, a revision string
  or a table/dialect name -- never a row's own content. No player_id,
  username, email, free-text field, token, self-rating, answer, evidence
  detail or uploaded excerpt is ever read or printed.
- `TABLE_COUNTERS` is a fixed, explicit allowlist, not a dynamic
  `Base.metadata.tables` walk. A future PII-bearing table must be
  deliberately added here (and reviewed for this exact purpose) before this
  tool ever reports anything about it, rather than a schema change silently
  starting to expose a table nobody vetted.
- This module never accepts a player_id, user id or free-text filter of any
  kind -- there is no code path here that can be pointed at one subject.
- Secrets are reported as a present/absent boolean only
  (`CONFIGURED_ENV_FLAGS`); their actual values are never read into any
  return value, printed, or logged.
- A fresh, empty or partially-migrated database must be reportable, not
  fatal: `get_table_row_counts` checks which tables actually exist before
  counting any of them, and returns the rest as `missing_tables` rather than
  letting the first absent table's `OperationalError` abort the whole
  status -- "tell me my database isn't set up yet" is this tool's primary
  purpose, not an edge case it can afford to crash on.

See `LANE2_INTEGRATION_GUIDE.md` for how other lanes are expected to use
this (health-checking their own local setup, CI gating on `--check-migrations
--migration-only` -- see `get_database_status`'s `include_counts` for why the
CI form skips every table's row count), and `LANE2_SYNC.md`'s Package W (and
Package 6/AC) entries for the coordination that produced it.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.database import database_revision, migration_head_revision
from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon, Room
from models.governance import AuditEvent, EvidenceRecord, RoleTarget, SourceVersion
from models.guild import Guild
from models.identity import IdentityBinding
from models.learning import (
    CompetencyAssessment,
    GeneratedQuiz,
    LearnerProfile,
    LearningMaterial,
)
from models.player import Player
from models.question import Question
from models.session import GameSession
from models.submission import AnswerSubmission

# table label -> model class. Deliberately explicit and reviewable in one
# place -- see the module docstring's allowlist rationale.
TABLE_COUNTERS: dict[str, type] = {
    "players": Player,
    "learner_profiles": LearnerProfile,
    "competency_assessments": CompetencyAssessment,
    "learning_materials": LearningMaterial,
    "generated_quizzes": GeneratedQuiz,
    "role_targets": RoleTarget,
    "evidence_records": EvidenceRecord,
    "source_versions": SourceVersion,
    "audit_events": AuditEvent,
    "identity_bindings": IdentityBinding,
    "dungeons": Dungeon,
    "rooms": Room,
    "questions": Question,
    "guilds": Guild,
    "game_sessions": GameSession,
    "submissions": AnswerSubmission,
    "accuracy_history": AccuracyHistory,
}

# Env vars other lanes/operators commonly need to know are SET -- never
# printed by value. A missing GEMINI_API_KEY explains a lot of Lane 4's
# fallback behavior; a missing OIDC_ISSUER/OIDC_AUDIENCE explains why
# security.identity's verifier can't be built -- both are common "why isn't
# this working" questions this tool answers without exposing a secret.
CONFIGURED_ENV_FLAGS: tuple[str, ...] = (
    "DATABASE_URL",
    "OIDC_ISSUER",
    "OIDC_AUDIENCE",
    "GEMINI_API_KEY",
    "SEED_DEMO_DATA",
)


@dataclass(frozen=True)
class MigrationStatus:
    dialect: str
    current_revision: str | None
    head_revision: str
    at_head: bool


@dataclass(frozen=True)
class DatabaseStatus:
    generated_at: str
    tenant_scope: str
    migration: MigrationStatus
    table_row_counts: dict[str, int]
    counts_included: bool
    missing_tables: list[str]
    configured: dict[str, bool]


def get_migration_status(bind: Engine) -> MigrationStatus:
    """Read-only migration status: current vs. required head.

    Unlike `db.database.require_database_at_migration_head`, this never
    raises on drift -- a status tool must be able to report "not at head" as
    a fact for a caller to act on, not treat it as a fatal startup error.
    """
    head = migration_head_revision()
    current = database_revision(bind)
    return MigrationStatus(
        dialect=bind.dialect.name,
        current_revision=current,
        head_revision=head,
        at_head=current == head,
    )


def get_missing_tables(
    bind: Engine, *, tables: dict[str, type] = TABLE_COUNTERS
) -> list[str]:
    """Which advertised tables don't exist yet -- one inspector call, no
    `COUNT(*)` against any table. This is the cheap half of what
    `get_table_row_counts` does; split out so a caller that only needs the
    missing-table signal (e.g. `--migration-only`) never pays for a full
    count on every table just to get it."""
    existing = set(inspect(bind).get_table_names())
    return sorted(label for label, model in tables.items() if model.__tablename__ not in existing)


def get_table_row_counts(
    db: Session, *, tables: dict[str, type] = TABLE_COUNTERS
) -> tuple[dict[str, int], list[str]]:
    """`COUNT(*)` only, per table in the fixed allowlist above that actually
    exists in the database -- never a row's own content, never filtered by
    player_id or any other identifying value.

    Returns `(counts, missing_tables)` instead of raising on a fresh or
    partially-migrated database. This tool's whole point is to let a caller
    tell "database not set up yet" apart from "database is fine" -- an
    `OperationalError`/`ProgrammingError` from the first absent table (e.g.
    a brand-new SQLite file with no migrations applied yet, or a database
    stamped at a revision whose migration never actually ran) must not abort
    the entire report before it can say that.

    A `COUNT(*)` per table is unconditional real work against every
    advertised table, not merely a network round trip -- combining them into
    one `UNION ALL` query would cut round trips but still perform every
    exact count, which does not help a genuinely large table. Skip this
    function entirely (see `get_database_status(..., include_counts=False)`
    / `--migration-only`) when only the migration-head/missing-table signal
    is needed, rather than trying to make counting itself cheaper.
    """
    existing = set(inspect(db.get_bind()).get_table_names())
    counts: dict[str, int] = {}
    missing: list[str] = []
    for label, model in tables.items():
        if model.__tablename__ in existing:
            counts[label] = int(
                db.execute(
                    select(func.count()).select_from(model.__table__)
                ).scalar_one()
            )
        else:
            missing.append(label)
    return counts, sorted(missing)


def get_configured_flags(env: dict[str, str] | None = None) -> dict[str, bool]:
    """Whether each of `CONFIGURED_ENV_FLAGS` is set to a non-blank value.
    Booleans only -- the actual value is never read into the result."""
    source = env if env is not None else os.environ
    return {name: bool(source.get(name, "").strip()) for name in CONFIGURED_ENV_FLAGS}


def get_database_status(
    db: Session,
    *,
    tables: dict[str, type] = TABLE_COUNTERS,
    env: dict[str, str] | None = None,
    include_counts: bool = True,
) -> DatabaseStatus:
    """`include_counts=False` (the `--migration-only` CLI mode) skips
    `get_table_row_counts` entirely -- no `COUNT(*)` against any table, only
    the cheap existence check `get_missing_tables` needs. For a caller that
    only wants the migration-head/missing-table signal (the shape of every
    `--check-migrations` CI use this tool documents itself for), a full
    per-table count is real, unconditional work this tool has no reason to
    force on every table just to answer that one question -- see
    `get_table_row_counts`'s own docstring for why `UNION ALL` doesn't fix
    this either. `table_row_counts` is `{}` when skipped; `counts_included`
    says which happened so a caller can't mistake "skipped" for "everything
    is empty".
    """
    bind = db.get_bind()
    if not isinstance(bind, Engine):
        raise TypeError(
            "database_status requires a Session bound to a real Engine, not a "
            f"Connection/other bind ({type(bind)!r}) -- migration_status needs "
            "the engine's own dialect, independent of any open transaction."
        )
    if include_counts:
        counts, missing = get_table_row_counts(db, tables=tables)
    else:
        counts, missing = {}, get_missing_tables(bind, tables=tables)
    return DatabaseStatus(
        generated_at=datetime.now(timezone.utc).isoformat(),
        # Matches docs/contracts/data-authorization.md section 1/6.1: there is
        # no multi-tenant key to report yet, so the only honest tenant_scope
        # value today is the deployment database itself.
        tenant_scope="deployment-database",
        migration=get_migration_status(bind),
        table_row_counts=counts,
        counts_included=include_counts,
        missing_tables=missing,
        configured=get_configured_flags(env),
    )


def status_to_dict(status: DatabaseStatus) -> dict:
    return asdict(status)


def format_human(status: DatabaseStatus) -> str:
    lines = [
        f"generated_at: {status.generated_at}",
        f"tenant_scope: {status.tenant_scope}",
        f"dialect: {status.migration.dialect}",
        f"migration: current={status.migration.current_revision or 'unversioned'} "
        f"head={status.migration.head_revision} "
        f"({'AT HEAD' if status.migration.at_head else 'NOT AT HEAD'})",
        "configured:",
    ]
    for name in sorted(status.configured):
        lines.append(f"  {name}: {'set' if status.configured[name] else 'not set'}")
    if status.counts_included:
        lines.append("table_row_counts:")
        for label in sorted(status.table_row_counts):
            lines.append(f"  {label}: {status.table_row_counts[label]}")
    else:
        lines.append("table_row_counts: skipped (--migration-only)")
    if status.missing_tables:
        lines.append(
            "missing_tables (not created yet -- run `alembic upgrade head` "
            "or a fresh Base.metadata.create_all(), see the migration line above):"
        )
        for label in status.missing_tables:
            lines.append(f"  {label}")
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    # Import every model module so SQLAlchemy's string-referenced
    # relationships are configured -- this script may run standalone,
    # without FastAPI's `main` having imported the full model registry
    # first (same precedent as security/identity_bootstrap.py and
    # scripts/retention_job.py).
    from models import (  # noqa: F401
        accuracy_history,
        dungeon,
        governance,
        guild,
        identity,
        learning,
        player,
        question,
        session,
        submission,
    )
    from db.database import SessionLocal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    parser.add_argument(
        "--check-migrations",
        action="store_true",
        help=(
            "Exit 1 if the database is not at the repository's Alembic head, "
            "or if any advertised table is missing even when a revision is "
            "stamped (for CI/other-lane scripting; the default text/JSON "
            "output is printed either way)"
        ),
    )
    parser.add_argument(
        "--migration-only",
        action="store_true",
        help=(
            "Skip every table's COUNT(*) -- report only the migration-head/"
            "missing-table signal. Use this for a CI gate: --check-migrations "
            "does not need row counts, and counting every advertised table is "
            "real, unconditional work a status check has no reason to force "
            "on a large table just to answer a yes/no schema question."
        ),
    )
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        status = get_database_status(db, include_counts=not args.migration_only)
    finally:
        db.close()

    if args.json:
        print(json.dumps(status_to_dict(status), indent=2, sort_keys=True))
    else:
        print(format_human(status))

    if args.check_migrations and (not status.migration.at_head or status.missing_tables):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
