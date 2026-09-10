"""HTTP contract for the real-execution DSA sandbox (routes/dsa_sandbox.py).

Judge0 itself is mocked (monkeypatched at the point routes/dsa_sandbox.py
imported it, same idiom test_combat_model.py uses for the Gemini AI client)
so these tests are deterministic and don't depend on network access to a
third-party judge -- the problems' own reference solutions were separately
verified against the real, live Judge0 CE instance during development (see
the DSA sandbox PR description), which is what this test suite cannot
itself prove and doesn't try to.

Follows test_api_integration_game_authorization.py's isolated-app +
in-memory-SQLite + require_principal-override pattern rather than the
shared main.app + file-backed app.db some older test files use, since this
route is owner-scoped (require_own_player) and needs a real bound principal
to exercise properly.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
# Base.metadata is process-global and every model's foreign keys must
# resolve within it -- importing the same full model set main.py does
# (rather than only what this route touches directly) keeps
# Base.metadata.create_all() below correct regardless of which other test
# modules have or haven't already run in this pytest session.
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from models.governance import RoleTarget, EvidenceRecord, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
import routes.dsa_sandbox as dsa_sandbox_routes
from routes.authorization import require_principal
from routes.dsa_sandbox import router as dsa_sandbox_router
from security.rbac import BoundPrincipal
from services import dsa_lang_gen
from services.dsa_problems import PROBLEMS, PROBLEM_GUIDANCE


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"learner"})


def _principal(player_id: str) -> BoundPrincipal:
    return BoundPrincipal(subject=_Subject(), binding_id="binding-1", player_id=player_id, roles=_Subject.roles)


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, principal: BoundPrincipal | None) -> FastAPI:
    app = FastAPI()
    app.include_router(dsa_sandbox_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"dsa-sandbox-{player_id[:8]}"))
    db.commit()
    return player_id


def _mock_judge(monkeypatch, results):
    """results: a list of per-call return dicts, consumed in order."""
    calls = iter(results)

    async def fake_run_test_case(source_code, stdin, expected_output, language="python"):
        return next(calls)

    monkeypatch.setattr(dsa_sandbox_routes, "run_test_case", fake_run_test_case)


def test_problem_bank_covers_every_dsa_topic_with_real_test_cases():
    db = _db()
    client = TestClient(_app(db, None))
    response = client.get("/learning/dsa-sandbox/problems")
    assert response.status_code == 200
    body = response.json()
    problems = body["problems"]
    assert len(problems) == len(PROBLEMS)
    assert len(problems) >= 22
    topics = {p["competency_id"] for p in problems}
    assert topics == {p["competency_id"] for p in PROBLEMS}
    pattern_labels = {p["topic_label"] for p in problems}
    assert {
        "Hash Maps",
        "Strings & Sliding Window",
        "Two Pointers",
        "Backtracking",
        "Greedy Intervals",
        "Matrices",
        "Prefix Sums",
        "Graph Traversal",
    } <= pattern_labels
    assert set(PROBLEM_GUIDANCE) == {p["id"] for p in PROBLEMS}
    assert set(body["languages"]) == set(dsa_lang_gen.LANGUAGES)
    for problem in problems:
        assert problem["test_case_count"] >= 3
        assert "def solve" in problem["starter_code"]
        # Every advertised language must have real, generated starter code
        # -- not just Python.
        assert set(problem["starter_code_by_language"]) == set(dsa_lang_gen.LANGUAGES)
        assert "solve" in problem["starter_code_by_language"]["java"].lower()
        assert "solve" in problem["starter_code_by_language"]["cpp"].lower()
        assert "solve" in problem["starter_code_by_language"]["csharp"].lower()
        assert "solve" in problem["starter_code_by_language"]["javascript"].lower()
        assert len(problem["constraints"]) >= 2
        assert len(problem["examples"]) == 2
        assert all(example["explanation"] for example in problem["examples"])
        assert problem["solution_outline"]
        # The public view must never leak expected_output/full test cases.
        assert "expected_output" not in problem
        assert "test_cases" not in problem


def test_matrix_result_harnesses_serialize_nested_lists_in_every_language():
    """The interval problem returns int[][], including in C++ and C#."""
    problem = next(p for p in PROBLEMS if p["id"] == "sorting_merge_intervals")

    for language in dsa_lang_gen.LANGUAGES:
        starter = dsa_lang_gen.starter_code(language, problem)
        source = dsa_lang_gen.full_source(language, starter, problem)
        assert source

    cpp_source = dsa_lang_gen.full_source(
        "cpp", dsa_lang_gen.starter_code("cpp", problem), problem
    )
    csharp_source = dsa_lang_gen.full_source(
        "csharp", dsa_lang_gen.starter_code("csharp", problem), problem
    )
    assert "__wrap(const vector<vector<long long>>& matrix)" in cpp_source
    assert "List<System.Collections.Generic.List<long>> matrix" in csharp_source


