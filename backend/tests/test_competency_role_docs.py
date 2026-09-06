"""Role catalogue, document corpus and the role -> docs -> MCQ pipeline.

Network is never required: the one end-to-end quiz test runs against a cached
document and skips cleanly if the cache is cold, so CI stays deterministic.
Populate the cache with:

    python -m scripts.role_demo sso_price --quiz
"""
import asyncio

import pytest

from services.competency_docs import (
    DocumentUnavailable,
    _front_matter_skip,
    _is_boilerplate,
    all_documents,
    corpus_status,
    documents_for_competency,
    documents_for_role,
    extract_document_text,
    get_document,
    quiz_from_document,
    role_learning_plan,
    uncovered_competencies,
)
from services.curricula import CURRICULA, SOURCES
from services.role_catalogue import (
    CATEGORY_LABELS,
    COMPETENCY_CATEGORY,
    ROLES,
    categories_for_role,
    get_role,
    list_roles,
)

CACHED_DOC = "cpi_imputation"

KNOWN_COMPETENCIES = {
    competency["id"]
    for curriculum in CURRICULA.values()
    for competency in curriculum["competencies"]
}


# --------------------------------------------------------------------------
# Role catalogue
# --------------------------------------------------------------------------


def test_roles_exist_and_are_complete():
    roles = list_roles()
    assert len(roles) >= 5
    for role in roles:
        assert role["role_id"]
        assert role["designation"]
        assert role["job_role"]
        assert role["department"]
        assert role["cadre"]
        assert role["focus_categories"]


def test_every_role_target_is_a_real_competency_at_a_valid_level():
    for role_id, role in ROLES.items():
        assert role["competency_targets"], f"{role_id} targets nothing"
        for competency_id, level in role["competency_targets"].items():
            assert competency_id in KNOWN_COMPETENCIES, f"{role_id} -> unknown {competency_id}"
            assert 1 <= level <= 5


def test_every_role_target_is_provisional_and_unapproved():
    """Role targets are team-authored. No official source publishes role ->
    competency -> level, so claiming approval would be fabrication."""
    for role_id, role in ROLES.items():
        assert role["assurance"] == "PROVISIONAL", f"{role_id} claims non-provisional assurance"
        assert role["approved_by"] is None, f"{role_id} claims an approver"


def test_four_problem_statement_categories_are_present():
    """docs/SIH26101_PROBLEM_STATEMENT.md names exactly these four."""
    assert set(CATEGORY_LABELS.values()) == {
        "Statistical",
        "Technical",
        "Digital Governance",
        "Behavioural and Managerial",
    }


def test_every_categorised_competency_exists():
    assert set(COMPETENCY_CATEGORY) <= KNOWN_COMPETENCIES


def test_categories_for_role_groups_every_target():
    for role_id, role in ROLES.items():
        grouped = categories_for_role(role_id)
        flattened = {c for ids in grouped.values() for c in ids}
        assert flattened == set(role["competency_targets"]), f"{role_id} lost a competency"


def test_unknown_role_returns_none_not_a_guess():
    assert get_role("chief_wizard") is None
    assert categories_for_role("chief_wizard") == {}
    assert documents_for_role("chief_wizard") == []


# --------------------------------------------------------------------------
# Document corpus
# --------------------------------------------------------------------------


def test_corpus_loads_and_covers_all_four_categories():
    status = corpus_status()
    assert status["total_documents"] == len(all_documents())
    assert set(status["documents_by_category"]) == set(CATEGORY_LABELS.values())


def test_every_document_record_is_complete_and_verified():
    for document in all_documents():
        assert document["doc_id"]
        assert document["title"]
        assert document["publisher"]
        assert document["url"].startswith("https://")
        assert document["source_id"]
        assert document["category"] in CATEGORY_LABELS
        assert document["competency_ids"]
        assert len(document["sha256"]) == 64, f"{document['doc_id']} has no usable hash"
        assert document["pages"] > 0
        assert document["bytes"] > 0
        assert document["link_status"] == "verified-file"
        assert document["verified_on"]


def test_documents_map_only_to_real_competencies():
    for document in all_documents():
        unknown = set(document["competency_ids"]) - KNOWN_COMPETENCIES
        assert not unknown, f"{document['doc_id']} maps to unknown: {sorted(unknown)}"


def test_document_ids_and_hashes_are_unique():
    documents = all_documents()
    assert len({d["doc_id"] for d in documents}) == len(documents)
    assert len({d["sha256"] for d in documents}) == len(documents)


def test_new_document_sources_are_registered_or_clearly_new():
    """A doc citing SRC-NN that curricula.SOURCES does not carry is fine while
    the corpus grows faster than the registry, but the ID must at least follow
    the convention so the two can be reconciled later."""
    for document in all_documents():
        assert document["source_id"].startswith("SRC-"), document["doc_id"]


def test_documents_for_competency_is_consistent_with_the_corpus():
    for document in all_documents():
        for competency_id in document["competency_ids"]:
            matches = {d["doc_id"] for d in documents_for_competency(competency_id)}
            assert document["doc_id"] in matches


def test_documents_for_role_explains_every_match():
    for role_id, role in ROLES.items():
        targets = set(role["competency_targets"])
        for document in documents_for_role(role_id):
            assert document["matched_competencies"], f"{document['doc_id']} matched nothing"
            assert set(document["matched_competencies"]) <= targets


