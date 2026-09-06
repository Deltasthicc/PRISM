"""Runnable end-to-end demo: pick a role, see the plan, docs and real MCQs.

    python -m scripts.role_demo                     # list the roles
    python -m scripts.role_demo sso_price           # plan + documents
    python -m scripts.role_demo sso_price --quiz    # plan + documents + MCQs
    python -m scripts.role_demo sso_price --quiz --offline   # cached files only

The first --quiz run downloads the document it quizzes from (a few MB) and
caches it under backend/data/.doc_cache/, so later runs are offline-capable.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.competency_docs import (  # noqa: E402
    DocumentUnavailable,
    corpus_status,
    documents_for_role,
    quiz_from_document,
    role_learning_plan,
    uncovered_competencies,
)
from services.curricula import CURRICULA  # noqa: E402
from services.role_catalogue import list_roles  # noqa: E402

RULE = "=" * 78
THIN = "-" * 78

_LABELS = {
    competency["id"]: competency["label"]
    for curriculum in CURRICULA.values()
    for competency in curriculum["competencies"]
}


def _print_roles() -> None:
    print(RULE)
    print("AVAILABLE ROLES  (hardcoded demo set)")
    print(RULE)
    for role in list_roles():
        print(f"\n  {role['role_id']}")
        print(f"     Designation : {role['designation']}")
        print(f"     Job role    : {role['job_role']}")
        print(f"     Department  : {role['department']}")
        print(f"     Assignment  : {role['current_assignment']}")
        print(f"     Cadre       : {role['cadre']}  ({role['experience_level']})")
        print(f"     Focus       : {', '.join(role['focus_categories'])}")
    status = corpus_status()
    print(f"\n{THIN}")
    print(f"Corpus: {status['total_documents']} verified documents, "
          f"{status['competencies_covered']} competencies covered")
    for label, count in status["documents_by_category"].items():
        print(f"   {label:<28} {count}")
    print(f"\nRun:  python -m scripts.role_demo <role_id> --quiz")


def _print_plan(role_id: str) -> dict:
    plan = role_learning_plan(role_id)
    print(RULE)
    print(f"LEARNING PLAN  ·  {plan['designation']} — {plan['job_role']}")
    print(RULE)
    print(f"  Department  : {plan['department']}")
    print(f"  Cadre       : {plan['cadre']}")
    print(f"  Experience  : {plan['experience_level']}")
    print(f"  Targets     : {plan['framework_version']} · assurance {plan['assurance']} "
          f"· approved_by {plan['approved_by']}")

    for category in plan["categories"]:
        print(f"\n{THIN}")
        print(f"CATEGORY: {category['category_label'].upper()}")
        print(THIN)
        for competency in category["competencies"]:
            label = _LABELS.get(competency["competency_id"], competency["competency_id"])
            print(f"\n  {label}  (target level {competency['target_level']})")
            if not competency["documents"]:
                print("     no verified government document in the corpus yet")
                continue
            for document in competency["documents"]:
                print(f"     • {document['title']}")
                print(f"       {document['publisher']} · {document['pages']} pages "
                      f"· {document['source_id']} · {document['link_status']}")
                print(f"       {document['url']}")

    print(f"\n{THIN}")
    print(f"  {plan['competencies_with_documents']}/{plan['total_competencies']} competencies "
          f"have at least one document · {plan['total_documents']} documents in this plan")
    print(f"  {plan['note']}")
    return plan


async def _print_quiz(role_id: str, count: int, offline: bool) -> None:
    documents = documents_for_role(role_id)
    if not documents:
        print("\nNo documents for this role; nothing to quiz from.")
        return

    target = documents[0]
    print(f"\n{RULE}")
    print("DEMONSTRATED-COMPETENCY QUIZ")
    print(RULE)
    print(f"  Source     : {target['title']}")
    print(f"  Publisher  : {target['publisher']}")
    print(f"  URL        : {target['url']}")
    print(f"  Tests      : {', '.join(_LABELS.get(c, c) for c in target['matched_competencies'])}")

    try:
        quiz = await quiz_from_document(
            target["doc_id"], count=count, allow_network=not offline
        )
    except DocumentUnavailable as exc:
        print(f"\n  Could not build a quiz: {exc}")
        return

    print(f"  Locator    : {quiz['locator']}")
    print(f"  Integrity  : {quiz['integrity']}  (sha256 {quiz['sha256'][:16]}…)"
          if "sha256" in quiz else f"  Integrity  : {quiz['integrity']}")
    print(f"  Generated  : {quiz['generation_mode']} · status {quiz['status']}")

    for index, question in enumerate(quiz["questions"], 1):
        print(f"\n{THIN}")
        print(f"Q{index}. {question['question']}")
        for option_index, option in enumerate(question["options"]):
            marker = "*" if option_index == question["answer_index"] else " "
            print(f"    {marker} {chr(65 + option_index)}. {option}")
        print(f"    Bloom      : {question['bloom_level']}")
        print(f"    Explanation: {question['explanation'][:150]}")
        excerpt = " ".join(question["source_excerpt"].split())
        print(f"    Cited from : \"{excerpt[:170]}…\"")

    print(f"\n{THIN}")
    print(f"  {quiz['review_note']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Role → documents → MCQ demo")
    parser.add_argument("role_id", nargs="?", help="role id; omit to list all roles")
    parser.add_argument("--quiz", action="store_true", help="also generate MCQs")
    parser.add_argument("--count", type=int, default=4, help="how many MCQs (default 4)")
    parser.add_argument("--offline", action="store_true", help="use cached documents only")
    parser.add_argument("--gaps", action="store_true", help="show uncovered competencies")
    args = parser.parse_args()

    if args.gaps:
        gaps = uncovered_competencies()
        print(RULE)
        print("COMPETENCIES TARGETED BY A ROLE WITH NO DOCUMENT YET")
        print(RULE)
        if not gaps:
            print("  none")
        for role_id, missing in sorted(gaps.items()):
            print(f"  {role_id:<24} {', '.join(missing)}")
        return

    if not args.role_id:
        _print_roles()
        return

    try:
        _print_plan(args.role_id)
    except DocumentUnavailable as exc:
        print(f"{exc}\n")
        _print_roles()
        return

    if args.quiz:
        asyncio.run(_print_quiz(args.role_id, args.count, args.offline))


if __name__ == "__main__":
    main()
