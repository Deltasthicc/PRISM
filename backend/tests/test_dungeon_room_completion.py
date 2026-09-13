"""Regression test for GET /game/dungeon/{id}'s room.completion field.

Real bug: a learner who only ever practiced via the plain, non-gamified
/practice page (routes/competency_quiz.py, AccuracyHistory.recent_accuracy)
was shown a permanent 0% completion on the Prerequisite Pathways map even
after being marked "mastered" -- room.completion was computed only from
Quest Mode's combat damage_dealt, a completely separate signal that
/practice never touches. Fixed in routes/game.py::_annotate_rooms_for_player
by taking whichever real signal (damage-based or accuracy-based) is
further along, not just the damage one.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon, Room
from models.guild import Guild  # noqa: F401
from models.learning import LearningMaterial  # noqa: F401
from models.player import Player
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from routes.authorization import require_principal
from routes.game import router as game_router
from security.rbac import BoundPrincipal


class Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"learner"})


def _principal(player_id: str | None) -> BoundPrincipal:
    return BoundPrincipal(subject=Subject(), binding_id="binding-1", player_id=player_id, roles=Subject.roles)


def _app(db, principal: BoundPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(game_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: principal
    return app


def _db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_accuracy_only_practice_still_shows_real_completion_percent():
    db = _db()
    player = Player(username="practice-only-learner")
    db.add(player)
    db.commit()

    dungeon = Dungeon(name="DSA Fundamentals", domain="dsa-fundamentals", curriculum_slug="dsa-fundamentals")
    db.add(dungeon)
    db.flush()
    # "arrays" has no prerequisites in services/knowledge_graph.TOPIC_GRAPH,
    # so it is unlocked for every player regardless of accuracy history --
    # isolates this test to the completion/status computation itself.
    room = Room(dungeon_id=dungeon.dungeon_id, topic="arrays", enemy_count=3, order_index=0)
    db.add(room)

    # Real signal from /practice: high accuracy, zero combat damage --
    # exactly what a learner who never touched Quest Mode combat has.
    db.add(
        AccuracyHistory(
            player_id=player.player_id,
            topic="arrays",
            attempts=5,
            correct=5,
            recent_accuracy=1.0,
            damage_dealt=0,
        )
    )
    db.commit()

    response = TestClient(_app(db, _principal(player.player_id))).get(
        f"/game/dungeon/{dungeon.dungeon_id}", params={"player_id": player.player_id}
    )

    assert response.status_code == 200
    body = response.json()
    arrays_room = next(r for r in body["rooms"] if r["topic"] == "arrays")
    assert arrays_room["status"] == "mastered"
    # The actual regression: completion must reflect the same real mastery
    # the status field already claims, not stay pinned at 0.
    assert arrays_room["completion"] == 1.0


def test_combat_only_progress_still_shows_completion_as_before():
    db = _db()
    player = Player(username="combat-only-learner")
    db.add(player)
    db.commit()

    dungeon = Dungeon(name="DSA Fundamentals", domain="dsa-fundamentals", curriculum_slug="dsa-fundamentals")
    db.add(dungeon)
    db.flush()
    room = Room(dungeon_id=dungeon.dungeon_id, topic="arrays", enemy_count=4, order_index=0)
    db.add(room)

    # Real signal from Quest Mode combat: damage dealt, no practice accuracy
    # recorded at all -- the original, pre-fix behavior for this case.
    db.add(
        AccuracyHistory(
            player_id=player.player_id,
            topic="arrays",
            attempts=0,
            correct=0,
            recent_accuracy=0.0,
            damage_dealt=2,
        )
    )
    db.commit()

    response = TestClient(_app(db, _principal(player.player_id))).get(
        f"/game/dungeon/{dungeon.dungeon_id}", params={"player_id": player.player_id}
    )

    assert response.status_code == 200
    arrays_room = next(r for r in response.json()["rooms"] if r["topic"] == "arrays")
    assert arrays_room["completion"] == 0.5
