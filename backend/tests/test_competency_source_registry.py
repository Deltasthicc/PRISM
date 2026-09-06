"""Lane 3 sourced-taxonomy tests.

docs/internal/SIH26101_TEAM_ORCHESTRATION.md section 2 makes "sourced taxonomy" a Lane 3
must-deliver. These pin the *shape and honesty* of the citations, not their
content -- a test cannot verify that a government PDF says what we claim, so
what it can do is refuse a citation that is dangling, undated, mislabelled, or
dressed up as validation.
"""
import copy

import pytest

from services.curricula import (
    COMPETENCY_SOURCES,
    CURRICULA,
    DIRECT,
    INDIRECT,
    PROVISIONAL,
    RETRIEVED_ON,
    SOURCES,
    SOURCE_REGISTRY_VERSION,
    source_record,
    source_registry,
    stamp_competency_provenance,
    validate_curricula,
)

# Every status a source may carry, from the fixed documented vocabulary
# (CODEX.md architectural invariants). LIVE is deliberately absent: nothing in
# this registry is a live provider sync, and a source that claimed to be one
# would be the fabricated-integration failure the truth boundary forbids.
ALLOWED_SOURCE_STATUS = {"OFFICIAL", "CATALOGUE"}

# Government bodies that do not publish on a `.gov.in` domain. Kept as a named
# allowlist rather than loosening the domain check, so adding one is a
# deliberate, reviewable act: C-DAC is a scientific society under MeitY and
# publishes on `cdac.in`. Anything else must justify itself here first.
NON_GOV_IN_GOVERNMENT_HOSTS = {"www.cdac.in", "cdac.in"}


def _all_competencies():
    for slug, curriculum in CURRICULA.items():
        for competency in curriculum["competencies"]:
            yield slug, competency


def test_every_source_is_government_published_and_dated():
    for source_id, entry in SOURCES.items():
        assert source_id.startswith("SRC-"), f"{source_id} does not follow the SRC-NN convention"
        assert entry["title"], f"{source_id} has no title"
        assert entry["publisher"], f"{source_id} has no publisher"
        assert entry["url"].startswith("https://"), f"{source_id} is not an https URL"
        assert entry["status"] in ALLOWED_SOURCE_STATUS, (
            f"{source_id} carries status {entry['status']!r}, which is outside the documented "
            f"vocabulary {sorted(ALLOWED_SOURCE_STATUS)}"
        )


def test_every_source_is_on_a_government_domain():
    """A source register whose credibility claim is "government-published"
    has to actually be government-published. `.gov.in` is the check that
    stops a plausible-looking third-party summary drifting into the registry.
    """
    for source_id, entry in SOURCES.items():
        host = entry["url"].split("/")[2]
        assert host.endswith(".gov.in") or host in NON_GOV_IN_GOVERNMENT_HOSTS, (
            f"{source_id} points at {host}, which is neither a .gov.in domain nor a listed "
            "government body publishing elsewhere"
        )


def test_registry_reports_its_version_and_retrieval_date():
    registry = source_registry()
    assert registry["registry_version"] == SOURCE_REGISTRY_VERSION
    assert registry["retrieved"] == RETRIEVED_ON
    assert set(registry["sources"]) == set(SOURCES)
    for source_id, record in registry["sources"].items():
        assert record["source_id"] == source_id
        assert record["retrieved"] == RETRIEVED_ON


def test_source_registry_hands_out_copies():
    """A consumer that mutates what it is given must not corrupt the registry
    for every later caller -- the same defensive-copy rule get_curriculum()
    already follows."""
    first = source_registry()
    first["sources"]["SRC-01"]["publisher"] = "tampered"
    assert source_registry()["sources"]["SRC-01"]["publisher"] != "tampered"

    record = source_record("SRC-01")
    record["title"] = "tampered"
    assert source_record("SRC-01")["title"] != "tampered"


def test_source_record_returns_none_for_an_unknown_id():
    assert source_record("SRC-99") is None


def test_every_cited_competency_carries_a_resolvable_record():
    for slug, competency in _all_competencies():
        if competency["source"] == "internal-prototype":
            continue
        record = competency["source_record"]
        assert record is not None, f"{slug}:{competency['id']} cites a source but carries no record"
        assert record["source_id"] == competency["source"]
        assert record["url"].startswith("https://")
        assert competency["source_detail"], (
            f"{slug}:{competency['id']} cites {competency['source']} without saying what applies"
        )
        assert competency["source_strength"] in (DIRECT, INDIRECT)


