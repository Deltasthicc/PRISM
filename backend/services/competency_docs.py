"""Role -> categories -> verified government documents -> cited MCQs.

This is the demo spine: pick a role from `services/role_catalogue.py`, get the
competencies it needs, get the government documents that teach them, and
generate a quiz whose every question quotes one of those documents.

Every document in `data/document_corpus.json` was downloaded, hashed and
text-extracted on `verified_on`. `sha256` is of the exact bytes retrieved, so
a fetch that produces a different hash means the published file changed --
reported as `hash_mismatch`, never silently accepted. That is what makes a
citation checkable rather than decorative.

Why this does not call `services/content_ingestion.py`: that module bounds
*untrusted learner uploads* at 5 MB and 100 pages. These documents are
pre-verified, hash-pinned government publications, and several legitimately
exceed both limits (the National Accounts sources-and-methods volume is 353
pages, the PLFS annual report 643). A different threat model needs a different
reader, so this one bounds by an explicit page window instead and reports that
window as the citation locator. Learner uploads must keep going through
content_ingestion.

Nothing here is a live provider integration. A document is a published file at
a public URL; there is no enrolment, completion or writeback.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

from services.role_catalogue import (
    CATEGORY_LABELS,
    COMPETENCY_CATEGORY,
    ROLES,
    categories_for_role,
)

CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "document_corpus.json"
CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / ".doc_cache"

# Pages read from the front of a document for quiz generation. Bounded so a
# 643-page report cannot turn one quiz request into minutes of parsing, and so
# the excerpt a question cites is always locatable by a human ("pages 1-20").
DEFAULT_PAGE_WINDOW = 20

# Enough text to build four distinct questions from without the extractor
# running out of usable sentences.
MIN_USABLE_CHARS = 1200

# Government publications open with cover pages, ministry mastheads, contents
# tables and foreword matter. Feeding those to the generator produces questions
# like "MINISTRY OF STATISTICS AND PROGRAMME _____" -- grounded in the source
# and completely worthless as a competency probe. Skipping a proportional
# amount of front matter is the single biggest quality lever available here,
# and it costs nothing.
FRONT_MATTER_SKIP = 2
FRONT_MATTER_SKIP_LONG = 6
LONG_DOCUMENT_PAGES = 40


class DocumentUnavailable(Exception):
    """Raised when a corpus document cannot be fetched or read. Routes should
    surface this as a 503 with the doc_id, never as a 500."""


_corpus_cache: dict | None = None


def _corpus() -> dict:
    global _corpus_cache
    if _corpus_cache is None:
        with CORPUS_PATH.open(encoding="utf-8") as handle:
            _corpus_cache = json.load(handle)
    return _corpus_cache


def corpus_status() -> dict:
    document = _corpus()
    by_category: dict[str, int] = {}
    for record in document["documents"]:
        by_category[record["category"]] = by_category.get(record["category"], 0) + 1
    return {
        "corpus_version": document["corpus_version"],
        "verified_on": document["verified_on"],
        "total_documents": document["total_documents"],
        "documents_by_category": {
            CATEGORY_LABELS[key]: value for key, value in sorted(by_category.items())
        },
        "competencies_covered": len(
            {c for d in document["documents"] for c in d["competency_ids"]}
        ),
        "note": document["note"],
    }


def all_documents() -> list[dict]:
    return [dict(record) for record in _corpus()["documents"]]


def documents_for_competency(competency_id: str) -> list[dict]:
    return [
        dict(record)
        for record in _corpus()["documents"]
        if competency_id in record["competency_ids"]
    ]


def documents_for_role(role_id: str) -> list[dict]:
    """Every corpus document touching any competency this role targets.

    Each result carries `matched_competencies` -- the intersection with the
    role's own targets -- so a learner sees why the document is in their plan
    rather than an unexplained reading list.
    """
    role = ROLES.get(role_id)
    if not role:
        return []
    targets = set(role["competency_targets"])
    results = []
    for record in _corpus()["documents"]:
        matched = sorted(targets.intersection(record["competency_ids"]))
        if matched:
            entry = dict(record)
            entry["matched_competencies"] = matched
            results.append(entry)
    # Most relevant first (most of the role's competencies covered), then by
    # title so the order is stable across runs.
    results.sort(key=lambda item: (-len(item["matched_competencies"]), item["title"]))
    return results


def get_document(doc_id: str) -> dict | None:
    for record in _corpus()["documents"]:
        if record["doc_id"] == doc_id:
            return dict(record)
    return None


def _cache_path(doc_id: str) -> Path:
    return CACHE_DIR / f"{doc_id}.pdf"


def fetch_document_bytes(doc_id: str, *, allow_network: bool = True) -> tuple[bytes, str]:
    """Return the document's bytes and its integrity verdict.

    Verdicts: `cached`, `verified` (downloaded, hash matches the corpus),
    `hash_mismatch` (downloaded but the published file has changed). A
    mismatch is returned, not raised -- the caller decides whether a changed
    government document should still be quizzed from, and the demo reports it
    rather than hiding it.
    """
    record = get_document(doc_id)
    if not record:
        raise DocumentUnavailable(f"Unknown document: {doc_id}")

    cached = _cache_path(doc_id)
    if cached.exists():
        return cached.read_bytes(), "cached"

    if not allow_network:
        raise DocumentUnavailable(f"{doc_id} is not cached and network access is disabled")

    try:
        import httpx

        with httpx.Client(follow_redirects=True, timeout=90.0, verify=False) as client:
            response = client.get(record["url"])
            response.raise_for_status()
            data = response.content
    except Exception as exc:
        raise DocumentUnavailable(f"Could not fetch {doc_id}: {type(exc).__name__}") from exc

    verdict = "verified" if hashlib.sha256(data).hexdigest() == record["sha256"] else "hash_mismatch"
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached.write_bytes(data)
    return data, verdict


def _front_matter_skip(total_pages: int) -> int:
    """How many opening pages to drop. Never so many that a short document is
    left with nothing -- a 7-page FAQ has no room for a 6-page skip."""
    if total_pages <= 4:
        return 0
    skip = FRONT_MATTER_SKIP_LONG if total_pages >= LONG_DOCUMENT_PAGES else FRONT_MATTER_SKIP
    return min(skip, max(0, total_pages - 3))


def _is_boilerplate(line: str) -> bool:
    """Page furniture that survives the page skip: mastheads, running heads,
    page numbers, contents rows and figure captions. These make grammatically
    valid but meaningless cloze questions."""
    stripped = line.strip()
    if len(stripped) < 25:
        return True
    letters = [character for character in stripped if character.isalpha()]
    # An all-caps line of any length is a heading, not prose.
    if letters and sum(1 for character in letters if character.isupper()) / len(letters) > 0.7:
        return True
    # Contents/index rows: mostly dot leaders or digits.
    digits_and_dots = sum(1 for character in stripped if character.isdigit() or character == ".")
    return digits_and_dots / len(stripped) > 0.3


def extract_document_text(
    doc_id: str,
    *,
    page_window: int = DEFAULT_PAGE_WINDOW,
    page_start: int | None = None,
    allow_network: bool = True,
) -> dict:
    """Read a bounded page window and return the text plus its citation locator.

    `page_start` is 0-indexed and defaults to skipping front matter. The
    returned `locator` reports the real 1-indexed page range actually read, so
    a citation can be checked against the published PDF.
    """
    record = get_document(doc_id)
    if not record:
        raise DocumentUnavailable(f"Unknown document: {doc_id}")

    data, integrity = fetch_document_bytes(doc_id, allow_network=allow_network)

    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:
        raise DocumentUnavailable(f"Could not parse {doc_id} as a PDF") from exc

    total_pages = len(reader.pages)
    start = _front_matter_skip(total_pages) if page_start is None else max(0, page_start)
    start = min(start, max(0, total_pages - 1))
    end = min(start + page_window, total_pages)

    raw = "\n".join((reader.pages[index].extract_text() or "") for index in range(start, end))
    text = "\n".join(line for line in raw.splitlines() if not _is_boilerplate(line)).strip()

    if len(text) < MIN_USABLE_CHARS:
        raise DocumentUnavailable(
            f"{doc_id} yielded only {len(text)} usable characters from pages "
            f"{start + 1}-{end}; it may be a scanned document needing OCR"
        )

    return {
        "doc_id": doc_id,
        "title": record["title"],
        "publisher": record["publisher"],
        "url": record["url"],
        "source_id": record["source_id"],
        "integrity": integrity,
        "sha256": record["sha256"],
        "locator": f"pages {start + 1}-{end} of {total_pages}",
        "character_count": len(text),
        "text": text,
    }


async def quiz_from_document(
    doc_id: str,
    *,
    count: int = 4,
    difficulty: str = "mixed",
    language: str = "English",
    page_window: int = DEFAULT_PAGE_WINDOW,
    page_start: int | None = None,
    allow_network: bool = True,
) -> dict:
    """Generate MCQs whose every `source_excerpt` is quoted from this document.

    Delegates to Lane 4's `services/quiz_generator.generate_quiz`, so the
    grounding validation and the extractive fallback behave exactly as they do
    for a learner upload. With no `GEMINI_API_KEY` configured this returns
    `extractive-fallback` questions -- still quoted from the source, just
    simpler in form. That is reported, never disguised.
    """
    from services.quiz_generator import generate_quiz

    extracted = extract_document_text(
        doc_id,
        page_window=page_window,
        page_start=page_start,
        allow_network=allow_network,
    )
    questions, mode = await generate_quiz(extracted["text"], count, difficulty, language)

    return {
        "doc_id": doc_id,
        "title": extracted["title"],
        "publisher": extracted["publisher"],
        "url": extracted["url"],
        "source_id": extracted["source_id"],
        "locator": extracted["locator"],
        "integrity": extracted["integrity"],
        "generation_mode": mode,
        "question_count": len(questions),
        "questions": questions,
        "status": "DRAFT",
        "review_note": (
            "Generated items are drafts until automated checks and an authorized human "
            "review pass (CLAUDE.md invariant 9)."
        ),
    }


def role_learning_plan(role_id: str) -> dict:
    """The full role -> categories -> competencies -> documents view.

    Deliberately no quiz here: this is the reading plan, and generating a quiz
    costs a download plus a parse per document. `quiz_from_document` is called
    separately for whichever competency the learner actually starts on.
    """
    role = ROLES.get(role_id)
    if not role:
        raise DocumentUnavailable(f"Unknown role: {role_id}")

    grouped = categories_for_role(role_id)
    documents = documents_for_role(role_id)
    by_competency: dict[str, list[dict]] = {}
    for record in documents:
        for competency_id in record["matched_competencies"]:
            by_competency.setdefault(competency_id, []).append(
                {
                    "doc_id": record["doc_id"],
                    "title": record["title"],
                    "publisher": record["publisher"],
                    "url": record["url"],
                    "pages": record["pages"],
                    "source_id": record["source_id"],
                    "link_status": record["link_status"],
                }
            )

    categories = []
    for category, competency_ids in sorted(grouped.items()):
        categories.append(
            {
                "category": category,
                "category_label": CATEGORY_LABELS[category],
                "competencies": [
                    {
                        "competency_id": competency_id,
                        "target_level": role["competency_targets"][competency_id],
                        "documents": by_competency.get(competency_id, []),
                        "document_count": len(by_competency.get(competency_id, [])),
                    }
                    for competency_id in competency_ids
                ],
            }
        )

    covered = sum(1 for c in role["competency_targets"] if by_competency.get(c))
    return {
        "role_id": role_id,
        "designation": role["designation"],
        "job_role": role["job_role"],
        "department": role["department"],
        "cadre": role["cadre"],
        "experience_level": role["experience_level"],
        "framework_version": role["framework_version"],
        "assurance": role["assurance"],
        "approved_by": role["approved_by"],
        "categories": categories,
        "total_competencies": len(role["competency_targets"]),
        "competencies_with_documents": covered,
        "total_documents": len(documents),
        "note": (
            "Targets are team-authored and PROVISIONAL. Documents are real government "
            "publications verified by hash; they are not an endorsement of these targets."
        ),
    }


def uncovered_competencies() -> dict[str, list[str]]:
    """Competencies a role targets that no corpus document teaches, grouped by
    role. Surfaced rather than hidden: an honest gap is the input to the next
    round of corpus building."""
    covered = {c for d in _corpus()["documents"] for c in d["competency_ids"]}
    gaps = {}
    for role_id, role in ROLES.items():
        missing = sorted(set(role["competency_targets"]) - covered)
        if missing:
            gaps[role_id] = missing
    return gaps


def category_of(competency_id: str) -> str | None:
    return COMPETENCY_CATEGORY.get(competency_id)
