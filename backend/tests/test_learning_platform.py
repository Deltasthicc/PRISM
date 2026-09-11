"""
Tests for the cross-domain skill-intelligence layer: curricula validation,
gap/pathway analysis, catalog recommendations, bounded content ingestion,
the deterministic quiz fallback, and the cross-domain room-unlock fix in
routes/game.py. Pure-logic pieces are tested directly (no server, no
network, no API key) the same way test_progression.py tests
_is_room_unlocked_for_player directly rather than through HTTP.
"""
import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon, Room
from models.guild import Guild  # noqa: F401
from models.player import Player
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from routes.game import _is_room_unlocked_for_player
from services.content_ingestion import (
    MAX_UPLOAD_BYTES,
    MIN_EXTRACTED_CHARS,
    ContentExtractionError,
    extract_text,
)
from services.curricula import CURRICULA, curriculum_for_topic, get_curriculum, public_curricula, validate_curricula
from services.learning_catalog import integration_status, recommend_courses
from services.learning_engine import analyse_competencies
from services.quiz_generator import generate_quiz


# ─── curricula.py ───

def test_curricula_pass_their_own_validation():
    # Re-running this must never raise -- curricula.py already calls it once
    # at import time, so a broken catalog would have failed collection.
    validate_curricula()


def test_public_curricula_exposes_all_four_domains():
    slugs = {entry["slug"] for entry in public_curricula()}
    assert slugs == {"dsa-fundamentals", "official-statistics", "public-policy", "digital-literacy"}


def test_competency_ids_are_globally_unique_across_curricula():
    all_ids = [c["id"] for curriculum in CURRICULA.values() for c in curriculum["competencies"]]
    assert len(all_ids) == len(set(all_ids))


def test_curriculum_for_topic_crosses_domains():
    slug, curriculum = curriculum_for_topic("os_sampling_design")
    assert slug == "official-statistics"
    assert curriculum["name"] == "Official Statistics & Data Governance"

    slug, curriculum = curriculum_for_topic("not_a_real_competency")
    assert slug is None
    assert curriculum is None


# ─── learning_engine.py ───

def test_analyse_competencies_blends_measured_and_self_score():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={"os_statistical_foundations": 4.0},
        measured_scores={"os_statistical_foundations": 2.0},
        experience_level="advanced",
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_statistical_foundations")
    # 65% measured + 35% self, per learning_engine.py's documented policy.
    assert row["observed_level"] == pytest.approx(2.0 * 0.65 + 4.0 * 0.35, abs=0.01)
    assert "65%" in row["evidence"]


def test_analyse_competencies_rejects_unknown_competency():
    with pytest.raises(ValueError, match="outside this curriculum"):
        analyse_competencies("official-statistics", {"not_a_real_competency": 3.0}, {}, "beginner")


def test_analyse_competencies_rejects_unknown_curriculum():
    with pytest.raises(ValueError, match="Unknown curriculum"):
        analyse_competencies("not-a-real-curriculum", {}, {}, "beginner")


def test_pathway_orders_prerequisites_before_dependents():
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    order = {step["competency_id"]: step["step"] for step in result["pathway"]}
    # os_sampling_design depends on os_data_collection which depends on
    # os_statistical_foundations -- every prerequisite must be scheduled
    # strictly before the competency that needs it.
    if "os_sampling_design" in order and "os_data_collection" in order:
        assert order["os_data_collection"] < order["os_sampling_design"]


