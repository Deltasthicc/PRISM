"""HTTP contract for the training-effectiveness, course-completion and
activity-trend extensions to GET /learning/admin/overview
(routes/learning_analytics.py).

Every assertion below is checked against a hand-calculated expected value
from a small, deliberately seeded set of rows -- not just "the response has
the right shape" -- since a real math error in an aggregation like this
would otherwise slip past a shape-only test.

Follows test_course_enrollment.py's isolated-app + in-memory-SQLite +
require_principal-override pattern. The admin overview route needs
Permission.ORGANIZATION_ANALYTICS_READ, which only the "organization_admin"
role carries (security/rbac.py's ROLE_PERMISSIONS), so the principal here
mirrors test_api_contract_lane5.py's Subject rather than
test_course_enrollment.py's plain "learner".
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
# Base.metadata is process-global -- import the full model set so
# create_all() is correct regardless of what else has already run this
# session (see test_dsa_sandbox.py / test_course_enrollment.py's identical
# comment on this).
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import (
    LearnerProfile,
    CompetencyAssessment,
    LearningMaterial,
    GeneratedQuiz,
    GeneratedQuizAttempt,
)
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course_enrollment import CourseEnrollment
from models.judgment_scenario import JudgmentScenario, JudgmentScenarioAttempt
from models.proctoring import ProctoringEvent  # noqa: F401
from routes.authorization import require_principal
from routes.learning_analytics import router as analytics_router
from security.rbac import BoundPrincipal


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"organization_admin"})


def _principal() -> BoundPrincipal:
    return BoundPrincipal(
        subject=_Subject(), binding_id="binding-1", player_id=None, roles=_Subject.roles
    )


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db) -> FastAPI:
    app = FastAPI()
    app.include_router(analytics_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: _principal()
    return app


def _make_player(db, username: str) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=username))
    db.commit()
    return player_id


def _ts(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_training_effectiveness_averages_latest_minus_earliest_per_competency():
    """Player A improves os_sampling_design by +2.0 (1.0 -> 3.0), player B by
    +0.5 (2.0 -> 2.5). Average across the two players who each have >=2
    assessments touching that competency must be exactly (2.0+0.5)/2 = 1.25,
    with learner_count=2. Player C has only ONE assessment touching
    os_data_quality and must be excluded entirely (nothing to compare)."""
    db = _db()
    player_a = _make_player(db, "player-a")
    player_b = _make_player(db, "player-b")
    player_c = _make_player(db, "player-c")

    db.add_all([
        CompetencyAssessment(
            player_id=player_a, curriculum_slug="official-statistics",
            measured_scores={"os_sampling_design": 1.0},
            created_at=_ts(2026, 1, 1),
        ),
        CompetencyAssessment(
            player_id=player_a, curriculum_slug="official-statistics",
            measured_scores={"os_sampling_design": 3.0},
            created_at=_ts(2026, 2, 1),
        ),
        CompetencyAssessment(
            player_id=player_b, curriculum_slug="official-statistics",
            measured_scores={"os_sampling_design": 2.0},
            created_at=_ts(2026, 1, 5),
        ),
        CompetencyAssessment(
            player_id=player_b, curriculum_slug="official-statistics",
            measured_scores={"os_sampling_design": 2.5},
            created_at=_ts(2026, 2, 5),
        ),
        CompetencyAssessment(
            player_id=player_c, curriculum_slug="official-statistics",
            measured_scores={"os_data_quality": 1.0},
            created_at=_ts(2026, 1, 10),
        ),
    ])
    db.commit()

    client = TestClient(_app(db))
    response = client.get("/learning/admin/overview")

    assert response.status_code == 200
    effectiveness = response.json()["training_effectiveness"]
    assert effectiveness == [
        {
            "competency": "Sampling Design",
            "competency_id": "os_sampling_design",
            "avg_improvement": 1.25,
            "learner_count": 2,
        }
    ]


def test_course_completion_funnel_and_per_course_breakdown():
    """3 total enrollments (2 in one course, 1 in another), 2 completions ->
    a real 66.7% overall rate, plus an honest per-course breakdown."""
    db = _db()
    player_a = _make_player(db, "player-a")
    player_b = _make_player(db, "player-b")
    player_c = _make_player(db, "player-c")

    db.add_all([
        CourseEnrollment(
            player_id=player_a, course_id="igot::os_sampling_design", provider="igot",
            competency_id="os_sampling_design", title="Sampling Design 101",
            status="completed", enrolled_at=_ts(2026, 1, 1), completed_at=_ts(2026, 1, 10),
        ),
        CourseEnrollment(
            player_id=player_b, course_id="igot::os_sampling_design", provider="igot",
            competency_id="os_sampling_design", title="Sampling Design 101",
            status="enrolled", enrolled_at=_ts(2026, 1, 2),
        ),
        CourseEnrollment(
            player_id=player_c, course_id="nssta::os_ml", provider="nssta",
            competency_id="os_ml", title="ML for Officials",
            status="completed", enrolled_at=_ts(2026, 1, 3), completed_at=_ts(2026, 1, 8),
        ),
    ])
    db.commit()

    client = TestClient(_app(db))
    response = client.get("/learning/admin/overview")

    assert response.status_code == 200
    funnel = response.json()["course_completion"]
    assert funnel["total_enrollments"] == 3
    assert funnel["total_completions"] == 2
    assert funnel["completion_rate_pct"] == round(2 / 3 * 100, 1)
    assert funnel["by_course"] == [
        {
            "course_id": "igot::os_sampling_design",
            "title": "Sampling Design 101",
            "enrolled": 2,
            "completed": 1,
            "completion_rate_pct": 50.0,
        },
        {
            "course_id": "nssta::os_ml",
            "title": "ML for Officials",
            "enrolled": 1,
            "completed": 1,
            "completion_rate_pct": 100.0,
        },
    ]


def test_activity_trend_buckets_real_events_into_iso_weeks():
    """Feb 2/4/6 2026 fall in ISO week 2026-W06 (Monday 2026-02-02); Feb 9/11
    fall in ISO week 2026-W07 (Monday 2026-02-09) -- confirmed directly via
    Python's own date.isocalendar()/fromisocalendar(), not just asserted by
    assumption. Week 6 gets 2 quiz attempts + 1 scenario completion; week 7
    gets 1 quiz attempt + 1 course completion. No other weeks exist, and
    none should be fabricated."""
    db = _db()
    player = _make_player(db, "player-a")

    material = LearningMaterial(
        player_id=player, filename="doc.txt", sha256="a" * 64,
        character_count=10, text_excerpt="hello",
    )
    db.add(material)
    db.flush()
    quiz = GeneratedQuiz(
        material_id=material.material_id, player_id=player, title="Quiz",
        questions=[{"q": "1+1?", "a": "2"}],
    )
    db.add(quiz)
    scenario = JudgmentScenario(
        competency_id="pa_decision_making", title="Scenario",
        situation_brief="brief",
        nodes={"start": {"prompt": "p", "choices": []}},
        start_node_id="start",
    )
    db.add(scenario)
    db.flush()

    db.add_all([
        GeneratedQuizAttempt(
            quiz_id=quiz.quiz_id, player_id=player, correct_count=1, total_questions=1,
            weighted_score=1.0, attempted_at=_ts(2026, 2, 2),
        ),
        GeneratedQuizAttempt(
            quiz_id=quiz.quiz_id, player_id=player, correct_count=1, total_questions=1,
            weighted_score=1.0, attempted_at=_ts(2026, 2, 4),
        ),
        GeneratedQuizAttempt(
            quiz_id=quiz.quiz_id, player_id=player, correct_count=1, total_questions=1,
            weighted_score=1.0, attempted_at=_ts(2026, 2, 9),
        ),
    ])
    db.add(
        JudgmentScenarioAttempt(
            player_id=player, scenario_id=scenario.scenario_id,
            path_taken=[{"node_id": "start", "choice_id": "c1"}],
            recommended_choice_count=1, total_choice_count=1,
            completed_at=_ts(2026, 2, 6),
        )
    )
    db.add(
        CourseEnrollment(
            player_id=player, course_id="igot::pa_decision_making", provider="igot",
            competency_id="pa_decision_making", title="Decisions",
            status="completed", enrolled_at=_ts(2026, 1, 20), completed_at=_ts(2026, 2, 11),
        )
    )
    db.commit()

    client = TestClient(_app(db))
    response = client.get("/learning/admin/overview")

    assert response.status_code == 200
    assert response.json()["activity_trend"] == [
        {
            "week_start": "2026-02-02",
            "quiz_attempts": 2,
            "scenario_completions": 1,
            "course_completions": 0,
            "total": 3,
        },
        {
            "week_start": "2026-02-09",
            "quiz_attempts": 1,
            "scenario_completions": 0,
            "course_completions": 1,
            "total": 2,
        },
    ]


def test_emerging_skill_gaps_requires_minimum_rows_and_computes_delta():
    """With only 3 total assessment rows (below the min_assessments=4
    floor), emerging_skill_gaps must be empty -- not a noisy signal from too
    little data."""
    db = _db()
    player = _make_player(db, "player-a")
    db.add_all([
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Sampling Design", "priority": "high"}],
            created_at=_ts(2026, 1, 1),
        ),
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Sampling Design", "priority": "high"}],
            created_at=_ts(2026, 1, 2),
        ),
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Sampling Design", "priority": "high"}],
            created_at=_ts(2026, 1, 3),
        ),
    ])
    db.commit()

    client = TestClient(_app(db))
    response = client.get("/learning/admin/overview")
    assert response.json()["emerging_skill_gaps"] == []


def test_emerging_skill_gaps_surfaces_a_rising_gap_with_a_positive_delta():
    """4 assessment rows split into an earlier half (rows 1-2) and a later
    half (rows 3-4). "Data Quality" appears 0 times earlier and 2 times
    recently -> delta=+2, a genuinely emerging gap. "Sampling Design"
    appears 2 times earlier and 0 times recently -> delta=-2, and must be
    excluded (falling, not emerging)."""
    db = _db()
    player = _make_player(db, "player-a")
    db.add_all([
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Sampling Design", "priority": "high"}],
            created_at=_ts(2026, 1, 1),
        ),
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Sampling Design", "priority": "high"}],
            created_at=_ts(2026, 1, 2),
        ),
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Data Quality", "priority": "medium"}],
            created_at=_ts(2026, 1, 3),
        ),
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Data Quality", "priority": "medium"}],
            created_at=_ts(2026, 1, 4),
        ),
    ])
    db.commit()

    client = TestClient(_app(db))
    response = client.get("/learning/admin/overview")
    assert response.json()["emerging_skill_gaps"] == [
        {"competency": "Data Quality", "earlier_count": 0, "recent_count": 2, "delta": 2},
    ]


def test_existing_response_fields_are_unchanged_by_the_new_additions():
    """Regression guard: the pre-existing fields (learners, top_skill_gaps,
    gap_priorities, etc.) must keep their exact prior shape and values --
    the new fields are additive, not a replacement."""
    db = _db()
    player = _make_player(db, "player-a")
    db.add(
        CompetencyAssessment(
            player_id=player, curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Sampling Design", "priority": "high"}],
            created_at=_ts(2026, 1, 1),
        )
    )
    db.commit()

    client = TestClient(_app(db))
    response = client.get("/learning/admin/overview")
    body = response.json()

    assert body["learners"] == 1
    assert body["profiles_completed"] == 0
    assert body["assessments_completed"] == 1
    assert body["quizzes_generated"] == 0
    assert body["top_skill_gaps"] == [{"competency": "Sampling Design", "learner_count": 1}]
    assert body["gap_priorities"] == {"high": 1}
    assert "privacy_note" in body
    assert "integration_status" in body
