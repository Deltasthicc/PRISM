"""Adversarial acceptance tests for Package P's retention hardening.

This file is Package R and belongs to Codex.  It deliberately tests the
public safety boundary rather than duplicating the implementation owner's
happy-path coverage.  Claude Code owns the implementation and existing
Package P tests; Codex must not repair those files to make this contract pass.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.dml import Delete
from sqlalchemy.sql.selectable import Select

from db.database import Base
from models import (  # noqa: F401 -- register all relationships before create_all
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
from scripts import retention_job
from scripts.retention_job import RetentionJobError
from security.retention import RetentionPolicy


_CATEGORY = "retain_append_only_security_log_duration_policy_pending"
_SYNTHETIC_POLICIES = {
    _CATEGORY: RetentionPolicy(
        category=_CATEGORY,
        minimum_retention_days=None,
        minimum_retention_source=None,
        maximum_retention_days=30,
        maximum_retention_source="synthetic Package R fixture; not a real retention citation",
        notes="test only",
    )
}
_TABLE_MAP = {_CATEGORY: (AuditEvent, "created_at", "audit_id")}


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    database_session = sessionmaker(bind=engine)()
    yield database_session
    database_session.close()


def _insert_old_event(db, *, event_id: str = "package-r-old-event") -> None:
    db.add(
        AuditEvent(
            audit_id=event_id,
            actor="package-r",
            action="synthetic.event",
            entity_type="test",
            created_at=datetime.now(timezone.utc) - timedelta(days=40),
        )
    )
    db.commit()


def test_public_enforcement_has_no_synthetic_registry_injection_seam():
    parameters = inspect.signature(retention_job.enforce_maximum_retention).parameters
    assert "policies" not in parameters
    assert "table_map" not in parameters


def test_absurd_batch_size_is_rejected_even_when_real_policy_is_a_noop():
    """A positive integer is not automatically a safe operational bound."""
    fake_db = Mock()

    with pytest.raises(RetentionJobError, match="maximum|too large|at most|cap"):
        retention_job.enforce_maximum_retention(
            fake_db,
            _CATEGORY,
            apply=False,
            batch_size=1_000_000_000,
        )


def test_postgres_apply_checks_migration_head_before_real_policy_noop(monkeypatch):
    """Today's no-maximum registry must not bypass the destructive CLI gate."""
    bind = SimpleNamespace(dialect=SimpleNamespace(name="postgresql"))
    fake_db = Mock()
    fake_db.get_bind.return_value = bind
    checked_binds: list[object] = []

    monkeypatch.setattr(
        retention_job,
        "require_database_at_migration_head",
        lambda candidate_bind: checked_binds.append(candidate_bind),
    )

    result = retention_job.enforce_maximum_retention(fake_db, _CATEGORY, apply=True)

    assert checked_binds == [bind]
    assert result.deleted_count == 0
    assert result.reason and "no cited maximum" in result.reason


def test_concurrent_loser_does_not_audit_or_claim_rows_it_did_not_delete(db, monkeypatch):
    """Simulate another transaction winning after selection but before DELETE.

    PostgreSQL supplies the real concurrency evidence later.  This deterministic
    unit probe protects the result/audit contract without relying on thread timing.
    """
    _insert_old_event(db)
    original_execute = db.execute

    class _NoRowsDeleted:
        @staticmethod
        def all():
            return []

    def execute_with_lost_delete(statement, *args, **kwargs):
        if isinstance(statement, Delete):
            return _NoRowsDeleted()
        return original_execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", execute_with_lost_delete)

    def unexpected_audit(*args, **kwargs):
        raise AssertionError("a zero-actual-delete race loser must not emit a deletion audit")

    monkeypatch.setattr(retention_job, "record_audit_event", unexpected_audit)

    result = retention_job._enforce_maximum_retention_core(
        db,
        _CATEGORY,
        apply=True,
        policies=_SYNTHETIC_POLICIES,
        table_map=_TABLE_MAP,
        batch_size=1,
        now=datetime.now(timezone.utc),
        actor="package-r",
    )

    assert result.deleted_count == 0
    assert result.deleted_ids == ()
    assert result.candidate_count == len(result.deleted_ids)


def test_row_corrected_after_selection_is_rechecked_before_delete(db, monkeypatch):
    """A stale selection must not delete a row that is no longer expired."""
    _insert_old_event(db, event_id="corrected-event")
    original_execute = db.execute
    selection_seen = False
    fixed_now = datetime.now(timezone.utc)

    def execute_with_timestamp_correction(statement, *args, **kwargs):
        nonlocal selection_seen
        result = original_execute(statement, *args, **kwargs)
        if isinstance(statement, Select) and not selection_seen:
            selection_seen = True
            original_execute(
                text(
                    "UPDATE audit_events SET created_at = :created_at "
                    "WHERE audit_id = :audit_id"
                ),
                {"created_at": fixed_now, "audit_id": "corrected-event"},
            )
        return result

    monkeypatch.setattr(db, "execute", execute_with_timestamp_correction)

    result = retention_job._enforce_maximum_retention_core(
        db,
        _CATEGORY,
        apply=True,
        policies=_SYNTHETIC_POLICIES,
        table_map=_TABLE_MAP,
        batch_size=1,
        now=fixed_now,
        actor="package-r",
    )

    assert result.deleted_count == 0
    assert db.query(AuditEvent).filter_by(audit_id="corrected-event").count() == 1


def test_audit_failure_rolls_back_the_bounded_delete(db, monkeypatch):
    _insert_old_event(db, event_id="rollback-event")

    def fail_audit(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(retention_job, "record_audit_event", fail_audit)

    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        retention_job._enforce_maximum_retention_core(
            db,
            _CATEGORY,
            apply=True,
            policies=_SYNTHETIC_POLICIES,
            table_map=_TABLE_MAP,
            batch_size=1,
            now=datetime.now(timezone.utc),
            actor="package-r",
        )

    db.expire_all()
    assert db.query(AuditEvent).filter_by(audit_id="rollback-event").count() == 1
