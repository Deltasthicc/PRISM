"""Deterministic, explainable competency-gap and pathway calculation."""

from services.behavioral_anchors import DEFAULT_SOURCE, DEFAULT_STATUS, get_anchor
from services.curricula import get_curriculum
from services.learning_catalog import recommend_courses
from services.role_targets import FRAMEWORK_VERSION, experience_cap, resolve_role_target

# Versions the 65/35 blend itself (CLAUDE.md architectural invariant #4: "the
# 65/35 blend ... remain versioned prototype policies until validated").
# Distinct from role_targets.FRAMEWORK_VERSION, which versions target
# selection -- these are two independently-changeable policies.
ASSESSMENT_POLICY_VERSION = "prototype-v1"

# The one documented status term that applies to a Lane 3 competency result
# (CODEX.md architectural invariants: use SIMULATED, CATALOGUE, LIVE,
# PROVISIONAL and NO EVIDENCE "precisely"; SIH26101_TEAM_ORCHESTRATION.md
# section 5 has Lane 1 render exactly these). The vocabulary defines no
# positive counterpart, so evidence_state is this string or None -- the
# present case is described by evidence_sources instead of an invented term.
NO_EVIDENCE = "NO EVIDENCE"

# Evidence types this engine understands, in Lane 2's storage vocabulary
# (models/governance.py's EVIDENCE_TYPES). Ordered strongest-corroboration
# first purely for stable display; the order is NOT a weighting.
EVIDENCE_TYPE_ORDER = (
    "reviewer",
    "diagnostic",
    "observed_practice",
    "provider_imported",
    "self_report",
)

# Only these two contribute to observed_level, at the 65/35 weights this
# policy version has always used. SIH26101_TEAM_ORCHESTRATION.md section 5
# asks Lane 3 to *separate* the five evidence types -- not to blend them --
# and no validated weights exist for the other three, so they are recorded,
# separated and displayed while deliberately not moving the score. Giving
# them invented weights would be exactly the fabricated psychometric
# precision CLAUDE.md invariant #4 forbids, and would require a contract
# version bump plus approval under competency-evidence.md section 10.
SCORING_EVIDENCE_TYPES = ("observed_practice", "self_report")

# Types recorded for transparency but not yet scored. Weighting them needs
# domain-reviewer-validated weights, which SIH26101_MASTER_CHECKLIST.md
# section 4.1 marks BLOCKED-EXTERNAL.
UNSCORED_EVIDENCE_TYPES = ("reviewer", "diagnostic", "provider_imported")

# Qualitative uncertainty band -- SIH26101_MASTER_CHECKLIST.md section 4.1:
# "Display evidence coverage and uncertainty." Deliberately qualitative: a
# numeric confidence interval would imply psychometric validation this policy
# does not have (CLAUDE.md invariant #4). "high" is intentionally unreachable
# until a validated instrument exists -- do not add it without one.
def _confidence(evidence_sources: list[str]) -> str:
    if not evidence_sources:
        return "none"
    if set(evidence_sources) == {"self_report"}:
        return "low"
    return "moderate"


# Bounded, hand-translated template strings for this engine's own generated
# prose (never AI output -- these are plain Python f-strings). Curriculum
# label/description translation lives in services/curricula.py's
# curricula_hi.json instead, since it's a different, much larger dataset with
# its own review process.
_LEVEL_LABEL = {
    "en": {
        "not_yet_evidenced": "not yet evidenced",
        "foundation": "foundation",
        "working_knowledge": "working knowledge",
        "practitioner": "practitioner",
        "advanced": "advanced",
        "expert": "expert",
    },
    "hi": {
        "not_yet_evidenced": "अभी तक कोई प्रमाण नहीं",
        "foundation": "आधारभूत",
        "working_knowledge": "कार्यसाधक ज्ञान",
        "practitioner": "अभ्यासी",
        "advanced": "उन्नत",
        "expert": "विशेषज्ञ",
    },
}

