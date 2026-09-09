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

from integrations.provider import LiveHTTPProviderAdapter, SimulatedIGOTAdapter

IGOT_CATALOG_URL = "https://igotkarmayogi.gov.in/"
NSSTA_CATALOG_URL = "https://nssta.gov.in/document"

# Read once at import, same as before -- but no longer the whole story. An
# env var being *set* only selects which adapter integration_status() below
# asks; whether that adapter's health_check() actually succeeds is what
# decides the reported mode now, per docs/contracts/provider-adapter.md's own
# rule that "an environment variable alone must never imply LIVE". Kept under
# these names for backward compatibility with anything importing them
# directly (e.g. tests/test_learning_platform.py's importlib.reload seam).
IGOT_CONFIGURED = bool(os.getenv("IGOT_API_BASE_URL"))
NSSTA_CONFIGURED = bool(os.getenv("NSSTA_API_BASE_URL"))

# `mode` values use the fixed, documented vocabulary (CODEX.md/CLAUDE.md
# architectural invariants: SIMULATED, CATALOGUE, LIVE, PROVISIONAL,
# NO EVIDENCE -- see tests/test_competency_status_vocabulary.py) instead of
# this module's old "configured"/"catalog-fallback" pair, which matched
# nothing else in the codebase's vocabulary. `CATALOGUE` covers both "never
# configured" and "configured but the health check failed" -- either way,
# recommendations fall back to the real public catalog link, which is
# genuinely what CATALOGUE means here; the *why* goes in `detail`, not in a
# sixth ad hoc mode value. The frontend compares `mode` by equality, so this
# is a breaking rename for any consumer still checking "configured" --
# frontend/lib/api and frontend/components were updated in the same change.
_DETAIL = {
    "en": {
        "igot_live": "Live iGOT Karmayogi API reachable (health check succeeded).",
        "igot_error": (
            "IGOT_API_BASE_URL is set but the health check failed -- falling back to the "
            "authoritative public catalog instead of reporting a live sync that isn't real."
        ),
        "igot_fallback": (
            "No public iGOT Karmayogi partner API exists today. Recommendations link to "
            "the authoritative public catalog instead of a fabricated enrolment record."
        ),
        "nssta_live": "Live NSSTA/TPAC programme feed reachable (health check succeeded).",
        "nssta_error": (
            "NSSTA_API_BASE_URL is set but the health check failed -- falling back to the "
            "published training-calendar documents instead of reporting a live sync that isn't real."
        ),
        "nssta_fallback": (
            "No public NSSTA/TPAC programme API exists today. Recommendations link to "
            "the published NSSTA training-calendar documents instead."
        ),
    },
    "hi": {
        "igot_live": "लाइव iGOT कर्मयोगी API पहुंच योग्य है (हेल्थ चेक सफल रहा)।",
        "igot_error": (
            "IGOT_API_BASE_URL सेट है लेकिन हेल्थ चेक विफल रहा -- एक झूठा लाइव सिंक बताने के "
            "बजाय आधिकारिक सार्वजनिक सूची पर वापस जा रहे हैं।"
        ),
        "igot_fallback": (
            "आज कोई सार्वजनिक iGOT कर्मयोगी पार्टनर API मौजूद नहीं है। अनुशंसाएं एक काल्पनिक "
            "नामांकन रिकॉर्ड के बजाय आधिकारिक सार्वजनिक सूची से जुड़ी हैं।"
        ),
        "nssta_live": "लाइव NSSTA/TPAC कार्यक्रम फ़ीड पहुंच योग्य है (हेल्थ चेक सफल रहा)।",
        "nssta_error": (
            "NSSTA_API_BASE_URL सेट है लेकिन हेल्थ चेक विफल रहा -- एक झूठा लाइव सिंक बताने के "
            "बजाय प्रकाशित प्रशिक्षण-कैलेंडर दस्तावेज़ों पर वापस जा रहे हैं।"
        ),
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


def _provider_status(env_var: str, detail: dict, live_key: str, error_key: str, fallback_key: str) -> dict:
    base_url = os.getenv(env_var)
    if not base_url:
        return {"mode": "CATALOGUE", "detail": detail[fallback_key]}
    result = LiveHTTPProviderAdapter(base_url).health_check()
    if result.status == "LIVE":
        return {"mode": "LIVE", "detail": detail[live_key]}
    return {"mode": "CATALOGUE", "detail": detail[error_key]}


def integration_status(lang: str = "en") -> dict:
    """Report each provider's real status -- never `LIVE` from an env var's
    mere presence (docs/contracts/provider-adapter.md's own rule). Setting
    `IGOT_API_BASE_URL`/`NSSTA_API_BASE_URL` selects a real
    `LiveHTTPProviderAdapter` and this function reports whatever its
    `health_check()` actually returns; unset (today's default -- no approved
    endpoint contract exists yet) reports `CATALOGUE`, same as a configured
    but unreachable URL."""
    detail = _DETAIL.get(lang, _DETAIL["en"])
    return {
        "igot": _provider_status("IGOT_API_BASE_URL", detail, "igot_live", "igot_error", "igot_fallback"),
        "nssta": _provider_status("NSSTA_API_BASE_URL", detail, "nssta_live", "nssta_error", "nssta_fallback"),
    }


# SimulatedIGOTAdapter is exercised directly by tests/test_api_integration_lane5.py's
# contract tests (search_catalogue/get_course/request_enrolment/import_completions/
# health_check/reconcile all report status="SIMULATED"). Re-exported here so a
# caller that already imports this module for IGOT/NSSTA status doesn't need a
# second import path just to construct one for a demo-mode code path.
__all__ = [
    "IGOT_CATALOG_URL",
    "NSSTA_CATALOG_URL",
    "IGOT_CONFIGURED",
    "NSSTA_CONFIGURED",
    "SimulatedIGOTAdapter",
    "integration_status",
    "recommend_courses",
]


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
