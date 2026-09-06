"""Hand-transcribed/hand-authored MCQs layered on top of the document corpus.

Two different reasons a doc_id ends up here, both covered below:
1. The two scanned UPSC page-image PDFs, which
   services.competency_docs.extract_document_text() cannot read automatically
   at all (no embedded text layer) -- these are verbatim transcriptions.
2. A handful of real, text-extractable corpus documents (dpdp_act_2023,
   niti_ai_strategy, cpi_manual_2010) chosen for the live competency-quiz
   route's reliability: quiz_from_document() depends on a live network fetch
   per request, which is a real risk for a demo; these hand-authored items
   guarantee every quiz topic has fast, offline-capable, still genuinely
   sourced content regardless of network conditions.

Network is never required -- these are pure in-repo data, unlike
test_competency_role_docs.py's one live-fetch test.
"""
import pytest

from services.competency_docs import DocumentUnavailable, all_documents, get_document
from services.curricula import CURRICULA
from services.hand_authored_questions import (
    hand_authored_doc_ids,
    quiz_from_hand_authored,
    questions_for_competency,
    questions_for_doc,
)

KNOWN_COMPETENCIES = {
    competency["id"]
    for curriculum in CURRICULA.values()
    for competency in curriculum["competencies"]
}

UPSC_DOC_IDS = {"upsc_csm26_statistics_p1", "upsc_csm26_statistics_p2"}
RELIABILITY_DOC_IDS = {"dpdp_act_2023", "niti_ai_strategy", "cpi_manual_2010"}
ALL_HAND_AUTHORED_DOC_IDS = UPSC_DOC_IDS | RELIABILITY_DOC_IDS


def test_both_upsc_documents_are_registered_in_the_corpus():
    corpus_ids = {doc["doc_id"] for doc in all_documents()}
    assert UPSC_DOC_IDS <= corpus_ids


def test_upsc_documents_carry_an_extraction_note_explaining_the_scanned_gap():
    for doc_id in UPSC_DOC_IDS:
        record = get_document(doc_id)
        assert record is not None
        assert "scanned" in record["extraction_note"].lower()
        assert "hand_authored_questions" in record["extraction_note"]


def test_hand_authored_doc_ids_covers_scanned_docs_and_reliability_docs():
    # Confirms the hand-authored path exists precisely for the documents that
    # need it (scanned) or that the quiz route deliberately pins for
    # reliability -- not some arbitrary, unbounded subset.
    assert hand_authored_doc_ids() == ALL_HAND_AUTHORED_DOC_IDS


@pytest.mark.parametrize("doc_id", sorted(UPSC_DOC_IDS))
def test_every_item_references_a_real_corpus_document(doc_id):
    items = questions_for_doc(doc_id)
    assert len(items) > 0
    for item in items:
        assert item["doc_id"] == doc_id


def test_every_item_has_a_valid_shape():
    for doc_id in ALL_HAND_AUTHORED_DOC_IDS:
        for item in questions_for_doc(doc_id):
            assert len(item["options"]) == 4
            assert len(set(item["options"])) == 4, f"{item['item_id']}: duplicate options"
            assert 0 <= item["answer_index"] < 4
            assert item["difficulty"] in {"easy", "medium", "hard"}
            assert item["competency_id"] in KNOWN_COMPETENCIES, (
                f"{item['item_id']}: competency_id {item['competency_id']!r} is not in services.curricula.CURRICULA"
            )
            assert len(item["explanation"]) > 20
            assert len(item["source_excerpt"]) > 10


def test_answer_index_is_not_degenerate_across_the_whole_bank():
    # Regression guard: every item was originally hand-written with the
    # correct option listed first (answer_index == 0 for all 21 items before
    # a deterministic per-item shuffle fixed it), which would have let an
    # "always pick the first option" strategy score 100% on any of these
    # quizzes -- a real flaw a competency assessment cannot have. This does
    # not require a perfectly uniform distribution, just that no single
    # index accounts for every item.
    all_items = [item for doc_id in ALL_HAND_AUTHORED_DOC_IDS for item in questions_for_doc(doc_id)]
    indexes = {item["answer_index"] for item in all_items}
    assert len(indexes) > 1, "every item has the same answer_index -- the bank is guessable"


def test_no_duplicate_item_ids():
    ids = [
        item["item_id"]
        for doc_id in ALL_HAND_AUTHORED_DOC_IDS
        for item in questions_for_doc(doc_id)
    ]
    assert len(ids) == len(set(ids))


def test_no_duplicate_question_text_across_the_bank():
    texts = [
        " ".join(item["question"].lower().split())
        for doc_id in ALL_HAND_AUTHORED_DOC_IDS
        for item in questions_for_doc(doc_id)
    ]
    assert len(texts) == len(set(texts))


def test_questions_for_competency_matches_manual_count():
    stats_foundations = questions_for_competency("os_statistical_foundations")
    assert len(stats_foundations) >= 8
    assert all(item["competency_id"] == "os_statistical_foundations" for item in stats_foundations)


def test_quiz_from_hand_authored_returns_the_same_shape_as_quiz_from_document():
    quiz = quiz_from_hand_authored("upsc_csm26_statistics_p1")
    assert quiz["generation_mode"] == "hand-transcribed"
    assert quiz["integrity"] == "verified"
    assert quiz["status"] == "DRAFT"
    assert quiz["doc_id"] == "upsc_csm26_statistics_p1"
    assert quiz["question_count"] == len(quiz["questions"])
    for question in quiz["questions"]:
        assert set(question) == {
            "question", "options", "answer_index", "explanation",
            "source_excerpt", "competency", "bloom_level",
        }


def test_quiz_from_hand_authored_count_limits_the_pool():
    quiz = quiz_from_hand_authored("upsc_csm26_statistics_p1", count=2)
    assert quiz["question_count"] == 2


def test_quiz_from_hand_authored_difficulty_filters_the_pool():
    quiz = quiz_from_hand_authored("upsc_csm26_statistics_p1", difficulty="hard")
    assert quiz["question_count"] > 0
    assert all(
        item["difficulty"] == "hard"
        for item in questions_for_doc("upsc_csm26_statistics_p1")
        if item["question"] in {q["question"] for q in quiz["questions"]}
    )


def test_quiz_from_hand_authored_rejects_unknown_doc_id():
    with pytest.raises(DocumentUnavailable):
        quiz_from_hand_authored("not-a-real-doc-id")


def test_quiz_from_hand_authored_rejects_a_known_doc_with_no_hand_authored_items():
    # sif_guideline is real (in the corpus) but has no hand-authored items --
    # must fail closed, not silently return an empty quiz.
    with pytest.raises(DocumentUnavailable):
        quiz_from_hand_authored("sif_guideline")
