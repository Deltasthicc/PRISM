"""Course catalogue and keyword-matching tests.

The catalogue is reference data, so most of what matters is that it cannot
quietly start lying: no fabricated provider record, no record that claims to be
a live sync, no recommendation that cannot say why it appeared, and no
competency citing a source we do not carry.
"""
from services.course_catalogue import (
    MIN_KEYWORD_TERMS,
    all_courses,
    catalogue_status,
    recommend_for_competency,
    search,
)
from services.curricula import CURRICULA, SOURCES

PROVIDER_TYPES = {"igot", "nssta", "institute"}


def _competency_index():
    return {
        competency["id"]: competency
        for curriculum in CURRICULA.values()
        for competency in curriculum["competencies"]
    }


def test_catalogue_loads_and_reports_its_version():
    status = catalogue_status()
    assert status["status"] == "CATALOGUE"
    assert status["total_courses"] == len(all_courses())
    assert status["catalogue_version"]
    assert status["retrieved"]


def test_every_course_record_is_complete():
    for course in all_courses():
        assert course["course_id"]
        assert course["title"]
        assert course["provider"]
        assert course["provider_type"] in PROVIDER_TYPES
        assert course["url"].startswith("https://")
        assert course["source_id"] in SOURCES, (
            f"{course['course_id']} cites {course['source_id']}, which is not in the registry"
        )
        assert course["competency_ids"], f"{course['course_id']} maps to no competency"


def test_course_ids_are_unique():
    ids = [course["course_id"] for course in all_courses()]
    assert len(ids) == len(set(ids))


def test_no_course_maps_to_an_unknown_competency():
    known = set(_competency_index())
    for course in all_courses():
        unknown = set(course["competency_ids"]) - known
        assert not unknown, f"{course['course_id']} maps to unknown: {sorted(unknown)}"


def test_every_course_is_catalogue_never_live():
    """Architectural invariant 6 and 7: a catalogue record must never present
    itself as a live integration. Nothing here has enrolment, completion or
    writeback, so nothing may be labelled LIVE."""
    for course in all_courses():
        assert course["status"] == "CATALOGUE", (
            f"{course['course_id']} claims status {course['status']!r}"
        )


def test_competency_mapping_is_always_marked_provisional():
    """iGOT says its courses are KCM-mapped but does not publish the mapping,
    so ours is inference. Invariant 11 forbids presenting it as the official
    one."""
    for course in all_courses():
        assert course["mapping_assurance"] == "PROVISIONAL"


def test_only_igot_records_carry_a_provider_record_id():
    """A fabricated provider ID is exactly what invariant 6 rules out. NSSTA
    programmes are PDF table rows and have no ID; theirs must stay null rather
    than being given a plausible-looking one."""
    for course in all_courses():
        if course["provider_type"] == "igot":
            assert course["provider_record_id"], f"{course['course_id']} lost its iGOT do_ id"
            assert course["provider_record_id"].startswith("do_")
        else:
            assert course["provider_record_id"] is None, (
                f"{course['course_id']} carries a provider record ID it cannot have"
            )


def test_non_igot_records_locate_themselves_in_their_source():
    """An NSSTA record's URL is a whole 29-page PDF, so without a locator a
    reader cannot check the claim. Same page/section-locator idea SourceVersion
    uses."""
    for course in all_courses():
        if course["provider_type"] == "nssta":
            assert course["locator"], f"{course['course_id']} has no locator into SRC-01"


def test_every_recommendation_explains_itself():
    index = _competency_index()
    for competency_id, competency in index.items():
        for hit in recommend_for_competency(
            competency_id, competency["label"], competency["description"]
        ):
            assert hit["match_reason"], f"{hit['course_id']} appeared with no reason"
            assert hit["match_type"] in {"mapped", "keyword"}
            if hit["match_type"] == "keyword":
                assert hit["matched_terms"], "a keyword hit must name the words it matched"


def test_curated_mappings_outrank_keyword_hits():
    index = _competency_index()
    for competency_id, competency in index.items():
        types = [
            hit["match_type"]
            for hit in recommend_for_competency(
                competency_id, competency["label"], competency["description"]
            )
        ]
        if "mapped" in types and "keyword" in types:
            assert types.index("keyword") > max(
                position for position, kind in enumerate(types) if kind == "mapped"
            ), f"{competency_id} ranked a keyword guess above a curated mapping"


def test_every_non_dsa_competency_has_at_least_one_course():
    index = _competency_index()
    uncovered = [
        competency["id"]
        for slug, curriculum in CURRICULA.items()
        if slug != "dsa-fundamentals"
        for competency in curriculum["competencies"]
        if not recommend_for_competency(competency["id"])
    ]
    assert not uncovered, f"non-DSA competencies with no course: {uncovered}"


def test_dsa_competencies_return_nothing_rather_than_a_loose_match():
    """DSA has no government-catalogued course. Returning an unrelated MoSPI
    programme to avoid an empty list would be worse than the empty list --
    internal practice is the honest fallback."""
    for competency in CURRICULA["dsa-fundamentals"]["competencies"]:
        assert recommend_for_competency(
            competency["id"], competency["label"], competency["description"]
        ) == []


def test_a_single_shared_word_is_not_a_match():
    """"Design Thinking" shares only `design` with "Sampling Design" and is not
    a sampling course."""
    titles = [hit["title"] for hit in search("design")]
    assert titles == [], "a one-term query matched something; MIN_KEYWORD_TERMS is not holding"
    assert MIN_KEYWORD_TERMS >= 2


def test_search_finds_the_obvious_thing():
    titles = [hit["title"] for hit in search("artificial intelligence machine learning")]
    assert any("Artificial Intelligence" in title for title in titles)


def test_search_is_deterministic():
    assert search("cyber security cloud") == search("cyber security cloud")


def test_search_on_stopwords_alone_returns_nothing():
    """Every term in this query is a stopword, so there is no signal left. An
    empty result is correct; returning the whole catalogue would not be."""
    assert search("the data and management of statistics") == []


def test_recommend_without_text_returns_only_curated_mappings():
    hits = recommend_for_competency("os_sampling_design")
    assert hits
    assert {hit["match_type"] for hit in hits} == {"mapped"}


def test_all_courses_hides_internal_token_cache():
    for course in all_courses():
        assert not any(key.startswith("_") for key in course)


def test_limit_is_respected():
    index = _competency_index()
    for competency_id, competency in index.items():
        hits = recommend_for_competency(
            competency_id, competency["label"], competency["description"], limit=2
        )
        assert len(hits) <= 2
