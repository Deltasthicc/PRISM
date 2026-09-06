"""JSON-backed course catalogue with deterministic keyword matching.

New file, so ownership is assigned before first modification rather than
assumed (SIH26101_TEAM_ORCHESTRATION.md section 2, "Unlisted legacy files are
assigned ... using the nearest mission owner"). Nearest mission owner is
Lane 5, which owns provider recommendations and `learning_catalog.py`.
Recorded in `docs/contracts/competency-evidence.md` section 9.6; Lane 3
authored the data and the matcher, Lane 5 owns the wiring.

Why a JSON file and not a table: a course catalogue is read-only reference
data that ships with the code, like `curricula.py`. Persisting it would need a
new Lane 2 model plus an Alembic migration and would buy nothing until there
is a live provider sync to reconcile against -- and `learning_materials`
cannot stand in, because its `player_id`, `filename` and `sha256` are all
NOT NULL and describe one learner's uploaded file, not a published course.
When a real adapter exists, this module is the seam to replace.

Matching is deliberately keyword-based and deterministic, not embeddings:
every recommendation can state exactly which words matched, a judge can change
a competency label and watch the result move, and there is no model to explain
away. SIH26101_WINNING_PLAYBOOK.md section 6 puts a vector adapter behind
"only when real retrieval is implemented"; this is the honest version until
then.

Nothing here performs a live provider call. Every record is CATALOGUE: a real
published course at a real URL, with no enrolment, completion or writeback.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "data" / "course_catalogue.json"

# Words that appear in so many competency labels and course titles that
# matching on them would rank almost everything equally. Kept explicit rather
# than pulled from an NLP package: the list is short, auditable, and a reviewer
# can see exactly what the matcher ignores.
STOPWORDS = frozenset({
    "a", "an", "and", "for", "from", "in", "into", "of", "on", "or", "the", "to", "with",
    "using", "its", "their", "this", "that", "how", "what", "why", "when",
    # Domain-generic: true of nearly every record in a statistics-training catalogue.
    "data", "statistics", "statistical", "course", "training", "programme", "program",
    "introduction", "basics", "basic", "fundamentals", "overview", "concepts", "concept",
    "management", "analysis", "skills", "skill", "official", "government",
})

TOKEN_RE = re.compile(r"[a-z][a-z0-9+#-]{2,}")

# A course explicitly mapped to the competency always outranks a keyword hit.
# The two are different kinds of claim -- a curated mapping versus a lexical
# coincidence -- so they get different reasons in the result, never a blended
# score a reader cannot take apart.
MAPPED_SCORE = 1.0

MATCH_MAPPED = "mapped"
MATCH_KEYWORD = "keyword"

# A keyword hit needs at least two distinct query terms. One shared word is
# coincidence, not relevance: "Design Thinking" overlaps "Sampling Design" on
# `design` alone and is not a sampling course. Recommending it anyway would be
# the padded-results failure the playbook's honesty rules exist to prevent --
# an empty list is a better answer than a wrong one, and the pathway already
# has internal practice to fall back on.
MIN_KEYWORD_TERMS = 2


def _tokenize(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS}


@lru_cache(maxsize=1)
def _load() -> dict:
    with CATALOGUE_PATH.open(encoding="utf-8") as handle:
        document = json.load(handle)

    for course in document["courses"]:
        # Precomputed once per process. The haystack deliberately excludes the
        # provider name: "ISB Hyderabad" appearing in a query should not pull
        # in every ISB course regardless of subject.
        course["_tokens"] = _tokenize(f"{course['title']} {course['track']} {course['locator']}")
    return document


def catalogue_status() -> dict:
    """What routes/learning.py's integration-status view can show. Mirrors
    learning_catalog.integration_status()'s shape so both can sit side by side
    without a consumer special-casing one of them."""
    document = _load()
    return {
        "mode": "catalogue-json",
        "catalogue_version": document["catalogue_version"],
        "retrieved": document["retrieved"],
        "total_courses": len(document["courses"]),
        "status": document["status"],
        "detail": document["note"],
    }


def all_courses() -> list[dict]:
    """Every record, without the internal token cache."""
    return [
        {key: value for key, value in course.items() if not key.startswith("_")}
        for course in _load()["courses"]
    ]


def search(query: str, limit: int = 10) -> list[dict]:
    """Free-text keyword search over the catalogue.

    Ranked by how many distinct query terms a course matches, then by title so
    ties are stable and the same query always returns the same order -- the
    determinism golden fixtures depend on.
    """
    terms = _tokenize(query)
    if not terms:
        return []

    hits = []
    for course in _load()["courses"]:
        matched = terms & course["_tokens"]
        if len(matched) >= MIN_KEYWORD_TERMS:
            hits.append((len(matched), sorted(matched), course))

    hits.sort(key=lambda hit: (-hit[0], hit[2]["title"]))
    return [
        _present(course, MATCH_KEYWORD, round(count / len(terms), 2), matched)
        for count, matched, course in hits[:limit]
    ]


def recommend_for_competency(
    competency_id: str,
    label: str = "",
    description: str = "",
    limit: int = 5,
) -> list[dict]:
    """Courses for one competency: curated mappings first, then keyword hits.

    `label` and `description` come from the competency record in
    services/curricula.py. Passing them is optional -- with neither, this
    returns the curated mappings alone, which is the conservative result.
    """
    document = _load()
    mapped = []
    remaining = []
    for course in document["courses"]:
        if competency_id in course["competency_ids"]:
            mapped.append(course)
        else:
            remaining.append(course)

    # Provider order is display-stability only, never a quality ranking.
    provider_order = {"igot": 0, "nssta": 1, "institute": 2}
    mapped.sort(key=lambda course: (provider_order[course["provider_type"]], course["title"]))
    results = [_present(course, MATCH_MAPPED, MAPPED_SCORE, []) for course in mapped]

    if len(results) >= limit:
        return results[:limit]

    terms = _tokenize(f"{label} {description}")
    if not terms:
        return results

    hits = []
    for course in remaining:
        matched = terms & course["_tokens"]
        if len(matched) >= MIN_KEYWORD_TERMS:
            hits.append((len(matched), sorted(matched), course))
    hits.sort(key=lambda hit: (-hit[0], hit[2]["title"]))

    for count, matched, course in hits:
        if len(results) >= limit:
            break
        results.append(_present(course, MATCH_KEYWORD, round(count / len(terms), 2), matched))
    return results


def _present(course: dict, match_type: str, score: float, matched_terms: list[str]) -> dict:
    """One recommendation, carrying why it was chosen.

    `match_reason` is the point of this module: a learner (and a judge) can see
    that a course was curated for this competency, or exactly which words made
    it surface. A recommendation that cannot say why it appeared is the kind of
    unexplainable output CLAUDE.md invariant #3 rules out.
    """
    return {
        "course_id": course["course_id"],
        "provider": course["provider"],
        "provider_type": course["provider_type"],
        "provider_record_id": course["provider_record_id"],
        "title": course["title"],
        "duration": course["duration"],
        "url": course["url"],
        "competency_ids": list(course["competency_ids"]),
        "source_id": course["source_id"],
        "locator": course["locator"],
        "status": course["status"],
        "mapping_assurance": course["mapping_assurance"],
        "retrieved": course["retrieved"],
        "match_type": match_type,
        "match_score": score,
        "matched_terms": list(matched_terms),
        "match_reason": (
            f"Curated mapping to this competency, {course['mapping_assurance'].lower()}"
            if match_type == MATCH_MAPPED
            else f"Keyword match on: {', '.join(matched_terms)}"
        ),
    }