_EVIDENCE_TYPE_LABEL = {
    "en": {
        "reviewer": "reviewer",
        "diagnostic": "diagnostic",
        "observed_practice": "observed practice",
        "provider_imported": "provider-imported",
        "self_report": "self-report",
    },
    "hi": {
        "reviewer": "समीक्षक",
        "diagnostic": "निदान",
        "observed_practice": "देखा गया अभ्यास",
        "provider_imported": "प्रदाता-आयातित",
        "self_report": "स्व-रिपोर्ट",
    },
}

_EVIDENCE_SENTENCE = {
    "en": {
        "both": "65% demonstrated performance + 35% self-assessment",
        "measured_only": "demonstrated performance",
        "self_only": "self-assessment only; diagnostic evidence still required",
        "unscored": "{types} evidence recorded but not scored under policy {version}; no rated evidence yet",
        "none": "no evidence yet",
    },
    "hi": {
        "both": "65% प्रदर्शित प्रदर्शन + 35% स्व-मूल्यांकन",
        "measured_only": "प्रदर्शित प्रदर्शन",
        "self_only": "केवल स्व-मूल्यांकन; अभी भी निदान प्रमाण आवश्यक है",
        "unscored": "{types} प्रमाण दर्ज है लेकिन नीति {version} के तहत स्कोर नहीं किया गया; अभी कोई रेटेड प्रमाण नहीं",
        "none": "अभी तक कोई प्रमाण नहीं",
    },
}

_RECOMMENDED_ACTION = {
    "en": {
        "unassessed": "Complete a diagnostic to establish a baseline -- no evidence recorded yet",
        "foundation": "Complete a diagnostic and foundation module",
        "targeted": "Complete targeted learning, then re-assess with applied questions",
    },
    "hi": {
        "unassessed": "आधाररेखा स्थापित करने के लिए एक निदान पूरा करें -- अभी तक कोई प्रमाण दर्ज नहीं है",
        "foundation": "एक निदान और आधारभूत मॉड्यूल पूरा करें",
        "targeted": "लक्षित शिक्षण पूरा करें, फिर लागू प्रश्नों के साथ पुनः मूल्यांकन करें",
    },
}

_METHOD_NOTE = {
    "en": "Self-ratings never override demonstrated performance; missing evidence is surfaced explicitly.",
    "hi": "स्व-रेटिंग कभी भी प्रदर्शित प्रदर्शन को अधिलेखित नहीं करती; अनुपस्थित प्रमाण को स्पष्ट रूप से दिखाया जाता है।",
}


def _level_label(score: float, lang: str = "en") -> str:
    labels = _LEVEL_LABEL.get(lang, _LEVEL_LABEL["en"])
    if score < 1.0:
        return labels["not_yet_evidenced"]
    if score < 2.0:
        return labels["foundation"]
    if score < 3.0:
        return labels["working_knowledge"]
    if score < 4.0:
        return labels["practitioner"]
    if score < 4.75:
        return labels["advanced"]
    return labels["expert"]