# Before this, every analyse_competencies() call in the whole test suite
# (this file's own tests, the golden fixtures, behavioral-anchor tests) used
# "official-statistics" -- public-policy and digital-literacy had real
# competencies, real prerequisite graphs and real target_levels in
# services/curricula.py, but nothing had ever run the engine against them
# end to end, so a real regression specific to either curriculum had nothing
# to fail against.
@pytest.mark.parametrize(
    ("curriculum_slug", "self_ratings", "measured", "known_competency"),
    [
        ("public-policy", {"pa_governance_foundations": 3.0}, {"pa_governance_foundations": 4.0}, "pa_governance_foundations"),
        ("digital-literacy", {"dl_digital_foundations": 2.0}, {"dl_digital_foundations": 3.0}, "dl_digital_foundations"),
    ],
)
def test_analyse_competencies_blends_measured_and_self_score_for_other_curricula(
    curriculum_slug, self_ratings, measured, known_competency
):
    result = analyse_competencies(
        curriculum_slug, self_ratings, measured, experience_level="advanced"
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == known_competency)
    expected = measured[known_competency] * 0.65 + self_ratings[known_competency] * 0.35
    assert row["observed_level"] == pytest.approx(expected, abs=0.01)
    assert "65%" in row["evidence"]


def test_pathway_orders_prerequisites_before_dependents_for_public_policy():
    result = analyse_competencies("public-policy", {}, {}, "beginner")
    order = {step["competency_id"]: step["step"] for step in result["pathway"]}
    # pa_impact_evaluation depends on pa_monitoring_evaluation, which depends
    # on both pa_policy_design and pa_public_finance, which both depend on
    # pa_governance_foundations -- every link in that chain must hold.
    if "pa_impact_evaluation" in order and "pa_monitoring_evaluation" in order:
        assert order["pa_monitoring_evaluation"] < order["pa_impact_evaluation"]
    if "pa_monitoring_evaluation" in order and "pa_policy_design" in order:
        assert order["pa_policy_design"] < order["pa_monitoring_evaluation"]
    if "pa_policy_design" in order and "pa_governance_foundations" in order:
        assert order["pa_governance_foundations"] < order["pa_policy_design"]


def test_pathway_orders_prerequisites_before_dependents_for_digital_literacy():
    result = analyse_competencies("digital-literacy", {}, {}, "beginner")
    order = {step["competency_id"]: step["step"] for step in result["pathway"]}
    # dl_digital_public_infrastructure depends on both dl_government_cloud and
    # dl_data_privacy, and dl_data_privacy itself depends on dl_cyber_hygiene,
    # which depends on dl_digital_foundations -- a real multi-level chain.
    if "dl_digital_public_infrastructure" in order and "dl_data_privacy" in order:
        assert order["dl_data_privacy"] < order["dl_digital_public_infrastructure"]
    if "dl_data_privacy" in order and "dl_cyber_hygiene" in order:
        assert order["dl_cyber_hygiene"] < order["dl_data_privacy"]
    if "dl_cyber_hygiene" in order and "dl_digital_foundations" in order:
        assert order["dl_digital_foundations"] < order["dl_cyber_hygiene"]


def test_experience_level_caps_the_pathway_target_below_role_target():
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    # ML for Official Statistics has a role target of 5; a beginner's cap is 3.
    ml_row = next(r for r in result["competencies"] if r["competency_id"] == "os_ml")
    assert ml_row["role_target"] == 5
    assert ml_row["pathway_target"] <= 3


# ─── learning_catalog.py ───

def test_recommend_courses_includes_internal_practice_and_both_providers():
    gaps = [{"competency_id": "os_data_quality", "label": "Data Quality", "gap": 2.0}]
    courses = recommend_courses(gaps)
    provider_types = {course["provider_type"] for course in courses}
    assert provider_types == {"internal-practice", "igot", "nssta"}
    assert all(course["course_id"].split("::")[1] == "os_data_quality" for course in courses)


def test_integration_status_reports_fallback_without_configured_env(monkeypatch):
    monkeypatch.delenv("IGOT_API_BASE_URL", raising=False)
    monkeypatch.delenv("NSSTA_API_BASE_URL", raising=False)
    # Re-import to pick up the cleared env vars (module-level constants read
    # os.getenv once at import time).
    import importlib
    import services.learning_catalog as catalog_module
    importlib.reload(catalog_module)
    status = catalog_module.integration_status()
    assert status["igot"]["mode"] == "CATALOGUE"
    assert status["nssta"]["mode"] == "CATALOGUE"
    importlib.reload(catalog_module)  # restore normal state for any later test


