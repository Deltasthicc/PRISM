"""
Catalog boundary for iGOT Karmayogi and NSSTA/TPAC recommendations.

No public partner API exists for either provider today (see
docs/SIH26101_FEASIBILITY_AND_ROADMAP.md, section 3.4) -- this module is
deliberately honest about that rather than fabricating a course ID,
enrolment, or completion record. Every recommendation either points at this
app's own adaptive practice quests (verifiable, real) or at the provider's
public catalog page (real, but not a confirmed live sync). integration_status()
is what routes/learning.py's GET /learning/integrations/status and the
Academy UI's "iGOT mode: ..." line read from -- flip a provider to
"configured" only once a real adapter exists behind these functions.
"""
from __future__ import annotations

import os

IGOT_CATALOG_URL = "https://igotkarmayogi.gov.in/"
NSSTA_CATALOG_URL = "https://nssta.gov.in/document"

# Set these once a real partner contract exists; until then every call below
# reports "catalog-fallback", never a fabricated "configured" sync.
IGOT_CONFIGURED = bool(os.getenv("IGOT_API_BASE_URL"))
NSSTA_CONFIGURED = bool(os.getenv("NSSTA_API_BASE_URL"))


def integration_status() -> dict:
    return {
        "igot": {
            "mode": "configured" if IGOT_CONFIGURED else "catalog-fallback",
            "detail": (
                "Live iGOT Karmayogi API configured."
                if IGOT_CONFIGURED
                else (
                    "No public iGOT Karmayogi partner API exists today. Recommendations link to "
                    "the authoritative public catalog instead of a fabricated enrolment record."
                )
            ),
        },
        "nssta": {
            "mode": "configured" if NSSTA_CONFIGURED else "catalog-fallback",
            "detail": (
                "Live NSSTA/TPAC programme feed configured."
                if NSSTA_CONFIGURED
                else (
                    "No public NSSTA/TPAC programme API exists today. Recommendations link to "
                    "the published NSSTA training-calendar documents instead."
                )
            ),
        },
    }


def recommend_courses(skill_gaps: list[dict]) -> list[dict]:
    """Return provider-tagged recommendations for the given gaps.

    Every gap gets one internal-practice entry (this app's own adaptive
    quest, always real and clickable) plus one iGOT and one NSSTA
    catalog-fallback entry. Capped at the 5 highest-priority gaps so the
    list stays scannable; skill_gaps is expected pre-sorted by severity
    (see learning_engine.analyse_competencies).
    """
    status = integration_status()
    courses: list[dict] = []
    for gap in skill_gaps[:5]:
        competency_id = gap["competency_id"]
        label = gap["label"]
        relevance = round(min(5.0, gap.get("gap", 0.0) + 1.0), 2)

        courses.append({
            "course_id": f"practice::{competency_id}",
            "provider": "SkillQuest Practice",
            "provider_type": "internal-practice",
            "title": f"Adaptive practice: {label}",
            "url": f"/dungeon#{competency_id}",
            "relevance_score": relevance,
            "verification_note": "Generated on demand by this app's own adaptive question engine.",
        })
        courses.append({
            "course_id": f"igot::{competency_id}",
            "provider": "iGOT Karmayogi",
            "provider_type": "igot",
            "title": f"Search iGOT Karmayogi for: {label}",
            "url": IGOT_CATALOG_URL,
            "relevance_score": relevance,
            "verification_note": status["igot"]["detail"],
        })
        courses.append({
            "course_id": f"nssta::{competency_id}",
            "provider": "NSSTA / TPAC",
            "provider_type": "nssta",
            "title": f"Check the NSSTA training calendar for: {label}",
            "url": NSSTA_CATALOG_URL,
            "relevance_score": relevance,
            "verification_note": status["nssta"]["detail"],
        })
    return courses