def test_documents_for_role_is_ranked_most_relevant_first():
    for role_id in ROLES:
        counts = [len(d["matched_competencies"]) for d in documents_for_role(role_id)]
        assert counts == sorted(counts, reverse=True)


# --------------------------------------------------------------------------
# Learning plan
# --------------------------------------------------------------------------


def test_learning_plan_covers_every_category_the_role_targets():
    for role_id in ROLES:
        plan = role_learning_plan(role_id)
        assert plan["categories"], f"{role_id} produced an empty plan"
        planned = {
            competency["competency_id"]
            for category in plan["categories"]
            for competency in category["competencies"]
        }
        assert planned == set(ROLES[role_id]["competency_targets"])


def test_learning_plan_reports_its_own_coverage_honestly():
    for role_id in ROLES:
        plan = role_learning_plan(role_id)
        counted = sum(
            1
            for category in plan["categories"]
            for competency in category["competencies"]
            if competency["document_count"] > 0
        )
        assert plan["competencies_with_documents"] == counted
        assert plan["competencies_with_documents"] <= plan["total_competencies"]


def test_learning_plan_never_claims_approval():
    for role_id in ROLES:
        plan = role_learning_plan(role_id)
        assert plan["assurance"] == "PROVISIONAL"
        assert plan["approved_by"] is None
        assert "PROVISIONAL" in plan["note"]


def test_unknown_role_plan_raises_rather_than_returning_empty():
    with pytest.raises(DocumentUnavailable, match="Unknown role"):
        role_learning_plan("chief_wizard")


def test_uncovered_competencies_are_surfaced_not_hidden():
    """Gaps are the input to the next round of corpus building, so they must
    be reportable rather than silently absent from plans."""
    gaps = uncovered_competencies()
    covered = {c for d in all_documents() for c in d["competency_ids"]}
    for role_id, missing in gaps.items():
        for competency_id in missing:
            assert competency_id in ROLES[role_id]["competency_targets"]
            assert competency_id not in covered


# --------------------------------------------------------------------------
# Text extraction quality
# --------------------------------------------------------------------------


def test_front_matter_skip_never_starves_a_short_document():
    assert _front_matter_skip(3) == 0
    assert _front_matter_skip(9) <= 6
    for pages in range(1, 200):
        assert _front_matter_skip(pages) < max(1, pages)


def test_boilerplate_filter_drops_page_furniture():
    assert _is_boilerplate("MINISTRY OF STATISTICS AND PROGRAMME IMPLEMENTATION")
    assert _is_boilerplate("Page 12")
    assert _is_boilerplate("2.1 .......................... 14")
    assert _is_boilerplate("   ")


def test_boilerplate_filter_keeps_real_prose():
    assert not _is_boilerplate(
        "The imputed index for a sub-group is derived from the last observed index "
        "multiplied by the ratio of current to previous prices."
    )


def test_unknown_document_raises():
    assert get_document("not_a_real_doc") is None
    with pytest.raises(DocumentUnavailable, match="Unknown document"):
        extract_document_text("not_a_real_doc", allow_network=False)


def test_offline_mode_refuses_rather_than_silently_downloading():
    uncached = next(
        (d["doc_id"] for d in all_documents() if d["doc_id"] != CACHED_DOC), None
    )
    assert uncached
    from services.competency_docs import _cache_path

    if _cache_path(uncached).exists():
        pytest.skip("every document happens to be cached")
    with pytest.raises(DocumentUnavailable, match="not cached"):
        extract_document_text(uncached, allow_network=False)


# --------------------------------------------------------------------------
# End to end: role -> document -> cited MCQs
# --------------------------------------------------------------------------


def _require_cached():
    from services.competency_docs import _cache_path

    if not _cache_path(CACHED_DOC).exists():
        pytest.skip(
            f"{CACHED_DOC} not cached; run `python -m scripts.role_demo sso_price --quiz` first"
        )


def test_extraction_reports_a_checkable_locator():
    _require_cached()
    extracted = extract_document_text(CACHED_DOC, allow_network=False)
    assert extracted["character_count"] >= 1200
    assert extracted["locator"].startswith("pages ")
    assert extracted["integrity"] in {"cached", "verified"}
    assert extracted["url"].startswith("https://")


def test_end_to_end_role_to_cited_mcqs():
    _require_cached()
    quiz = asyncio.run(quiz_from_document(CACHED_DOC, count=3, allow_network=False))

    assert quiz["question_count"] == 3
    assert quiz["status"] == "DRAFT", "generated items must stay drafts until reviewed"
    assert quiz["url"].startswith("https://")
    assert quiz["locator"]

    source = extract_document_text(CACHED_DOC, allow_network=False)["text"]
    compact = " ".join(source.split()).lower()
    for question in quiz["questions"]:
        assert question["question"]
        assert len(question["options"]) == 4
        assert len({o.strip().lower() for o in question["options"]}) == 4
        assert 0 <= question["answer_index"] <= 3
        excerpt = " ".join(question["source_excerpt"].split()).lower()
        assert excerpt in compact, "every question must quote the source document"


def test_generated_quiz_is_never_labelled_live_or_approved():
    _require_cached()
    quiz = asyncio.run(quiz_from_document(CACHED_DOC, count=2, allow_network=False))
    assert quiz["generation_mode"] in {"gemini-grounded", "extractive-fallback"}
    assert "review" in quiz["review_note"].lower()
