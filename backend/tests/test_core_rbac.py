"""Lane 2 tests for issuer-scoped identity binding and RBAC decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.governance import AuditEvent
from models.guild import Guild  # noqa: F401
from models.identity import IdentityBinding
from models.learning import (  # noqa: F401
    CompetencyAssessment,
    GeneratedQuiz,
    LearnerProfile,
    LearningMaterial,
)
from models.player import Player
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from schemas.identity import IdentityBindingCreate, IdentityBindingResponse
from security.identity import AuthenticatedSubject
from security.rbac import (
    DEPLOYMENT_TENANT_SCOPE,
    AuthorizationError,
    BoundPrincipal,
    IdentityBindingConflict,
    Permission,
    PrincipalBindingError,
    create_identity_binding,
    deactivate_identity_binding,
    effective_roles,
    permissions_for,
    require_any_role,
    require_deployment_tenant,
    require_permission,
    reactivate_identity_binding,
    resolve_bound_principal,
    scoped_to_own_player,
)


ISSUER = "https://identity.example.test/realms/sih"
PLAYER_ID = "rbac-player"
OTHER_PLAYER_ID = "rbac-other-player"


@dataclass(frozen=True)
class SyntheticSubject:
    subject_id: str
    issuer: str = ISSUER
    roles: frozenset[str] = frozenset()
    username: str | None = None
    expires_at: datetime = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            Player(player_id=PLAYER_ID, username="rbac_player"),
            Player(player_id=OTHER_PLAYER_ID, username="rbac_other_player"),
        ]
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _binding(
    db,
    subject_id: str,
    *,
    player_id: str | None = None,
    active: bool = True,
    issuer: str = ISSUER,
) -> IdentityBinding:
    row = IdentityBinding(
        binding_id=f"binding-{subject_id}",
        issuer=issuer,
        subject_id=subject_id,
        player_id=player_id,
        active=active,
    )
    db.add(row)
    db.commit()
    return row


def _principal(
    db,
    subject_id: str,
    roles: set[str],
    *,
    player_id: str | None = None,
) -> BoundPrincipal:
    _binding(db, subject_id, player_id=player_id)
    return resolve_bound_principal(
        db,
        SyntheticSubject(subject_id=subject_id, roles=frozenset(roles)),
    )


def test_resolves_exact_issuer_subject_and_does_not_equate_sub_with_player(db):
    _binding(db, "external-random-subject", player_id=PLAYER_ID)
    subject = SyntheticSubject(
        subject_id="external-random-subject",
        roles=frozenset({"learner", "untrusted-realm-admin"}),
        username=PLAYER_ID,
    )

    principal = resolve_bound_principal(db, subject)

    assert principal.player_id == PLAYER_ID
    assert principal.subject.subject_id != principal.player_id
    assert principal.roles == frozenset({"learner"})
    assert principal.tenant_scope == DEPLOYMENT_TENANT_SCOPE


def test_authn_subject_contract_composes_with_bound_principal(db):
    _binding(db, "authn-subject", player_id=PLAYER_ID)
    subject = AuthenticatedSubject(
        subject_id="authn-subject",
        username="display-only",
        roles=frozenset({"learner"}),
        issuer=ISSUER,
        expires_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        raw_claims={"sub": "authn-subject"},
    )

    principal = resolve_bound_principal(db, subject)

    assert principal.player_id == PLAYER_ID
    assert principal.roles == frozenset({"learner"})


@pytest.mark.parametrize("failure", ["issuer", "subject", "inactive"])
def test_resolution_fails_closed_for_nonmatching_or_inactive_binding(db, failure):
    binding = _binding(db, "known-subject", player_id=PLAYER_ID)
    subject = SyntheticSubject(subject_id="known-subject")
    if failure == "issuer":
        subject = SyntheticSubject(
            subject_id="known-subject",
            issuer="https://other.example.test/realms/sih",
        )
    elif failure == "subject":
        subject = SyntheticSubject(subject_id="unknown-subject")
    else:
        binding.active = False
        db.commit()

    with pytest.raises(PrincipalBindingError):
        resolve_bound_principal(db, subject)


@pytest.mark.parametrize(
    "issuer",
    [
        "http://identity.example.test/realm",
        "relative/issuer",
        "https://id.test/r?q=1",
        "https://user@id.test/realm",
        " https://id.test/realm",
        "https://id.test/re\nalm",
        "https://id.test/re\talm",
        "https://id.test/re\x00alm",
        "https://id.test:invalid/realm",
        "https://id.test:70000/realm",
    ],
)
def test_resolution_rejects_unsafe_issuer_shapes_before_lookup(db, issuer):
    with pytest.raises(AuthorizationError):
        resolve_bound_principal(
            db,
            SyntheticSubject(subject_id="subject", issuer=issuer),
        )


def test_loopback_http_issuer_is_allowed_only_for_local_provider(db):
    _binding(
        db,
        "local-subject",
        issuer="http://localhost:8081/realms/sih-learning",
    )
    principal = resolve_bound_principal(
        db,
        SyntheticSubject(
            subject_id="local-subject",
            issuer="http://localhost:8081/realms/sih-learning",
        ),
    )
    assert principal.binding_id == "binding-local-subject"


def test_role_gate_requires_a_bound_principal_and_allowlists_assertions(db):
    learner = SyntheticSubject(
        subject_id="subject",
        roles=frozenset({"learner", "made_up_superuser"}),
    )
    _binding(db, "subject", player_id=PLAYER_ID)
    principal = resolve_bound_principal(db, learner)
    assert require_any_role("learner")(principal) is principal
    with pytest.raises(AuthorizationError):
        require_any_role("auditor")(principal)
    with pytest.raises(ValueError, match="at least one"):
        require_any_role()
    with pytest.raises(ValueError, match="unknown application roles"):
        require_any_role("made_up_superuser")
    assert effective_roles(learner) == frozenset({"learner"})


def test_permission_matrix_is_minimal_and_does_not_grant_trainer_cross_subject(db):
    trainer = _principal(db, "trainer-subject", {"trainer"})
    assert Permission.CONTENT_DRAFT_CREATE in permissions_for(trainer)
    with pytest.raises(AuthorizationError):
        require_permission(trainer, Permission.SUBJECT_DATA_EXPORT)
    with pytest.raises(AuthorizationError):
        scoped_to_own_player(trainer, PLAYER_ID)

    auditor = _principal(db, "auditor-subject", {"auditor"})
    require_permission(auditor, Permission.SUBJECT_DATA_EXPORT)
    with pytest.raises(AuthorizationError):
        require_permission(auditor, Permission.SUBJECT_DATA_DELETE)

    department_admin = _principal(
        db,
        "department-admin-subject",
        {"department_admin"},
    )
    with pytest.raises(AuthorizationError):
        require_permission(
            department_admin,
            Permission.DEPARTMENT_ANALYTICS_READ,
        )


def test_learner_object_scope_uses_bound_player_not_username_or_sub(db):
    learner = _principal(db, "opaque-oidc-sub", {"learner"}, player_id=PLAYER_ID)
    require_permission(learner, Permission.PROFILE_SELF_READ)
    scoped_to_own_player(learner, PLAYER_ID)
    with pytest.raises(AuthorizationError):
        scoped_to_own_player(learner, OTHER_PLAYER_ID)
    with pytest.raises(AuthorizationError):
        scoped_to_own_player(learner, "opaque-oidc-sub")


def test_forged_tenant_scope_is_rejected(db):
    principal = _principal(db, "tenant-subject", {"learner"}, player_id=PLAYER_ID)
    require_deployment_tenant(principal)
    forged = BoundPrincipal(
        subject=principal.subject,
        binding_id=principal.binding_id,
        player_id=principal.player_id,
        roles=principal.roles,
        tenant_scope="client-supplied-tenant",
    )
    with pytest.raises(AuthorizationError):
        require_deployment_tenant(forged)


def test_audit_actor_encoding_cannot_collide_on_pipe_delimiters(db):
    # A plain f"{issuer}|{subject_id}" join (the original shape) is not
    # injective: neither validate_issuer() nor security.identity.verify()
    # rejects a literal "|" in the subject_id. Two different (issuer,
    # subject_id) pairs must not be able to produce the same audit_actor
    # string, matching the same fix already applied to
    # identity_bootstrap.expected_bootstrap_confirmation().
    principal_a = _principal(db, "a|b", {"learner"})
    _binding(db, "b", player_id=None, issuer=f"{ISSUER}|a")
    principal_b = resolve_bound_principal(
        db, SyntheticSubject(subject_id="b", issuer=f"{ISSUER}|a", roles=frozenset({"learner"}))
    )

    assert principal_a.audit_actor != principal_b.audit_actor
    assert principal_a.audit_actor == json.dumps(
        {"issuer": ISSUER, "subject_id": "a|b"}, sort_keys=True, separators=(",", ":")
    )


def test_organization_admin_creates_binding_and_audit_atomically(db):
    admin = _principal(db, "admin-subject", {"organization_admin"})

    binding = create_identity_binding(
        db,
        actor=admin,
        issuer=ISSUER,
        subject_id="new-subject",
        player_id=PLAYER_ID,
        reason="approved synthetic account link",
    )

    assert binding.player_id == PLAYER_ID
    event_row = db.query(AuditEvent).filter_by(action="identity_binding.create").one()
    assert event_row.actor == admin.audit_actor
    assert event_row.entity_id == binding.binding_id
    assert event_row.details["reason"] == "approved synthetic account link"

    response = IdentityBindingResponse.model_validate(binding)
    assert response.subject_id == "new-subject"


def test_binding_create_denies_non_admin_and_conflicts_fail_closed(db):
    learner = _principal(db, "learner-subject", {"learner"}, player_id=PLAYER_ID)
    with pytest.raises(AuthorizationError):
        create_identity_binding(
            db,
            actor=learner,
            issuer=ISSUER,
            subject_id="denied-subject",
            player_id=None,
            reason="must be denied",
        )

    admin = _principal(db, "admin-subject", {"organization_admin"})
    create_identity_binding(
        db,
        actor=admin,
        issuer=ISSUER,
        subject_id="first-subject",
        player_id=OTHER_PLAYER_ID,
        reason="first",
    )
    before_audits = db.query(AuditEvent).count()
    with pytest.raises(IdentityBindingConflict):
        create_identity_binding(
            db,
            actor=admin,
            issuer=ISSUER,
            subject_id="second-subject",
            player_id=OTHER_PLAYER_ID,
            reason="conflict",
        )
    assert db.query(AuditEvent).count() == before_audits


def test_privileged_write_rechecks_that_admin_binding_is_still_active(db):
    admin = _principal(db, "admin-subject", {"organization_admin"})
    admin_row = db.query(IdentityBinding).filter_by(binding_id=admin.binding_id).one()
    admin_row.active = False
    db.commit()

    with pytest.raises(PrincipalBindingError, match="no longer active"):
        create_identity_binding(
            db,
            actor=admin,
            issuer=ISSUER,
            subject_id="new-subject",
            player_id=None,
            reason="must fail after revocation",
        )
    assert db.query(AuditEvent).count() == 0


def test_deactivation_is_audited_and_future_resolution_fails(db):
    admin = _principal(db, "admin-subject", {"organization_admin"})
    target = _binding(db, "target-subject", player_id=PLAYER_ID)

    result = deactivate_identity_binding(
        db,
        actor=admin,
        binding_id=target.binding_id,
        reason="synthetic access revoked",
    )

    assert result.active is False
    assert db.query(AuditEvent).filter_by(action="identity_binding.deactivate").count() == 1
    with pytest.raises(PrincipalBindingError):
        resolve_bound_principal(db, SyntheticSubject(subject_id="target-subject"))

    reactivated = reactivate_identity_binding(
        db,
        actor=admin,
        binding_id=target.binding_id,
        reason="approved synthetic recovery",
    )
    assert reactivated.active is True
    assert db.query(AuditEvent).filter_by(action="identity_binding.reactivate").count() == 1
    assert (
        resolve_bound_principal(
            db,
            SyntheticSubject(subject_id="target-subject", roles=frozenset({"learner"})),
        ).player_id
        == PLAYER_ID
    )


def test_create_rolls_back_binding_and_audit_when_commit_fails(db, monkeypatch):
    admin = _principal(db, "admin-subject", {"organization_admin"})
    real_commit = db.commit

    def _fail_commit():
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db, "commit", _fail_commit)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        create_identity_binding(
            db,
            actor=admin,
            issuer=ISSUER,
            subject_id="rollback-subject",
            player_id=PLAYER_ID,
            reason="rollback proof",
        )
    monkeypatch.setattr(db, "commit", real_commit)
    db.expire_all()
    assert db.query(IdentityBinding).filter_by(subject_id="rollback-subject").count() == 0
    assert db.query(AuditEvent).filter_by(action="identity_binding.create").count() == 0


def test_identity_binding_schema_rejects_empty_or_oversized_identifiers():
    with pytest.raises(ValidationError):
        IdentityBindingCreate(issuer="", subject_id="subject")
    with pytest.raises(ValidationError):
        IdentityBindingCreate(issuer=ISSUER, subject_id="x" * 501)