def test_integration_status_never_reports_live_from_env_var_presence_alone(monkeypatch):
    """docs/contracts/provider-adapter.md's own rule: an environment variable
    alone must never imply LIVE, only a successful authenticated capability
    check does. Mocks health_check() to fail (no real network dependency in
    this test) with IGOT_API_BASE_URL still set, proving the reported mode
    is decided by the check's outcome, not by the variable being present."""
    import services.learning_catalog as catalog_module
    from integrations.provider import ProviderResult

    monkeypatch.setenv("IGOT_API_BASE_URL", "https://example.invalid")
    monkeypatch.setattr(
        catalog_module.LiveHTTPProviderAdapter,
        "health_check",
        lambda self: ProviderResult("ERROR", {"error": "connection refused"}),
    )
    status = catalog_module.integration_status()
    assert status["igot"]["mode"] == "CATALOGUE"
    assert "health check" in status["igot"]["detail"].lower()


def test_integration_status_reports_live_when_health_check_succeeds(monkeypatch):
    """The other half of the same rule: a real, successful health check
    (not just an env var) is what earns LIVE. Mocks the adapter's
    health_check() rather than depending on real network access in a test."""
    import services.learning_catalog as catalog_module
    from integrations.provider import ProviderResult

    monkeypatch.setenv("IGOT_API_BASE_URL", "https://example.invalid")
    monkeypatch.setattr(
        catalog_module.LiveHTTPProviderAdapter,
        "health_check",
        lambda self: ProviderResult("LIVE", {"capabilities": ["search_catalogue"]}),
    )
    status = catalog_module.integration_status()
    assert status["igot"]["mode"] == "LIVE"
    assert "live" in status["igot"]["detail"].lower()


# ─── content_ingestion.py ───

def test_extract_text_reads_plain_txt():
    text = ("Official statistics require careful sampling design. " * 10).encode("utf-8")
    result = extract_text("notes.txt", text)
    assert "sampling design" in result


def test_extract_text_rejects_oversized_upload():
    oversized = b"x" * (MAX_UPLOAD_BYTES + 1)
    with pytest.raises(ContentExtractionError, match="MB upload limit"):
        extract_text("notes.txt", oversized)


def test_extract_text_rejects_unsupported_extension():
    with pytest.raises(ContentExtractionError, match="Unsupported file type"):
        extract_text("notes.exe", b"whatever")


def test_extract_text_rejects_too_short_material():
    with pytest.raises(ValueError, match="too short"):
        extract_text("notes.txt", b"short")


def test_min_extracted_chars_is_meaningfully_nonzero():
    # Guards against someone accidentally setting this to 0 and silently
    # disabling the "not enough source material" check above.
    assert MIN_EXTRACTED_CHARS >= 100


# ─── quiz_generator.py ───

def test_generate_quiz_falls_back_deterministically_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    source = (
        "Sampling design determines which frame is used, how weights are computed, "
        "and how non-response is handled. Data quality validation checks completeness "
        "and consistency before a statistical product is disseminated. Metadata "
        "documents each variable so downstream users can interpret it correctly."
    )
    questions, mode = asyncio.run(generate_quiz(source, count=3, difficulty="mixed", language="English"))
    assert mode == "extractive-fallback"
    assert len(questions) == 3
    for question in questions:
        assert len(question["options"]) == 4
        assert len({option.lower() for option in question["options"]}) == 4
        assert 0 <= question["answer_index"] <= 3
        assert question["source_excerpt"] in source
        assert question["difficulty"] in {"easy", "medium", "hard"}


# ─── deterministic answer-index derivation (never trust a bare stated index) ───

def _make_llm_item(**overrides):
    item = {
        "question": "What does sampling design determine?",
        "options": ["The frame and weights", "The font used", "The office address", "The logo"],
        "option_truth": [True, False, False, False],
        "explanation": "The source states sampling design determines the frame and weights.",
        "source_excerpt": "Sampling design determines which frame is used",
        "competency": "Sampling",
        "bloom_level": "understand",
        "difficulty": "medium",
    }
    item.update(overrides)
    return item