def analyse_competencies(
    curriculum_slug: str,
    self_ratings: dict[str, float],
    measured_scores: dict[str, float],
    experience_level: str = "beginner",
    job_role: str = "",
    designation: str = "",
    current_assignment: str = "",
    department: str = "",
    evidence: dict[str, dict[str, dict]] | None = None,
    role_targets: dict[str, dict] | None = None,
    lang: str = "en",
) -> dict:
    """Compute an explainable competency gap and ordered pathway.

    `evidence` is the optional separated-evidence map from
    services/evidence_resolver.py -- `{competency_id: {evidence_type: {value,
    recorded_at, detail}}}` in Lane 2's storage vocabulary. When a competency
    carries `self_report` or `observed_practice` there, those authoritative
    rows take precedence over the legacy `self_ratings`/`measured_scores`
    arguments for that competency. The other three types are recorded and
    reported per SCORING_EVIDENCE_TYPES' note, but never move the score.

    This function stays pure: no database, no HTTP, no clock. That is what
    lets the golden fixtures pin its output exactly.
    """
    curriculum = get_curriculum(curriculum_slug, lang)
    if not curriculum:
        raise ValueError(f"Unknown curriculum: {curriculum_slug}")

    evidence_sentences = _EVIDENCE_SENTENCE.get(lang, _EVIDENCE_SENTENCE["en"])
    evidence_type_labels = _EVIDENCE_TYPE_LABEL.get(lang, _EVIDENCE_TYPE_LABEL["en"])

    allowed = {item["id"] for item in curriculum["competencies"]}
    unknown = sorted(set(self_ratings) - allowed)
    if unknown:
        raise ValueError(f"Ratings contain competencies outside this curriculum: {', '.join(unknown)}")

    # Bound to its own name: `evidence` is reused below as the per-competency
    # explanation string, and rebinding the parameter would corrupt it on the
    # next loop iteration.
    evidence_map = evidence or {}
    unknown_evidence = sorted(set(evidence_map) - allowed)
    if unknown_evidence:
        raise ValueError(
            f"Evidence contains competencies outside this curriculum: {', '.join(unknown_evidence)}"
        )

    target_cap = experience_cap(experience_level)
    competency_results = []
    for item in curriculum["competencies"]:
        competency_id = item["id"]
        recorded = evidence_map.get(competency_id, {})

        # A stored EvidenceRecord outranks the legacy argument for the same
        # type: it is the auditable row, the argument is a loose input.
        # `value=None` (Lane 2 allows qualitative reviewer notes) counts as
        # present-but-unscored, never as zero.
        self_score = self_ratings.get(competency_id)
        if "self_report" in recorded and recorded["self_report"].get("value") is not None:
            self_score = float(recorded["self_report"]["value"])
        measured = measured_scores.get(competency_id)
        if "observed_practice" in recorded and recorded["observed_practice"].get("value") is not None:
            measured = float(recorded["observed_practice"]["value"])

        # evidence_sources uses Lane 2's EVIDENCE_TYPES vocabulary
        # (backend/models/governance.py) so nothing needs relabeling as more
        # evidence moves into EvidenceRecord rows.
        present = set(recorded)
        if measured is not None:
            present.add("observed_practice")
        if self_score is not None:
            present.add("self_report")
        evidence_sources = [t for t in EVIDENCE_TYPE_ORDER if t in present]

        # Each type kept separate and individually inspectable -- the literal
        # "separate ... evidence" deliverable, rather than a single collapsed
        # number a reviewer cannot take apart.
        evidence_records = [
            {
                "evidence_type": evidence_type,
                "value": recorded[evidence_type].get("value"),
                "recorded_at": recorded[evidence_type].get("recorded_at"),
                "detail": recorded[evidence_type].get("detail", ""),
                "scored": evidence_type in SCORING_EVIDENCE_TYPES,
            }
            for evidence_type in EVIDENCE_TYPE_ORDER
            if evidence_type in recorded
        ]
        unscored_present = [t for t in UNSCORED_EVIDENCE_TYPES if t in present]

        if measured is not None and self_score is not None:
            observed = measured * 0.65 + self_score * 0.35
            evidence = evidence_sentences["both"]
        elif measured is not None:
            observed = measured
            evidence = evidence_sentences["measured_only"]
        elif self_score is not None:
            observed = self_score
            evidence = evidence_sentences["self_only"]
        elif unscored_present:
            # Evidence exists, but none of it is scored under this policy
            # version -- so there is still no defensible number. Say that,
            # rather than letting 0.0 read as a measured floor.
            observed = 0.0
            evidence = evidence_sentences["unscored"].format(
                types=", ".join(evidence_type_labels.get(t, t) for t in unscored_present),
                version=ASSESSMENT_POLICY_VERSION,
            )
        else:
            observed = 0.0
            evidence = evidence_sentences["none"]

        # A resolved map (from services/role_target_resolver.py, backed by
        # Lane 2's role_targets table) is authoritative and complete when
        # supplied; otherwise fall back to the in-memory demonstration set.
        # Both produce the identical record shape.
        if role_targets is not None and competency_id in role_targets:
            role_target_info = role_targets[competency_id]
        else:
            role_target_info = resolve_role_target(
                competency_id,
                item.get("target_level", 3),
                job_role,
                designation,
                current_assignment,
                department,
            )
        role_target = role_target_info["target_level"]
        pathway_target = min(role_target, float(target_cap))
        gap = max(0.0, pathway_target - observed)
        has_evidence = bool(evidence_sources)
        # Only *scored* evidence yields a defensible observed_level. A learner
        # carrying just a qualitative reviewer note has evidence but no rating,
        # so the gap-derived tiers below would turn a 0.0 placeholder into
        # "critical" -- the exact unsupported low-ability judgment CLAUDE.md
        # architectural invariant #3 forbids.
        has_scored_evidence = measured is not None or self_score is not None
        if not has_scored_evidence:
            # The gap number itself is unchanged and still drives sort order.
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
                "observed_label": _level_label(observed, lang),
                "observed_anchor": get_anchor(competency_id, observed),
                "target_anchor": get_anchor(competency_id, pathway_target),
                "pathway_target": pathway_target,
                "role_target": role_target,
                "role_target_source": role_target_info["source"],
                "role_target_assurance": role_target_info["assurance"],
                "matched_role": role_target_info["matched_role"],
                "matched_field": role_target_info["matched_field"],
                "gap": round(gap, 2),
                "priority": priority,
                "has_evidence": has_evidence,
                "has_scored_evidence": has_scored_evidence,
                "evidence_sources": evidence_sources,
                "evidence_records": evidence_records,
                # NO EVIDENCE is reserved for genuinely nothing on file. A
                # recorded-but-unscored type is evidence, so it does not carry
                # that label -- has_scored_evidence is what says the level is
                # not yet derivable.
                "evidence_state": None if has_evidence else NO_EVIDENCE,
                "confidence": _confidence(evidence_sources),
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
                        _RECOMMENDED_ACTION.get(lang, _RECOMMENDED_ACTION["en"])["unassessed"]
                        if item["priority"] == "unassessed"
                        else _RECOMMENDED_ACTION.get(lang, _RECOMMENDED_ACTION["en"])["foundation"]
                        if item["observed_level"] < 1
                        else _RECOMMENDED_ACTION.get(lang, _RECOMMENDED_ACTION["en"])["targeted"]
                    ),
                }
            )
            pending.pop(item["competency_id"], None)

    courses = recommend_courses(skill_gaps, lang)
    return {
        "curriculum_slug": curriculum_slug,
        "curriculum_name": curriculum["name"],
        "domain": curriculum["domain"],
        "experience_level": experience_level,
        "job_role": job_role,
        "designation": designation,
        "current_assignment": current_assignment,
        "department": department,
        "method": {
            "scale": "0-5 proficiency",
            "demonstrated_weight": 0.65,
            "self_assessment_weight": 0.35,
            "note": _METHOD_NOTE.get(lang, _METHOD_NOTE["en"]),
            "policy_version": ASSESSMENT_POLICY_VERSION,
            "scored_evidence_types": list(SCORING_EVIDENCE_TYPES),
            "recorded_unscored_evidence_types": list(UNSCORED_EVIDENCE_TYPES),
            "unscored_note": (
                "Reviewer, diagnostic and provider-imported evidence is recorded and shown "
                "separately but does not move observed_level: no domain-reviewer-validated "
                "weights exist for it yet."
            ),
            "role_target_framework_version": FRAMEWORK_VERSION,
            # Per-anchor source/status live inside each observed_anchor/
            # target_anchor record; these two are just the module-wide
            # starting defaults, for a consumer that wants one summary value
            # without inspecting every anchor individually.
            "behavioral_anchor_default_source": DEFAULT_SOURCE,
            "behavioral_anchor_default_status": DEFAULT_STATUS,
        },
        "competencies": competency_results,
        "skill_gaps": skill_gaps,
        "pathway": pathway,
        "courses": courses,
    }
