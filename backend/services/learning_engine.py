"""Deterministic, explainable competency-gap and pathway calculation."""

from services.curricula import get_curriculum
from services.learning_catalog import recommend_courses
from services.role_targets import FRAMEWORK_VERSION, experience_cap, resolve_role_target

# Versions the 65/35 blend itself (CLAUDE.md architectural invariant #4: "the
# 65/35 blend ... remain versioned prototype policies until validated").
# Distinct from role_targets.FRAMEWORK_VERSION, which versions target
# selection -- these are two independently-changeable policies.
ASSESSMENT_POLICY_VERSION = "prototype-v1"


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
    job_role: str = "",
    designation: str = "",
) -> dict:
    curriculum = get_curriculum(curriculum_slug)
    if not curriculum:
        raise ValueError(f"Unknown curriculum: {curriculum_slug}")

    allowed = {item["id"] for item in curriculum["competencies"]}
    unknown = sorted(set(self_ratings) - allowed)
    if unknown:
        raise ValueError(f"Ratings contain competencies outside this curriculum: {', '.join(unknown)}")

    target_cap = experience_cap(experience_level)
    competency_results = []
    for item in curriculum["competencies"]:
        competency_id = item["id"]
        self_score = self_ratings.get(competency_id)
        measured = measured_scores.get(competency_id)

        # evidence_sources uses Lane 2's EVIDENCE_TYPES vocabulary
        # (backend/models/governance.py: self_report, observed_practice, ...)
        # so a future switch to real EvidenceRecord rows needs no relabeling.
        evidence_sources = []
        if measured is not None:
            evidence_sources.append("observed_practice")
        if self_score is not None:
            evidence_sources.append("self_report")

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

        role_target_info = resolve_role_target(
            competency_id, item.get("target_level", 3), job_role, designation
        )
        role_target = role_target_info["target_level"]
        pathway_target = min(role_target, float(target_cap))
        gap = max(0.0, pathway_target - observed)
        has_evidence = bool(evidence_sources)
        if not has_evidence:
            # Zero evidence must never be indistinguishable from a
            # demonstrated low score (CLAUDE.md architectural invariant #3):
            # "unassessed" overrides the gap-derived tier below even though
            # the gap number itself is unchanged and still drives sort order.
            priority = "unassessed"
        elif gap >= 2.5:
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
                "role_target_source": role_target_info["source"],
                "matched_role": role_target_info["matched_role"],
                "gap": round(gap, 2),
                "priority": priority,
                "has_evidence": has_evidence,
                "evidence_sources": evidence_sources,
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
                        "Complete a diagnostic to establish a baseline -- no evidence recorded yet"
                        if item["priority"] == "unassessed"
                        else "Complete a diagnostic and foundation module"
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
        "job_role": job_role,
        "designation": designation,
        "method": {
            "scale": "0-5 proficiency",
            "demonstrated_weight": 0.65,
            "self_assessment_weight": 0.35,
            "note": "Self-ratings never override demonstrated performance; missing evidence is surfaced explicitly.",
            "policy_version": ASSESSMENT_POLICY_VERSION,
            "role_target_framework_version": FRAMEWORK_VERSION,
        },
        "competencies": competency_results,
        "skill_gaps": skill_gaps,
        "pathway": pathway,
        "courses": courses,
    }
