"""Retention-enforcement job -- Package P.

`security.retention.RETENTION_POLICIES` records a cited MAXIMUM retention
ceiling for a category only when one has actually been sourced. Today none
exist, so this job -- run against the real registry -- is a provable no-op:
it finds zero candidates for every real category and deletes nothing. The
deletion mechanism itself is proven separately against a synthetic,
clearly-labelled test-only policy in
`backend/tests/test_core_retention_job.py`, not by inventing a real ceiling
here.

Only categories with a single well-defined table and timestamp column are
eligible (see `CATEGORY_TABLES` below). `delete_with_verified_subject_request`
and `scrub_with_verified_subject_request` are intentionally NOT eligible:
their whole definition is that rows are deleted/scrubbed only on a verified
subject request (`security.data_rights`), never on an age-based schedule.
This job must not silently start deleting them just because someone later
adds a `maximum_retention_days` to their policy entry by mistake -- it
refuses instead, loudly.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.database import require_database_at_migration_head
from models.governance import AuditEvent
from security.audit import record_audit_event
from security.retention import (
    RETENTION_POLICIES,
    RetentionPolicy,
    assert_minimum_retention_satisfied,
)


class RetentionJobError(RuntimeError):
    """Raised when an enforcement request is invalid or unsafe to run."""


# category -> (SQLAlchemy model, UTC timestamp column name, primary key column name)
CATEGORY_TABLES: dict[str, tuple[type, str, str]] = {
    "retain_append_only_security_log_duration_policy_pending": (
        AuditEvent,
        "created_at",
        "audit_id",
    ),
}

DEFAULT_BATCH_SIZE = 500


@dataclass(frozen=True)
class RetentionEnforcementResult:
    category: str
    dry_run: bool
    candidate_count: int
    deleted_count: int
    reason: str | None = None
    deleted_ids: tuple[str, ...] = ()
    more_remain: bool = False


MAX_BATCH_SIZE = 10_000


def _require_valid_batch_size(batch_size: object) -> int:
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise RetentionJobError(
            f"batch_size must be a positive non-boolean integer, got {batch_size!r}"
        )
    if batch_size > MAX_BATCH_SIZE:
        raise RetentionJobError(
            f"batch_size must be at most {MAX_BATCH_SIZE} (an operational cap independent of "
            f"whether any real policy is currently a no-op), got {batch_size!r}"
        )
    return batch_size


def _enforce_maximum_retention_core(
    db: Session,
    category: str,
    *,
    apply: bool,
    policies: dict[str, RetentionPolicy],
    table_map: dict[str, tuple[type, str, str]],
    batch_size: int,
    now: datetime | None,
    actor: str,
) -> RetentionEnforcementResult:
    """The actual enforcement mechanism -- private. `policies`/`table_map`
    are REQUIRED here (never defaulted) so this function can only ever be
    reached with an explicit registry. Tests call this directly with a
    synthetic policy/table mapping to prove the deletion mechanism works,
    without that path being reachable from the public, registry-fixed
    `enforce_maximum_retention()` below -- an earlier version let
    `policies`/`table_map` default through the public function itself,
    which meant an ordinary (or future route) caller could pass an
    uncited ceiling and delete real rows through the public API.
    """
    batch_size = _require_valid_batch_size(batch_size)

    if category not in policies:
        raise RetentionJobError(f"unknown retention category: {category!r}")
    policy = policies[category]

    # Destructive PostgreSQL runs must be gated on migration-head status
    # BEFORE any policy-dependent early return -- including "no cited
    # maximum" below. A no-op-today category must never let a genuinely
    # unmigrated destructive-path database look like a clean, checked run;
    # the gate is a general safety invariant, not conditional on whether
    # this particular call happens to find anything to delete. SQLite's
    # documented local-demo profile is never Alembic-managed (see
    # db/database.py's own create_all()-vs-migration-head split), so it
    # remains deliberately exempt, exactly like every other startup path in
    # this project.
    if apply and db.get_bind().dialect.name == "postgresql":
        try:
            require_database_at_migration_head(db.get_bind())
        except RuntimeError as exc:
            raise RetentionJobError(f"database revision check failed: {exc}") from exc

    if policy.maximum_retention_days is None:
        return RetentionEnforcementResult(
            category=category,
            dry_run=not apply,
            candidate_count=0,
            deleted_count=0,
            reason="no cited maximum retention for this category -- nothing to enforce",
        )

    if category not in table_map:
        raise RetentionJobError(
            f"{category!r} has a cited maximum_retention_days but no registered table "
            "mapping -- refusing to guess which table to delete from"
        )
    model, timestamp_attr, pk_attr = table_map[category]
    timestamp_column = getattr(model, timestamp_attr)
    pk_column = getattr(model, pk_attr)

    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=policy.maximum_retention_days)

    base_query = (
        select(pk_column, timestamp_column)
        .where(timestamp_column < cutoff)
        .order_by(timestamp_column.asc(), pk_column.asc())
    )

    if apply and db.get_bind().dialect.name == "postgresql":
        # A plain SELECT (no locking) lets N concurrent PostgreSQL workers
        # all read the SAME unlocked candidate set, then race each other's
        # DELETEs -- RETURNING stops any one worker from double-claiming a
        # row another already deleted, but it does NOT stop every worker
        # from wastefully attempting the same batch while the rest of the
        # table's expired rows never get picked up by anyone. `FOR UPDATE
        # SKIP LOCKED` fixes this at the source: it atomically claims
        # exactly `batch_size` rows and skips any row a concurrent worker's
        # own FOR UPDATE has already locked, so concurrent workers
        # partition the real work instead of colliding on one batch. This
        # lock is held until this call's own commit()/rollback() below.
        #
        # The lock claims EXACTLY batch_size rows, not batch_size + 1 --
        # locking a lookahead row we have no intention of processing in
        # this call would be pure waste (and would needlessly block a
        # concurrent worker from claiming it). `more_remain` is therefore
        # answered by a completely separate, unlocked existence check
        # below, not by an over-fetched lookahead row.
        candidates = db.execute(
            base_query.limit(batch_size).with_for_update(skip_locked=True)
        ).all()
        claimed_pks = [pk_value for pk_value, _ in candidates]
        remaining_query = base_query.limit(1)
        if claimed_pks:
            remaining_query = remaining_query.where(pk_column.not_in(claimed_pks))
        more_remain = db.execute(remaining_query).first() is not None
    else:
        # SQLite (the documented local-demo profile) has no real concurrent-
        # writer model to defend against here -- its own single-writer lock
        # already serializes every write -- so the simpler bounded lookahead
        # is sufficient and keeps this path portable/dependency-free.
        candidates = db.execute(base_query.limit(batch_size + 1)).all()
        more_remain = len(candidates) > batch_size
        candidates = candidates[:batch_size]

    # Defense-in-depth: every candidate must also already satisfy the
    # category's cited MINIMUM floor. RetentionPolicy.__post_init__ already
    # guarantees minimum <= maximum whenever both are cited, so this can
    # only ever fire if a future bug lets an invalid policy or table mapping
    # slip past that guard -- it must never fire in ordinary operation.
    for _pk_value, ts_value in candidates:
        if ts_value.tzinfo is None:
            ts_value = ts_value.replace(tzinfo=timezone.utc)
        age_days = (now - ts_value).total_seconds() / 86400
        assert_minimum_retention_satisfied(category, age_days, policies=policies)

    # Keep the raw candidate PKs (whatever type the column actually is) for
    # the DELETE predicate -- stringifying before building the predicate
    # risked a silent type mismatch for any future non-string primary key.
    # Only the *reported* IDs are stringified, for display purposes only.
    raw_candidate_pks = [pk_value for pk_value, _ in candidates]
    candidate_ids = tuple(str(pk_value) for pk_value in raw_candidate_pks)

    if not apply or not raw_candidate_pks:
        return RetentionEnforcementResult(
            category=category,
            dry_run=not apply,
            candidate_count=len(candidate_ids),
            deleted_count=0,
            deleted_ids=candidate_ids,
            more_remain=more_remain,
        )

    try:
        # RETURNING makes `deleted_ids`/`deleted_count` reflect exactly what
        # THIS call actually removed, not what it merely selected as
        # candidates -- if a concurrent rerun (or any other deleter) already
        # removed some of these rows between the SELECT above and this
        # DELETE, this result will not claim credit for rows it didn't
        # actually delete. The predicate also rechecks `timestamp_column <
        # cutoff` -- not just PK membership -- so a row whose age no longer
        # qualifies by the time this DELETE runs (its timestamp was
        # corrected/updated after the SELECT above) is never deleted just
        # because it was a candidate a moment ago; PK membership alone would
        # delete it on stale evidence.
        deleted_rows = db.execute(
            model.__table__.delete()
            .where(pk_column.in_(raw_candidate_pks), timestamp_column < cutoff)
            .returning(pk_column)
        ).all()
        actually_deleted_ids = tuple(str(row[0]) for row in deleted_rows)
        if actually_deleted_ids:
            record_audit_event(
                db,
                actor=actor,
                action="retention_job.enforce_maximum",
                entity_type=category,
                entity_id=None,
                details={
                    "deleted_count": len(actually_deleted_ids),
                    "candidate_count": len(candidate_ids),
                    "maximum_retention_days": policy.maximum_retention_days,
                    "maximum_retention_source": policy.maximum_retention_source,
                    "cutoff": cutoff.isoformat(),
                    "batch_size": batch_size,
                },
                commit=False,
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    if not actually_deleted_ids:
        # A total race loss -- every originally selected candidate was
        # already removed by something else before this call's own DELETE
        # ran -- is reported exactly like "no candidates were ever found":
        # no audit event (nothing was done), and candidate_count reflects
        # that reality rather than the now-stale pre-race SELECT count.
        # This differs from a PARTIAL loss (some, not all, candidates
        # deleted by this call), which still reports the real candidate
        # count alongside the smaller actual deleted_count/deleted_ids.
        return RetentionEnforcementResult(
            category=category,
            dry_run=False,
            candidate_count=0,
            deleted_count=0,
            more_remain=more_remain,
        )

    return RetentionEnforcementResult(
        category=category,
        dry_run=False,
        candidate_count=len(candidate_ids),
        deleted_count=len(actually_deleted_ids),
        deleted_ids=actually_deleted_ids,
        more_remain=more_remain,
    )


def enforce_maximum_retention(
    db: Session,
    category: str,
    *,
    apply: bool = False,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    actor: str = "system:retention_job",
) -> RetentionEnforcementResult:
    """Report (default) or delete rows in `category` older than its cited
    MAXIMUM retention. A safe no-op when no maximum is cited for `category`.

    This is the only public entry point, and it always operates against the
    real `security.retention.RETENTION_POLICIES` and this module's real
    `CATEGORY_TABLES` -- there is no parameter that can redirect it to a
    different registry. A caller that needs to prove the deletion mechanism
    itself against a synthetic policy (this module's own tests) must import
    the private `_enforce_maximum_retention_core` directly.
    """
    return _enforce_maximum_retention_core(
        db,
        category,
        apply=apply,
        policies=RETENTION_POLICIES,
        table_map=CATEGORY_TABLES,
        batch_size=batch_size,
        now=now,
        actor=actor,
    )


def _main(argv: list[str] | None = None) -> int:
    # Import every model module so SQLAlchemy's string-referenced
    # relationships are configured -- this script may run standalone,
    # without FastAPI's `main` having imported the full model registry
    # first (same precedent as security/identity_bootstrap.py).
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
    parser.add_argument("--category", required=True, choices=sorted(RETENTION_POLICIES))
    parser.add_argument(
        "--apply", action="store_true", help="Actually delete; default is dry-run/report-only"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Maximum rows to consider in one run (default {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument("--actor", default="system:retention_job")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        result = enforce_maximum_retention(
            db,
            args.category,
            apply=args.apply,
            batch_size=args.batch_size,
            actor=args.actor,
        )
    finally:
        db.close()

    more = " (more rows beyond this batch remain -- re-run to continue)" if result.more_remain else ""
    if result.reason:
        print(f"{result.category}: {result.reason}")
    elif result.dry_run:
        print(
            f"{result.category}: DRY RUN -- {result.candidate_count} row(s) would be deleted"
            f"{more} (re-run with --apply to actually delete). IDs: {list(result.deleted_ids)}"
        )
    else:
        print(f"{result.category}: deleted {result.deleted_count} row(s).{more}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
