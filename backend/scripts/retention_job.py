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


@dataclass(frozen=True)
class RetentionEnforcementResult:
    category: str
    dry_run: bool
    candidate_count: int
    deleted_count: int
    reason: str | None = None
    deleted_ids: tuple[str, ...] = ()


def enforce_maximum_retention(
    db: Session,
    category: str,
    *,
    apply: bool = False,
    policies: dict[str, RetentionPolicy] | None = None,
    table_map: dict[str, tuple[type, str, str]] | None = None,
    now: datetime | None = None,
    actor: str = "system:retention_job",
) -> RetentionEnforcementResult:
    """Report (default) or delete rows in `category` older than its cited
    MAXIMUM retention. A safe no-op when no maximum is cited for `category`.

    `policies`/`table_map` default to the real registries; tests pass a
    synthetic policy/table mapping to prove the deletion mechanism itself
    works, without ever adding a fabricated ceiling to the real registry.
    """
    policies = RETENTION_POLICIES if policies is None else policies
    table_map = CATEGORY_TABLES if table_map is None else table_map

    if category not in policies:
        raise RetentionJobError(f"unknown retention category: {category!r}")
    policy = policies[category]

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

    candidates = db.execute(
        select(pk_column, timestamp_column).where(timestamp_column < cutoff)
    ).all()

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

    candidate_ids = tuple(str(pk_value) for pk_value, _ in candidates)

    if not apply or not candidate_ids:
        return RetentionEnforcementResult(
            category=category,
            dry_run=not apply,
            candidate_count=len(candidate_ids),
            deleted_count=0,
            deleted_ids=candidate_ids,
        )

    try:
        deleted = db.execute(
            model.__table__.delete().where(pk_column.in_(candidate_ids))
        ).rowcount
        record_audit_event(
            db,
            actor=actor,
            action="retention_job.enforce_maximum",
            entity_type=category,
            entity_id=None,
            details={
                "deleted_count": deleted,
                "maximum_retention_days": policy.maximum_retention_days,
                "maximum_retention_source": policy.maximum_retention_source,
                "cutoff": cutoff.isoformat(),
            },
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return RetentionEnforcementResult(
        category=category,
        dry_run=False,
        candidate_count=len(candidate_ids),
        deleted_count=deleted,
        deleted_ids=candidate_ids,
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
    parser.add_argument("--actor", default="system:retention_job")
    args = parser.parse_args(argv)

    db = SessionLocal()
    try:
        result = enforce_maximum_retention(
            db, args.category, apply=args.apply, actor=args.actor
        )
    finally:
        db.close()

    if result.reason:
        print(f"{result.category}: {result.reason}")
    elif result.dry_run:
        print(
            f"{result.category}: DRY RUN -- {result.candidate_count} row(s) would be deleted "
            f"(re-run with --apply to actually delete). IDs: {list(result.deleted_ids)}"
        )
    else:
        print(f"{result.category}: deleted {result.deleted_count} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
