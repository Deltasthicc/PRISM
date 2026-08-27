"""Deterministic, explainable competency-gap and pathway calculation."""

from services.curricula import get_curriculum
from services.learning_catalog import recommend_courses


EXPERIENCE_TARGET_CAP = {
    "beginner": 3,
    "intermediate": 4,
    "advanced": 5,
    "expert": 5,
}


def _level_label(score: float) -> str:
    if score < 1.0:
        return "not yet evidenced"
    if score < 2.0:
        return "foundation"
    if score < 3.0:
        return "working knowledge"
    if score < 4.0:
        return "practitioner"
    if score < 4.75:
        return "advanced"
    return "expert"


def analyse_competencies(
    curriculum_slug: str,
    self_ratings: dict[str, float],
    measured_scores: dict[str, float],
    experience_level: str = "beginner",
) -> dict:
    curriculum = get_curriculum(curriculum_slug)
    if not curriculum:
        raise ValueError(f"Unknown curriculum: {curriculum_slug}")

    allowed = {item["id"] for item in curriculum["competencies"]}
    unknown = sorted(set(self_ratings) - allowed)
    if unknown:
        raise ValueError(f"Ratings contain competencies outside this curriculum: {', '.join(unknown)}")

    target_cap = EXPERIENCE_TARGET_CAP.get(experience_level, 3)
    competency_results = []
    for item in curriculum["competencies"]:
        competency_id = item["id"]
        self_score = self_ratings.get(competency_id)
        measured = measured_scores.get(competency_id)

        if measured is not None and self_score is not None:
            observed = measured * 0.65 + self_score * 0.35
            evidence = "65% demonstrated performance + 35% self-assessment"
        elif measured is not None:
            observed = measured
            evidence = "demonstrated performance"
        elif self_score is not None:
            observed = self_score
            evidence = "self-assessment only; diagnostic evidence still required"
        else:
            observed = 0.0
            evidence = "no evidence yet"

        role_target = float(item.get("target_level", 3))
        pathway_target = min(role_target, float(target_cap))
        gap = max(0.0, pathway_target - observed)
        if gap >= 2.5:
            priority = "critical"
        elif gap >= 1.5:
            priority = "high"
        elif gap >= 0.5:
            priority = "medium"
        else:
            priority = "maintain"

        competency_results.append(
            {
                "competency_id": competency_id,
                "label": item["label"],
                "description": item["description"],
                "prerequisites": item.get("prerequisites", []),
                "observed_level": round(observed, 2),
                "observed_label": _level_label(observed),
                "pathway_target": pathway_target,
                "role_target": role_target,
                "gap": round(gap, 2),
                "priority": priority,
                "evidence": evidence,
            }
        )

    skill_gaps = [item for item in competency_results if item["gap"] >= 0.5]
    order = {item["id"]: index for index, item in enumerate(curriculum["competencies"])}
    skill_gaps.sort(key=lambda item: (-item["gap"], order[item["competency_id"]]))

    # Build a teachable order: prerequisites first, then the largest remaining
    # gaps. This keeps the output interpretable and lets a judge change a
    # prerequisite live without retraining a model.
    pending = {item["competency_id"]: item for item in skill_gaps}
    pathway = []
    while pending:
        ready = [
            item for item in pending.values()
            if all(prerequisite not in pending for prerequisite in item["prerequisites"])
        ]
        if not ready:  # Defensive fallback for malformed/cyclic seed data.
            ready = list(pending.values())
        ready.sort(key=lambda item: (-item["gap"], order[item["competency_id"]]))
        for item in ready:
            pathway.append(
                {
                    "step": len(pathway) + 1,
                    **item,
                    "recommended_action": (
                        "Complete a diagnostic and foundation module"
                        if item["observed_level"] < 1
                        else "Complete targeted learning, then re-assess with applied questions"
                    ),
                }
            )
            pending.pop(item["competency_id"], None)

    courses = recommend_courses(skill_gaps)
    return {
        "curriculum_slug": curriculum_slug,
        "curriculum_name": curriculum["name"],
        "domain": curriculum["domain"],
        "experience_level": experience_level,
        "method": {
            "scale": "0-5 proficiency",
            "demonstrated_weight": 0.65,
            "self_assessment_weight": 0.35,
            "note": "Self-ratings never override demonstrated performance; missing evidence is surfaced explicitly.",
        },
        "competencies": competency_results,
        "skill_gaps": skill_gaps,
        "pathway": pathway,
        "courses": courses,
    }