def test_accepted_submission_persists_and_updates_accuracy_history(monkeypatch):
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    problem = PROBLEMS[0]
    _mock_judge(monkeypatch, [{"status": "accepted", "stdout": "ok", "stderr": None,
                               "compile_output": None, "time": "0.01", "passed": True}
                              for _ in problem["test_cases"]])

    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": player_id, "problem_id": problem["id"], "code": "def solve(*a): pass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["passed_count"] == body["total_count"] == len(problem["test_cases"])
    assert body["first_failure"] is None

    submission = db.query(DsaSubmission).filter(
        DsaSubmission.submission_id == body["submission_id"]
    ).first()
    assert submission is not None
    assert submission.status == "accepted"
    assert submission.competency_id == problem["competency_id"]

    acc = db.query(AccuracyHistory).filter(
        AccuracyHistory.player_id == player_id,
        AccuracyHistory.topic == problem["competency_id"],
    ).first()
    assert acc is not None
    assert acc.attempts == 1
    assert acc.correct == 1
    assert acc.recent_accuracy == 1.0


def test_accepted_submission_in_non_python_language_persists_language(monkeypatch):
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    problem = PROBLEMS[0]
    _mock_judge(monkeypatch, [{"status": "accepted", "stdout": "ok", "stderr": None,
                               "compile_output": None, "time": "0.01", "passed": True}
                              for _ in problem["test_cases"]])

    java_code = dsa_lang_gen.starter_code("java", problem)
    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={
            "player_id": player_id,
            "problem_id": problem["id"],
            "code": java_code,
            "language": "java",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"

    submission = db.query(DsaSubmission).filter(
        DsaSubmission.submission_id == body["submission_id"]
    ).first()
    assert submission.language == "java"


def test_submit_with_unknown_language_falls_back_to_python(monkeypatch):
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    problem = PROBLEMS[0]
    _mock_judge(monkeypatch, [{"status": "accepted", "stdout": "ok", "stderr": None,
                               "compile_output": None, "time": "0.01", "passed": True}
                              for _ in problem["test_cases"]])

    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={
            "player_id": player_id,
            "problem_id": problem["id"],
            "code": "def solve(*a): pass",
            "language": "not-a-real-language",
        },
    )
    assert response.status_code == 200
    submission = db.query(DsaSubmission).filter(
        DsaSubmission.submission_id == response.json()["submission_id"]
    ).first()
    assert submission.language == "python"


def test_wrong_answer_stops_at_first_failure_and_still_records_evidence(monkeypatch):
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    problem = PROBLEMS[0]
    _mock_judge(monkeypatch, [{
        "status": "wrong_answer", "stdout": "[9, 9]", "stderr": None,
        "compile_output": None, "time": "0.01", "passed": False,
    }])

    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": player_id, "problem_id": problem["id"], "code": "def solve(*a): return [9, 9]"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "wrong_answer"
    assert body["passed_count"] == 0
    assert body["first_failure"]["test_index"] == 0
    assert body["first_failure"]["actual_output"] == "[9, 9]"

    acc = db.query(AccuracyHistory).filter(
        AccuracyHistory.player_id == player_id,
        AccuracyHistory.topic == problem["competency_id"],
    ).first()
    assert acc is not None
    assert acc.attempts == 1
    assert acc.correct == 0
    assert acc.recent_accuracy == 0.0


def test_judge_unavailable_returns_503_and_does_not_record_evidence(monkeypatch):
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    problem = PROBLEMS[0]

    async def fake_run_test_case(source_code, stdin, expected_output, language="python"):
        raise dsa_sandbox_routes.JudgeUnavailableError("boom")

    monkeypatch.setattr(dsa_sandbox_routes, "run_test_case", fake_run_test_case)

    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": player_id, "problem_id": problem["id"], "code": "def solve(*a): pass"},
    )
    assert response.status_code == 503

    acc = db.query(AccuracyHistory).filter(
        AccuracyHistory.player_id == player_id,
        AccuracyHistory.topic == problem["competency_id"],
    ).first()
    assert acc is None


def test_unknown_problem_id_404s():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": player_id, "problem_id": "not-a-real-problem", "code": "def solve(*a): pass"},
    )
    assert response.status_code == 404


def test_unknown_player_id_404s():
    db = _db()
    player_id = str(uuid.uuid4())
    client = TestClient(_app(db, _principal(player_id)))
    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": player_id, "problem_id": PROBLEMS[0]["id"], "code": "def solve(*a): pass"},
    )
    assert response.status_code == 404


def test_submit_rejects_another_players_id():
    db = _db()
    player_id = _make_player(db)
    other_player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": other_player_id, "problem_id": PROBLEMS[0]["id"], "code": "def solve(*a): pass"},
    )
    assert response.status_code == 403


def test_submit_requires_verified_bearer():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, None))
    response = client.post(
        "/learning/dsa-sandbox/submit",
        json={"player_id": player_id, "problem_id": PROBLEMS[0]["id"], "code": "def solve(*a): pass"},
    )
    assert response.status_code == 401
