"""HTTP contract for the bounded, source-attributed demo competency quiz."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, get_db
from main import app
from models.accuracy_history import AccuracyHistory
from models.governance import AuditEvent, EvidenceRecord
from models.player import Player
from routes.competency_quiz import TOPICS
from services.hand_authored_questions import questions_for_competency

client = TestClient(app)
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def issue(topic_id: str, count: int = 5) -> dict:
    response = client.get(
        "/learning/competency-quiz/questions",
        params={"topic_id": topic_id, "count": count},
    )
    assert response.status_code == 200
    return response.json()


def answer_key(topic_id: str) -> dict[str, dict]:
    """Maps item_id -> the raw hand-authored item, so callers can branch on
    question_type rather than assuming every item is an MCQ."""
    return {
        item["item_id"]: item
        for competency_id in TOPICS[topic_id]["competency_ids"]
        for item in questions_for_competency(competency_id)
    }


def submit_payload(issued: dict, *, correct: bool, player_id: str | None = None) -> dict:
    key = answer_key(issued["topic_id"])
    answers = []
    for question in issued["questions"]:
        item = key[question["item_id"]]
        if item.get("question_type", "mcq") == "mcq":
            expected = item["answer_index"]
            answers.append(
                {
                    "item_id": question["item_id"],
                    "selected_index": expected if correct else (expected + 1) % 4,
                }
            )
        else:
            answer_text = item["accepted_answers"][0] if correct else "definitely-not-the-right-answer"
            answers.append({"item_id": question["item_id"], "answer_text": answer_text})
    return {
        "attempt_id": issued["attempt_id"],
        "topic_id": issued["topic_id"],
        "answers": answers,
        **({"player_id": player_id} if player_id else {}),
    }


def test_topics_are_honest_nonempty_bank_slices():
    response = client.get("/learning/competency-quiz/topics")
    assert response.status_code == 200
    topics = response.json()
    assert len(topics) == len(TOPICS)
    assert {topic["topic_id"] for topic in topics} == set(TOPICS)
    for topic in topics:
        assert topic["question_count"] >= 2
        assert all(
            questions_for_competency(competency_id)
            for competency_id in topic["competency_ids"]
        ), f"{topic['topic_id']} advertises a competency with no item"


def test_questions_are_bounded_balanced_ordered_and_do_not_leak_answers():
    data = issue("statistical_foundations", 5)
    assert data["assessment_status"] == "PROVISIONAL"
    assert len(data["questions"]) == 5
    assert {question["competency_id"] for question in data["questions"]} == {
        "os_statistical_foundations",
        "os_sampling_design",
        "os_survey_design",
    }
    difficulties = [DIFFICULTY_ORDER[question["difficulty"]] for question in data["questions"]]
    assert difficulties == sorted(difficulties)
    for question in data["questions"]:
        assert set(question) == {
            "item_id", "question", "question_type", "options", "competency_id", "competency_label",
            "difficulty", "doc_id", "locator", "item_status",
        }
        assert question["item_status"] == "DRAFT"
        assert question["question_type"] == "mcq"
        assert len(question["options"]) == 4


@pytest.mark.parametrize("count", [0, -1, 11, 100_000])
def test_question_count_is_strictly_bounded(count):
    response = client.get(
        "/learning/competency-quiz/questions",
        params={"topic_id": "statistical_foundations", "count": count},
    )
    assert response.status_code == 422


def test_unknown_topic_is_rejected():
    response = client.get(
        "/learning/competency-quiz/questions", params={"topic_id": "not-a-real-topic"}
    )
    assert response.status_code == 404


def test_neither_topic_nor_competency_is_rejected():
    response = client.get("/learning/competency-quiz/questions")
    assert response.status_code == 422


def test_competency_id_scopes_questions_to_just_that_competency():
    """A Prerequisite Pathways room practicing one competency (e.g. "arrays")
    must never pull in its topic's other bundled competencies (linked_lists,
    stacks_queues) -- that would silently test something the learner didn't
    ask to practice."""
    response = client.get(
        "/learning/competency-quiz/questions",
        params={"competency_id": "arrays", "count": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == "linear_structures"  # resolved internally, not caller-supplied
    assert data["label"] == "Arrays"  # the competency's own label, not the whole topic's
    assert data["questions"]
    assert {q["competency_id"] for q in data["questions"]} == {"arrays"}


def test_unknown_competency_id_is_rejected():
    response = client.get(
        "/learning/competency-quiz/questions", params={"competency_id": "not-a-real-competency"}
    )
    assert response.status_code == 404


def test_competency_id_attempt_submits_and_grades_like_any_other():
    issued = client.get(
        "/learning/competency-quiz/questions",
        params={"competency_id": "arrays", "count": 2},
    ).json()
    key = {
        item["item_id"]: item for item in questions_for_competency("arrays")
    }
    answers = []
    for question in issued["questions"]:
        item = key[question["item_id"]]
        if item.get("question_type", "mcq") == "mcq":
            answers.append({"item_id": question["item_id"], "selected_index": item["answer_index"]})
        else:
            answers.append({"item_id": question["item_id"], "answer_text": item["accepted_answers"][0]})
    response = client.post(
        "/learning/competency-quiz/submit",
        json={"attempt_id": issued["attempt_id"], "topic_id": issued["topic_id"], "answers": answers},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] == body["total"] == len(issued["questions"])
    assert {score["competency_id"] for score in body["competency_scores"]} == {"arrays"}


def test_submit_grades_and_ranks_without_calling_it_self_assessment():
    issued = issue("ai_policy", 5)
    response = client.post(
        "/learning/competency-quiz/submit", json=submit_payload(issued, correct=True)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] == body["total"] == len(issued["questions"])
    assert body["score_percentage"] == 100
    assert body["assessment_status"] == "PROVISIONAL"
    assert "self_ratings" not in body
    assert set(body["diagnostic_scores"]) == {
        score["competency_id"] for score in body["competency_scores"]
    }
    assert [score["rank"] for score in body["competency_scores"]] == list(
        range(1, len(body["competency_scores"]) + 1)
    )
    # dl_ai_literacy still has only one real question, so one attempt keeps it
    # at "low" confidence; os_ml has since gained several more real questions
    # (services/ps02_coverage.py's weakest-covered technical competency, now
    # backed by NITI Aayog's National Strategy for AI), so a 5-question draw
    # genuinely pulls enough os_ml evidence to earn a higher confidence tier --
    # that is the correct behavior, not a regression, so this assertion tracks
    # the real evidence count rather than a stale "everything stays low" claim.
    scores_by_competency = {score["competency_id"]: score for score in body["competency_scores"]}
    assert scores_by_competency["dl_ai_literacy"]["confidence"] == "low"
    assert scores_by_competency["os_ml"]["confidence"] in {"moderate", "high"}


def test_submit_requires_exact_issued_set_and_rejects_duplicate_and_cross_topic():
    issued = issue("data_quality", 2)
    payload = submit_payload(issued, correct=False)
    partial = {**payload, "answers": payload["answers"][:1]}
    assert client.post("/learning/competency-quiz/submit", json=partial).status_code == 422
    duplicate = {**payload, "answers": [payload["answers"][0], payload["answers"][0]]}
    assert client.post("/learning/competency-quiz/submit", json=duplicate).status_code == 422
    wrong_topic = {**payload, "topic_id": "price_statistics"}
    assert client.post("/learning/competency-quiz/submit", json=wrong_topic).status_code == 422


def test_attempt_is_single_use():
    issued = issue("data_privacy", 2)
    payload = submit_payload(issued, correct=False)
    assert client.post("/learning/competency-quiz/submit", json=payload).status_code == 200
    assert client.post("/learning/competency-quiz/submit", json=payload).status_code == 409


def test_fast_correct_answers_score_at_least_as_high_as_untimed():
    # data_privacy has exactly one competency (dl_data_privacy) with exactly
    # 3 real questions, so count=3 guarantees evidence_count == 3 for it --
    # the >=3 threshold "high" confidence requires.
    issued = issue("data_privacy", 3)
    payload = submit_payload(issued, correct=True)
    for answer in payload["answers"]:
        answer["time_taken_ms"] = 1000  # far faster than any difficulty's reference time
    body = client.post("/learning/competency-quiz/submit", json=payload).json()
    for score in body["competency_scores"]:
        assert score["avg_time_factor"] >= 1.0
        assert score["provisional_level"] == 5.0  # still capped at the max, never exceeds it
        assert score["confidence"] == "high"


def test_slow_correct_answers_reduce_confidence_but_not_below_a_reasonable_floor():
    issued = issue("data_privacy", 3)
    payload = submit_payload(issued, correct=True)
    for answer in payload["answers"]:
        answer["time_taken_ms"] = 10 * 60 * 1000  # far slower than any difficulty's reference time
    body = client.post("/learning/competency-quiz/submit", json=payload).json()
    for score in body["competency_scores"]:
        assert score["avg_time_factor"] == pytest.approx(0.85, abs=0.01)
        assert 4.0 <= score["provisional_level"] < 5.0  # nudged down, but accuracy still dominates
        assert score["confidence"] == "moderate"  # never "low" just for being slow while still correct


def test_fast_wrong_answers_do_not_score_above_zero():
    issued = issue("statistical_foundations", 5)
    fast_wrong = submit_payload(issued, correct=False)
    for answer in fast_wrong["answers"]:
        answer["time_taken_ms"] = 500  # answering instantly does not rescue a wrong answer
    body = client.post("/learning/competency-quiz/submit", json=fast_wrong).json()
    assert all(score["provisional_level"] == 0.0 for score in body["competency_scores"])


def test_missing_timing_data_scores_exactly_as_before():
    issued = issue("statistical_foundations", 5)
    payload = submit_payload(issued, correct=True)
    body = client.post("/learning/competency-quiz/submit", json=payload).json()
    for score in body["competency_scores"]:
        assert score["avg_time_factor"] == 1.0
        assert score["provisional_level"] == 5.0


def test_submission_persists_separate_diagnostic_evidence_and_audit(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'quiz.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    player = Player(username=f"quiz-{uuid.uuid4()}")
    db.add(player)
    db.commit()
    db.refresh(player)

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        issued = issue("price_statistics", 2)
        response = client.post(
            "/learning/competency-quiz/submit",
            json=submit_payload(issued, correct=True, player_id=player.player_id),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["persisted_as_diagnostic_evidence"] is True
        records = db.query(EvidenceRecord).filter_by(player_id=player.player_id).all()
        assert len(records) == len(body["competency_scores"])
        assert {record.evidence_type for record in records} == {"observed_practice"}
        assert all('\"provisional\":true' in record.detail for record in records)
        assert db.query(AuditEvent).filter_by(action="competency_quiz.submit").count() == 1

        # Regression coverage: routes/game.py's _is_room_unlocked_for_player
        # and _annotate_rooms_for_player read ONLY AccuracyHistory to decide
        # a Prerequisite Pathways room's locked/unlocked/weak/mastered status
        # and next_topic -- for every curriculum, not just DSA (AccuracyHistory
        # is keyed by plain competency_id strings). Before this fix,
        # competency-quiz submissions wrote EvidenceRecord only, so a learner
        # could ace this quiz and the dungeon map would never move for any
        # course or topic. One row per competency_id scored, matching
        # dsa_sandbox.py's submit path exactly.
        accuracy_rows = db.query(AccuracyHistory).filter_by(player_id=player.player_id).all()
        assert {row.topic for row in accuracy_rows} == {
            score["competency_id"] for score in body["competency_scores"]
        }
        for row in accuracy_rows:
            assert row.attempts > 0
            assert row.recent_accuracy > 0.65
            assert row.mastered is True  # is_proven()'s accuracy ratchet, all-correct submission
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_repeated_submissions_accumulate_the_same_accuracy_history_row(tmp_path):
    """Two separate quiz submissions for the same competency must update one
    running AccuracyHistory row, not create duplicates or reset progress --
    the same row's `attempts`/`last_5_results` are what a later submission's
    rolling accuracy is computed from."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'quiz2.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    player = Player(username=f"quiz-{uuid.uuid4()}")
    db.add(player)
    db.commit()
    db.refresh(player)

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        for _ in range(2):
            issued = issue("data_quality", 2)
            response = client.post(
                "/learning/competency-quiz/submit",
                json=submit_payload(issued, correct=True, player_id=player.player_id),
            )
            assert response.status_code == 200
        rows = db.query(AccuracyHistory).filter_by(player_id=player.player_id).all()
        assert len(rows) == 1
        assert rows[0].attempts == 4
        assert rows[0].correct == 4
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
