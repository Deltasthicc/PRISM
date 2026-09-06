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

# `mode` values ("configured"/"catalog-fallback") are never translated -- the
# frontend compares them by equality (`status.mode === 'configured'`), so
# translating them would silently break that check. Only `detail` (free text
# shown to a learner) and course/provider display strings are localized.
_DETAIL = {
    "en": {
        "igot_configured": "Live iGOT Karmayogi API configured.",
        "igot_fallback": (
            "No public iGOT Karmayogi partner API exists today. Recommendations link to "
            "the authoritative public catalog instead of a fabricated enrolment record."
        ),
        "nssta_configured": "Live NSSTA/TPAC programme feed configured.",
        "nssta_fallback": (
            "No public NSSTA/TPAC programme API exists today. Recommendations link to "
            "the published NSSTA training-calendar documents instead."
        ),
    },
    "hi": {
        "igot_configured": "लाइव iGOT कर्मयोगी API कॉन्फ़िगर किया गया है।",
        "igot_fallback": (
            "आज कोई सार्वजनिक iGOT कर्मयोगी पार्टनर API मौजूद नहीं है। अनुशंसाएं एक काल्पनिक "
            "नामांकन रिकॉर्ड के बजाय आधिकारिक सार्वजनिक सूची से जुड़ी हैं।"
        ),
        "nssta_configured": "लाइव NSSTA/TPAC कार्यक्रम फ़ीड कॉन्फ़िगर किया गया है।",
        "nssta_fallback": (
            "आज कोई सार्वजनिक NSSTA/TPAC कार्यक्रम API मौजूद नहीं है। अनुशंसाएं प्रकाशित "
            "NSSTA प्रशिक्षण-कैलेंडर दस्तावेज़ों से जुड़ी हैं।"
        ),
    },
}

_PROVIDER_NAME = {
    "en": {"internal-practice": "Internal Practice", "igot": "iGOT Karmayogi", "nssta": "NSSTA / TPAC"},
    "hi": {"internal-practice": "आंतरिक अभ्यास", "igot": "iGOT कर्मयोगी", "nssta": "NSSTA / TPAC"},
}

_TITLE_TEMPLATE = {
    "en": {
        "internal-practice": "Adaptive practice: {label}",
        "igot": "Search iGOT Karmayogi for: {label}",
        "nssta": "Check the NSSTA training calendar for: {label}",
    },
    "hi": {
        "internal-practice": "अनुकूली अभ्यास: {label}",
        "igot": "iGOT कर्मयोगी में खोजें: {label}",
        "nssta": "NSSTA प्रशिक्षण कैलेंडर देखें: {label}",
    },
}

_INTERNAL_PRACTICE_NOTE = {
    "en": "Generated on demand by this app's own adaptive question engine.",
    "hi": "इस ऐप के अपने अनुकूली प्रश्न इंजन द्वारा मांग पर उत्पन्न।",
}


def integration_status(lang: str = "en") -> dict:
    detail = _DETAIL.get(lang, _DETAIL["en"])
    return {
        "igot": {
            "mode": "configured" if IGOT_CONFIGURED else "catalog-fallback",
            "detail": detail["igot_configured"] if IGOT_CONFIGURED else detail["igot_fallback"],
        },
        "nssta": {
            "mode": "configured" if NSSTA_CONFIGURED else "catalog-fallback",
            "detail": detail["nssta_configured"] if NSSTA_CONFIGURED else detail["nssta_fallback"],
        },
    }


def recommend_courses(skill_gaps: list[dict], lang: str = "en") -> list[dict]:
    """Return provider-tagged recommendations for the given gaps.

    Every gap gets one internal-practice entry (this app's own adaptive
    quest, always real and clickable) plus one iGOT and one NSSTA
    catalog-fallback entry. Capped at the 5 highest-priority gaps so the
    list stays scannable; skill_gaps is expected pre-sorted by severity
    (see learning_engine.analyse_competencies).
    """
    status = integration_status(lang)
    provider_name = _PROVIDER_NAME.get(lang, _PROVIDER_NAME["en"])
    title_template = _TITLE_TEMPLATE.get(lang, _TITLE_TEMPLATE["en"])
    courses: list[dict] = []
    for gap in skill_gaps[:5]:
        competency_id = gap["competency_id"]
        label = gap["label"]
        relevance = round(min(5.0, gap.get("gap", 0.0) + 1.0), 2)

        courses.append({
            "course_id": f"practice::{competency_id}",
            "provider": provider_name["internal-practice"],
            "provider_type": "internal-practice",
            "title": title_template["internal-practice"].format(label=label),
            "url": f"/dungeon#{competency_id}",
            "relevance_score": relevance,
            "verification_note": _INTERNAL_PRACTICE_NOTE.get(lang, _INTERNAL_PRACTICE_NOTE["en"]),
        })
        courses.append({
            "course_id": f"igot::{competency_id}",
            "provider": provider_name["igot"],
            "provider_type": "igot",
            "title": title_template["igot"].format(label=label),
            "url": IGOT_CATALOG_URL,
            "relevance_score": relevance,
            "verification_note": status["igot"]["detail"],
        })
        courses.append({
            "course_id": f"nssta::{competency_id}",
            "provider": provider_name["nssta"],
            "provider_type": "nssta",
            "title": title_template["nssta"].format(label=label),
            "url": NSSTA_CATALOG_URL,
            "relevance_score": relevance,
            "verification_note": status["nssta"]["detail"],
        })
    return courses
