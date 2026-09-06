"""routes/competency_quiz.py -- the real, source-cited competency quiz served
from services/hand_authored_questions.py, grouped into five topics.

No network, no live document fetch, no Gemini call -- everything here is
static, in-repo content, so these tests never skip and never flake.
"""
from fastapi.testclient import TestClient

from main import app
from routes.competency_quiz import TOPICS

client = TestClient(app)


def test_list_topics_returns_all_five_with_real_question_counts():
    response = client.get("/learning/competency-quiz/topics")
    assert response.status_code == 200
    topics = response.json()
    assert {topic["topic_id"] for topic in topics} == set(TOPICS.keys())
    for topic in topics:
        assert topic["question_count"] > 0, f"{topic['topic_id']} has no real questions available"


def test_get_questions_never_leaks_the_answer():
    response = client.get(
        "/learning/competency-quiz/questions", params={"topic_id": "statistical_foundations", "count": 5}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["topic_id"] == "statistical_foundations"
    assert len(data["questions"]) == 5
    for question in data["questions"]:
        assert set(question) == {
            "item_id", "question", "options", "competency_id",
            "competency_label", "difficulty", "doc_id", "locator",
        }
        assert len(question["options"]) == 4


def test_get_questions_rejects_unknown_topic():
    response = client.get("/learning/competency-quiz/questions", params={"topic_id": "not-a-real-topic"})
    assert response.status_code == 404


def test_get_questions_count_is_bounded_by_the_real_pool_size():
    # data_quality only has 2 real questions -- asking for 5 must not error
    # or fabricate extra items, just return what actually exists.
    response = client.get("/learning/competency-quiz/questions", params={"topic_id": "data_quality", "count": 5})
    assert response.status_code == 200
    assert len(response.json()["questions"]) == 2


def test_submit_grades_correctly_against_the_real_answer_key():
    questions = client.get(
        "/learning/competency-quiz/questions", params={"topic_id": "digital_governance", "count": 5}
    ).json()["questions"]

    # Deliberately get every answer wrong first, to prove correct=False is
    # reachable and not just a happy-path illusion.
    wrong_answers = [{"item_id": q["item_id"], "selected_index": 0} for q in questions]
    wrong_response = client.post(
        "/learning/competency-quiz/submit",
        json={"topic_id": "digital_governance", "answers": wrong_answers},
    )
    assert wrong_response.status_code == 200
    wrong_body = wrong_response.json()
    assert wrong_body["total"] == len(questions)
    # At least one of the two real digital_governance items must NOT have
    # its correct answer at index 0 after the shuffle -- otherwise this
    # "deliberately wrong" setup would coincidentally score 100%.
    assert wrong_body["correct"] < wrong_body["total"]

    # Now answer using the real correct_index from the graded response --
    # this proves the server, not the client, is the source of truth for
    # what counts as correct.
    correct_answers = [
        {"item_id": g["item_id"], "selected_index": g["correct_index"]}
        for g in wrong_body["graded_answers"]
    ]
    right_response = client.post(
        "/learning/competency-quiz/submit",
        json={"topic_id": "digital_governance", "answers": correct_answers},
    )
    right_body = right_response.json()
    assert right_body["correct"] == right_body["total"]
    assert right_body["score_percentage"] == 100


def test_submit_returns_self_ratings_shaped_for_the_assessment_endpoint():
    questions = client.get(
        "/learning/competency-quiz/questions", params={"topic_id": "ai_technology", "count": 5}
    ).json()["questions"]
    answers = [{"item_id": q["item_id"], "selected_index": 0} for q in questions]
    response = client.post("/learning/competency-quiz/submit", json={"topic_id": "ai_technology", "answers": answers})
    body = response.json()
    for competency_id, level in body["self_ratings"].items():
        assert competency_id in {c["competency_id"] for c in body["competency_scores"]}
        assert 0 <= level <= 5


def test_submit_rejects_an_unknown_item_id():
    response = client.post(
        "/learning/competency-quiz/submit",
        json={"topic_id": "statistical_foundations", "answers": [{"item_id": "not-real", "selected_index": 0}]},
    )
    assert response.status_code == 404


def test_submit_rejects_empty_answers():
    response = client.post(
        "/learning/competency-quiz/submit",
        json={"topic_id": "statistical_foundations", "answers": []},
    )
    assert response.status_code == 422
