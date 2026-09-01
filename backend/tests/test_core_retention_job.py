"""Tests for scripts/retention_job.py -- Package P.

Two concerns are tested separately: (1) that the job is a provable no-op
against the REAL retention registry, since no category has a cited maximum
retention today; (2) that the deletion mechanism itself actually works,
proven against a synthetic, clearly test-only policy/table mapping that is
never merged into the real registry.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models import (  # noqa: F401 -- registers every model so FK/relationship resolution succeeds
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
from models.governance import AuditEvent
from scripts.retention_job import (
    CATEGORY_TABLES,
    RetentionJobError,
    enforce_maximum_retention,
)
from security.retention import RETENTION_POLICIES, RetentionPolicy


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _insert_audit_event(db, *, age_days: float, event_id: str) -> None:
    created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.add(
        AuditEvent(
            audit_id=event_id,
            actor="test",
            action="synthetic.event",
            entity_type="test",
            created_at=created_at,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# 1. Real registry: must be a provable no-op today.
# ---------------------------------------------------------------------------


def test_real_registry_has_no_category_with_a_cited_maximum():
    # If this ever fails, a real maximum was added to RETENTION_POLICIES --
    # which is fine, but it means the "always a no-op today" claim below
    # (and in this module's own docstring) needs to be re-verified, not
    # silently left stale.
    assert all(p.maximum_retention_days is None for p in RETENTION_POLICIES.values())


def test_enforce_maximum_retention_is_a_noop_against_the_real_registry(db):
    _insert_audit_event(db, age_days=100_000, event_id="ancient-event")
    result = enforce_maximum_retention(
        db, "retain_append_only_security_log_duration_policy_pending", apply=True
    )
    assert result.candidate_count == 0
    assert result.deleted_count == 0
    assert "no cited maximum retention" in result.reason
    # Nothing was touched -- the ancient row is still there.
    assert db.query(AuditEvent).filter_by(audit_id="ancient-event").count() == 1


def test_enforce_maximum_retention_rejects_an_unknown_category(db):
    with pytest.raises(RetentionJobError, match="unknown retention category"):
        enforce_maximum_retention(db, "not_a_real_category")


def test_enforce_maximum_retention_refuses_a_category_with_no_table_mapping(db):
    synthetic_policies = {
        "delete_with_verified_subject_request": RetentionPolicy(
            category="delete_with_verified_subject_request",
            minimum_retention_days=None,
            minimum_retention_source=None,
            maximum_retention_days=30,
            maximum_retention_source="synthetic test-only source",
            notes="test only",
        ),
    }
    with pytest.raises(RetentionJobError, match="no registered table mapping"):
        enforce_maximum_retention(
            db,
            "delete_with_verified_subject_request",
            apply=True,
            policies=synthetic_policies,
        )


# ---------------------------------------------------------------------------
# 2. Synthetic policy: proves the deletion mechanism itself is correct.
# This maximum (30 days) is a TEST FIXTURE ONLY -- it is never added to the
# real security.retention.RETENTION_POLICIES registry.
# ---------------------------------------------------------------------------

_SYNTHETIC_CATEGORY = "retain_append_only_security_log_duration_policy_pending"
_SYNTHETIC_POLICIES = {
    _SYNTHETIC_CATEGORY: RetentionPolicy(
        category=_SYNTHETIC_CATEGORY,
        minimum_retention_days=None,
        minimum_retention_source=None,
        maximum_retention_days=30,
        maximum_retention_source="synthetic test-only source, not a real citation",
        notes="test only",
    ),
}


def test_dry_run_reports_candidates_without_deleting(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")
    _insert_audit_event(db, age_days=10, event_id="young-event")

    result = enforce_maximum_retention(
        db, _SYNTHETIC_CATEGORY, apply=False, policies=_SYNTHETIC_POLICIES
    )

    assert result.dry_run is True
    assert result.candidate_count == 1
    assert result.deleted_count == 0
    assert result.deleted_ids == ("old-event",)
    # Dry run must not have deleted anything.
    assert db.query(AuditEvent).count() == 2


def test_apply_deletes_only_rows_older_than_the_maximum(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")
    _insert_audit_event(db, age_days=29, event_id="just-under-event")
    _insert_audit_event(db, age_days=10, event_id="young-event")

    result = enforce_maximum_retention(
        db, _SYNTHETIC_CATEGORY, apply=True, policies=_SYNTHETIC_POLICIES
    )

    assert result.dry_run is False
    assert result.candidate_count == 1
    assert result.deleted_count == 1
    assert result.deleted_ids == ("old-event",)

    remaining_ids = {row.audit_id for row in db.query(AuditEvent).all()}
    # old-event was deleted; the synthetic.event rows for the two survivors
    # remain, plus the retention_job's own audit event about the deletion.
    assert "old-event" not in remaining_ids
    assert "just-under-event" in remaining_ids
    assert "young-event" in remaining_ids


def test_apply_writes_exactly_one_audit_event_describing_the_deletion(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")

    enforce_maximum_retention(db, _SYNTHETIC_CATEGORY, apply=True, policies=_SYNTHETIC_POLICIES)

    events = db.query(AuditEvent).filter_by(action="retention_job.enforce_maximum").all()
    assert len(events) == 1
    event = events[0]
    assert event.entity_type == _SYNTHETIC_CATEGORY
    assert event.details["deleted_count"] == 1
    assert event.details["maximum_retention_days"] == 30
    assert "synthetic test-only source" in event.details["maximum_retention_source"]


def test_apply_with_zero_candidates_deletes_nothing_and_writes_no_audit_event(db):
    _insert_audit_event(db, age_days=5, event_id="young-event")

    result = enforce_maximum_retention(
        db, _SYNTHETIC_CATEGORY, apply=True, policies=_SYNTHETIC_POLICIES
    )

    assert result.candidate_count == 0
    assert result.deleted_count == 0
    assert db.query(AuditEvent).filter_by(action="retention_job.enforce_maximum").count() == 0
    assert db.query(AuditEvent).filter_by(audit_id="young-event").count() == 1


def test_category_tables_only_registers_the_retain_only_category():
    # delete_with_verified_subject_request / scrub_with_verified_subject_request
    # must never be eligible for age-based automated deletion -- they are
    # deleted/scrubbed only on a verified subject request.
    assert set(CATEGORY_TABLES) == {"retain_append_only_security_log_duration_policy_pending"}