def test_answer_index_is_derived_from_option_truth_not_a_stated_index():
    from services.quiz_generator import _derive_answer_index

    # A separately-stated answer_index is not even read anymore -- only
    # option_truth decides. This is the exact mismatch class this feature
    # exists to make impossible: an LLM's explanation and its answer_index
    # field drifting apart with nothing to catch it.
    item = _make_llm_item(option_truth=[False, False, True, False], answer_index=0)
    assert _derive_answer_index(item) == 2


def test_negation_question_derives_the_one_false_option():
    from services.quiz_generator import _derive_answer_index

    item = _make_llm_item(
        is_negation=True,
        option_truth=[True, True, False, True],
    )
    assert _derive_answer_index(item) == 2


def test_ambiguous_option_truth_is_rejected_not_guessed():
    from services.quiz_generator import _derive_answer_index

    # Two options marked true (or zero) for a normal question is a
    # structural failure, not a 50/50 guess -- reject the item outright.
    assert _derive_answer_index(_make_llm_item(option_truth=[True, True, False, False])) is None
    assert _derive_answer_index(_make_llm_item(option_truth=[False, False, False, False])) is None


def test_validate_questions_rejects_items_with_missing_option_truth():
    from services.quiz_generator import _validate_questions

    source = "Sampling design determines which frame is used, how weights are computed."
    legacy_item = {
        "question": "What does sampling design determine?",
        "options": ["The frame and weights", "The font used", "The office address", "The logo"],
        "answer_index": 0,  # old-style field, no longer trusted or read
        "source_excerpt": "Sampling design determines which frame is used",
    }
    with pytest.raises(ValueError):
        _validate_questions([legacy_item], source, requested_count=1)


def test_validate_questions_accepts_a_well_formed_option_truth_item():
    from services.quiz_generator import _validate_questions

    source = "Sampling design determines which frame is used, how weights are computed."
    item = _make_llm_item(source_excerpt="Sampling design determines which frame is used")
    validated = _validate_questions([item], source, requested_count=1)
    assert len(validated) == 1
    assert validated[0]["answer_index"] == 0


def test_estimate_difficulty_scales_with_term_and_sentence_length():
    from services.quiz_generator import _estimate_difficulty

    assert _estimate_difficulty("Short sentence.", "data") == "easy"
    long_sentence = (
        "This is a considerably longer sentence about interoperability, deliberately "
        "padded out well past the two-hundred-and-twenty character threshold so that "
        "both the carrier-sentence-length signal and the long-answer-term signal "
        "clearly stack together into the hard bucket for this heuristic."
    )
    assert len(long_sentence) >= 220
    assert _estimate_difficulty(long_sentence, "interoperability") == "hard"


# ─── routes/game.py cross-domain room unlock ───

def test_room_unlock_falls_back_to_curricula_for_non_dsa_topics():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()

    dungeon = Dungeon(name="Official Statistics & Data Governance", domain="Official Statistics",
                       curriculum_slug="official-statistics")
    player = Player(username="stats_officer")
    db.add_all([dungeon, player])
    db.flush()

    foundations = Room(dungeon_id=dungeon.dungeon_id, topic="os_statistical_foundations",
                        order_index=0, is_unlocked=True, enemy_count=400)
    collection = Room(dungeon_id=dungeon.dungeon_id, topic="os_data_collection",
                       order_index=1, is_unlocked=False, enemy_count=400)
    db.add_all([foundations, collection])
    db.commit()

    # No evidence yet -- os_data_collection requires os_statistical_foundations,
    # which is not yet proven, so it must stay locked.
    assert _is_room_unlocked_for_player(db, player.player_id, collection, dungeon.dungeon_id) is False

    db.add(AccuracyHistory(
        player_id=player.player_id, topic="os_statistical_foundations",
        attempts=5, correct=4, recent_accuracy=0.8, mastered=True,
    ))
    db.commit()

    assert _is_room_unlocked_for_player(db, player.player_id, collection, dungeon.dungeon_id) is True
