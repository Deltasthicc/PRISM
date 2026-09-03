"""Lane 5 API, authorization, provider and analytics contract tests."""

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.learning import CompetencyAssessment
from models.player import Player
from routes.learning import admin_overview, latest_assessment
from routes.authorization import require_permission_dependency, require_principal
from security.identity import AuthenticationError
from security.rbac import BoundPrincipal, Permission
from integrations.provider import SimulatedIGOTAdapter


class Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"organization_admin", "learner"})


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_principal(player_id=None):
    return BoundPrincipal(
        subject=Subject(),
        binding_id="binding-1",
        player_id=player_id,
        roles=Subject.roles,
    )


def test_admin_analytics_count_latest_assessment_stream_once():
    db = make_db()
    player = Player(username="learner-1")
    db.add(player)
    db.flush()
    db.add_all([
        CompetencyAssessment(
            assessment_id="old",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Old gap", "priority": "high"}],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        CompetencyAssessment(
            assessment_id="new",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Current gap", "priority": "medium"}],
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
    ])
    db.commit()

    result = __import__("asyncio").run(admin_overview(db, make_principal()))

    assert result["assessments_completed"] == 1
    assert result["top_skill_gaps"] == [{"competency": "Current gap", "learner_count": 1}]
    assert result["gap_priorities"] == {"medium": 1}


def test_latest_assessment_returns_latest_stream():
    db = make_db()
    player = Player(username="learner-2")
    db.add(player)
    db.flush()
    db.add_all([
        CompetencyAssessment(
            assessment_id="old",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            self_ratings={"old": 1},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        CompetencyAssessment(
            assessment_id="new",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            self_ratings={"new": 4},
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
    ])
    db.commit()

    result = __import__("asyncio").run(
        latest_assessment(
            player.player_id,
            "official-statistics",
            db,
            make_principal(player.player_id),
        )
    )

    assert result["assessment"]["assessment_id"] == "new"
    assert result["assessment"]["self_ratings"] == {"new": 4}


def test_simulated_igot_never_claims_live_capability():
    adapter = SimulatedIGOTAdapter()

    result = adapter.health_check()

    assert result.status == "SIMULATED"
    assert result.data == {"capabilities": []}
    assert adapter.request_enrolment("course-1", idempotency_key="request-1").data["accepted"] is False


def test_route_auth_adapter_returns_401_for_missing_or_invalid_bearer(monkeypatch):
    def reject(_header):
        raise AuthenticationError("invalid")

    monkeypatch.setattr("routes.authorization.get_current_subject", reject)

    with pytest.raises(HTTPException) as error:
        require_principal(None, make_db())

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_route_auth_adapter_returns_403_for_missing_permission():
    dependency = require_permission_dependency(Permission.ORGANIZATION_ANALYTICS_READ)

    with pytest.raises(HTTPException) as error:
        dependency(make_principal("player-1").__class__(
            subject=Subject(), binding_id="binding-1", player_id="player-1", roles=frozenset({"learner"})
        ))

    assert error.value.status_code == 403


@pytest.mark.parametrize("permission", [Permission.ASSESSMENT_SELF_READ, Permission.ORGANIZATION_ANALYTICS_READ])
def test_lane5_permissions_are_explicit(permission):
    assert permission.value