def test_uncited_competencies_record_an_explicit_absence():
    """DSA is an engineering sample, not the pitch centre
    (SIH26101_MASTER_CHECKLIST.md section 3.3). Its competencies must read as
    "we claim no government source", never as a half-filled record that a
    reader could mistake for a pending lookup."""
    for _slug, competency in _all_competencies():
        if competency["source"] != "internal-prototype":
            continue
        assert competency["source_record"] is None
        assert competency["source_detail"] == ""
        assert competency["source_strength"] == ""


def test_no_dsa_competency_claims_a_government_source():
    for competency in CURRICULA["dsa-fundamentals"]["competencies"]:
        assert competency["source"] == "internal-prototype", (
            f"{competency['id']} claims source {competency['source']!r}; the DSA curriculum has "
            "no government backing and must not borrow one"
        )


def test_every_non_dsa_competency_is_cited():
    """The three government-facing curricula are the pitch. A competency there
    with no citation is a gap that must be visible, so this fails rather than
    letting an uncited one slip in unnoticed."""
    uncited = [
        f"{slug}:{competency['id']}"
        for slug, competency in _all_competencies()
        if slug != "dsa-fundamentals" and competency["source"] == "internal-prototype"
    ]
    assert not uncited, f"uncited competencies outside DSA: {', '.join(uncited)}"


def test_a_citation_never_upgrades_authoring_status():
    """The central honesty rule of this layer. A DIRECT citation from MoSPI
    proves the subject is real and trained-on; it does not validate our target
    level, prerequisites or anchors. SIH26101_MASTER_CHECKLIST.md section 4.1
    marks that validation BLOCKED-EXTERNAL, and
    docs/internal/SIH26101_WINNING_PLAYBOOK.md section 2 forbids claiming otherwise."""
    for slug, competency in _all_competencies():
        assert competency["authoring_status"] == PROVISIONAL, (
            f"{slug}:{competency['id']} is {competency['authoring_status']}, not PROVISIONAL -- "
            "a source citation is not a domain reviewer's approval"
        )


def test_no_source_claims_approval_of_this_taxonomy():
    """Guards the specific forbidden phrasings: nothing in the registry may
    read as MoSPI/CBC endorsement of PRISM's own competency model."""
    forbidden = ("approved", "endorse", "validated", "official framework", "certified")
    for source_id, entry in SOURCES.items():
        blob = f"{entry['title']} {entry['publisher']}".lower()
        for phrase in forbidden:
            assert phrase not in blob, f"{source_id} title/publisher implies approval: {phrase!r}"


def test_competency_sources_have_no_dangling_entries():
    known = {competency["id"] for _slug, competency in _all_competencies()}
    assert set(COMPETENCY_SOURCES) <= known


def test_validation_rejects_a_citation_to_an_unknown_source():
    catalog = copy.deepcopy(CURRICULA)
    catalog["official-statistics"]["competencies"][0]["source"] = "SRC-404"
    with pytest.raises(ValueError, match="unknown source"):
        validate_curricula(catalog)


def test_validation_rejects_a_citation_with_no_detail():
    catalog = copy.deepcopy(CURRICULA)
    catalog["official-statistics"]["competencies"][0]["source_detail"] = ""
    with pytest.raises(ValueError, match="without saying what in it applies"):
        validate_curricula(catalog)


def test_validation_rejects_an_invalid_strength():
    catalog = copy.deepcopy(CURRICULA)
    catalog["official-statistics"]["competencies"][0]["source_strength"] = "STRONG"
    with pytest.raises(ValueError, match="invalid source_strength"):
        validate_curricula(catalog)


def test_stamping_is_idempotent():
    """It runs at import; a second call from a test or a reload must not
    double-stamp or overwrite a record already in place."""
    catalog = copy.deepcopy(CURRICULA)
    before = copy.deepcopy(catalog)
    stamp_competency_provenance(catalog)
    assert catalog == before


def test_ps02_named_scope_is_fully_cited():
    """Every competency the problem statement names by hand is government-
    backed. This is the claim the demo actually makes, so it gets its own
    test rather than relying on the broader non-DSA sweep above."""
    from services.ps02_coverage import PS02_COVERAGE

    index = {competency["id"]: competency for _slug, competency in _all_competencies()}
    missing = [
        f"{named} ({competency_id})"
        for named, competency_id in PS02_COVERAGE.items()
        if index[competency_id]["source"] == "internal-prototype"
    ]
    assert not missing, f"PS-02 named competencies with no source: {', '.join(missing)}"
