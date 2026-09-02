"""L1-L5 behavioral anchors for the Official Statistics & Data Governance
curriculum (services/curricula.py's "official-statistics" domain) -- the
canonical demo domain per SIH26101_MASTER_CHECKLIST.md section 3.3.

Sourcing status, stated plainly: no public MoSPI/CBC document publishes
ready-made behavioral-anchor text at this granularity for these specific
competencies, so nothing below is copied or paraphrased from one. What IS
grounded in a real, cited source is the *structure* -- describing each level
as an observable activity a person can or cannot yet do, in the
role-activity-competency-level pattern that the publicly documented
FRAC / Karmayogi Competency Model actually uses (see
SIH26101_MASTER_CHECKLIST.md section 7 for the primary citations). The
specific wording of every anchor below is team-authored and unreviewed.

Every anchor is a per-item record -- {descriptor, source, status,
reviewed_by, version} -- not a single blanket note for the whole file. This
follows SIH26101_TEAM_ORCHESTRATION.md section 5's Lane 3 acceptance
evidence verbatim: "Every competency/target has source, authoring status and
version," and mirrors the per-record shape (source, approved_by,
framework_version) SIH26101_MASTER_CHECKLIST.md section 4.1 specifies for
role targets. The practical reason this matters: a real domain reviewer will
approve individual anchors one at a time, not all 45 at once, so the data
model has to support that from day one rather than needing a breaking change
later. DEFAULT_SOURCE/DEFAULT_STATUS below are starting values, not a claim
that review happens at file granularity -- SIH26101_MASTER_CHECKLIST.md
section 4.1 marks real MoSPI/NSSTA/CBC validation BLOCKED-EXTERNAL; no lane
or coding agent may upgrade any anchor's status, only a named domain
reviewer signing off on that specific anchor (CLAUDE.md "Ask versus act").
"""
from __future__ import annotations

from services.curricula import CURRICULA

DEFAULT_SOURCE = "internal-prototype"
DEFAULT_STATUS = "unreviewed-pending-domain-expert"

# The fixed assurance vocabulary (CODEX.md / CLAUDE.md: use SIMULATED,
# CATALOGUE, LIVE, PROVISIONAL and NO EVIDENCE "precisely"). DEFAULT_STATUS
# above is the human-readable review state; `assurance` is the machine value
# Lane 1 renders as a badge, and it must come from that vocabulary.
PROVISIONAL = "PROVISIONAL"

# Curriculum slugs this module currently covers. Every other curriculum
# (dsa-fundamentals, public-policy, digital-literacy) has no anchors yet --
# get_anchor() returns None for those rather than guessing.
ANCHOR_COVERAGE = ["official-statistics"]


def _anchor(
    descriptor: str,
    *,
    source: str = DEFAULT_SOURCE,
    status: str = DEFAULT_STATUS,
    assurance: str = PROVISIONAL,
    reviewed_by: str | None = None,
    version: int = 1,
) -> dict:
    """Build one per-level anchor record. A future reviewer upgrades exactly
    one of these -- e.g. `_anchor("...", status="expert-reviewed",
    reviewed_by="<name>")` -- without touching any other anchor's status."""
    return {
        "descriptor": descriptor,
        "source": source,
        "status": status,
        "assurance": assurance,
        "reviewed_by": reviewed_by,
        "version": version,
    }


BEHAVIORAL_ANCHORS: dict[str, dict[int, dict]] = {
    "os_statistical_foundations": {
        1: _anchor("Can define mean, median, mode, and variance, and explain why sampling error exists."),
        2: _anchor("Can compute basic descriptive statistics correctly from a small, clean dataset."),
        3: _anchor("Can choose an appropriate descriptive or inferential method for a stated question and interpret a confidence interval correctly."),
        4: _anchor("Can identify and correct a common statistical misinterpretation (e.g. correlation vs. causation, p-value misuse) in a draft report before publication."),
        5: _anchor("Can design the statistical methodology for a new survey or study and defend it under technical review."),
    },
    "os_data_collection": {
        1: _anchor("Can list the common data collection methods (census, survey, administrative records) and name one limitation of each."),
        2: _anchor("Can administer a pre-designed data collection instrument in the field under supervision."),
        3: _anchor("Can independently plan and execute one data collection round for a defined population, including field logistics."),
        4: _anchor("Can diagnose and correct a field-level data collection problem (non-response, enumerator error, instrument bias) mid-cycle."),
        5: _anchor("Can design a new data collection instrument and protocol for a previously uncollected indicator."),
    },
    "os_sampling_design": {
        1: _anchor("Can explain what a sampling frame is and why probability sampling is used instead of a full census."),
        2: _anchor("Can calculate a simple random sample size for a given confidence level and margin of error."),
        3: _anchor("Can design a stratified or single-stage cluster sample for one survey, with supervision on weighting."),
        4: _anchor("Can design a multi-stage sample with correct weighting and non-response adjustment for a regional survey."),
        5: _anchor("Can design and defend a national-scale, multi-stage probability sampling methodology."),
    },
    "os_data_quality": {
        1: _anchor("Can name the core data quality dimensions: accuracy, completeness, timeliness, and consistency."),
        2: _anchor("Can run a basic validation check (range, format, or duplicate check) on a dataset using a defined rule set."),
        3: _anchor("Can independently design and apply a validation and cleaning workflow for one dataset before release."),
        4: _anchor("Can investigate and resolve a data quality issue that surfaced after a revision cycle, documenting the root cause."),
        5: _anchor("Can define the quality-assurance standard and metadata documentation policy for a statistical product line."),
    },
    "os_official_statistics": {
        1: _anchor("Can name the core principles governing official statistics, such as impartiality, relevance, and methodological soundness."),
        2: _anchor("Can locate and correctly cite a published official statistical product for a given indicator."),
        3: _anchor("Can prepare a statistical release -- tables, notes, and methodology summary -- for one indicator following the standard product template."),
        4: _anchor("Can reconcile a discrepancy between two official statistical products covering overlapping ground."),
        5: _anchor("Can set methodology and dissemination standards for a new official statistical product."),
    },
    "os_visualization": {
        1: _anchor("Can read a bar chart, line chart, and choropleth map and correctly state what each is showing."),
        2: _anchor("Can build a basic chart from a dataset that matches the chart type to the data type."),
        3: _anchor("Can choose an appropriate chart type for a stated audience and message, avoiding common distortions like a truncated axis or misleading scale."),
        4: _anchor("Can design a multi-panel dashboard or report that communicates a complex finding to a non-technical decision-maker."),
        5: _anchor("Can set visualization and accessibility standards for a department's public-facing statistical communication."),
    },
    "os_gis": {
        1: _anchor("Can explain what a geography boundary layer is and why geocoding matters for statistics."),
        2: _anchor("Can join a tabular dataset to a geography layer and produce a basic thematic map, with supervision."),
        3: _anchor("Can independently produce a thematic map with an appropriate classification scheme for one indicator."),
        4: _anchor("Can diagnose and fix a geographic join error, such as mismatched boundary vintages or a coordinate system mismatch, in a spatial dataset."),
        5: _anchor("Can design a spatial data governance and geography-versioning standard for a statistical program."),
    },
    "os_big_data": {
        1: _anchor("Can explain the difference between a traditional survey pipeline and a modern data pipeline, such as batch vs. streaming or structured vs. unstructured."),
        2: _anchor("Can run a pre-built data pipeline step and check its output against a known expected result."),
        3: _anchor("Can independently build a basic pipeline that ingests, cleans, and stores one new administrative data source."),
        4: _anchor("Can evaluate a big-data or cloud-based source for statistical fitness-for-use -- coverage, bias, timeliness -- before it is adopted."),
        5: _anchor("Can design the governance and architecture for integrating a new big-data source into an official statistics pipeline at scale."),
    },
    "os_ml": {
        1: _anchor("Can explain, in plain language, what a machine-learning model does and name one risk of using one in an official statistic, such as bias or opacity."),
        2: _anchor("Can run a pre-built, documented ML model on a dataset and correctly interpret its basic output metrics."),
        3: _anchor("Can independently apply a standard ML method, such as classification or imputation, to one dataset with documented validation against a known benchmark."),
        4: _anchor("Can evaluate an ML-based statistical method for bias, robustness, and explainability before it is used in an official release."),
        5: _anchor("Can set the responsible-AI adoption policy for machine-learning use in official statistics production."),
    },
}

_REQUIRED_ANCHOR_KEYS = {"descriptor", "source", "status", "assurance", "reviewed_by", "version"}


def validate_anchors() -> None:
    """Fail fast if the anchor set drifts out of sync with curricula.py, or
    if a competency is missing a level, has a malformed record, or has an
    anchor for a level outside 1-5."""
    official_statistics_ids = {
        item["id"] for item in CURRICULA["official-statistics"]["competencies"]
    }
    anchor_ids = set(BEHAVIORAL_ANCHORS)
    if anchor_ids != official_statistics_ids:
        missing = official_statistics_ids - anchor_ids
        extra = anchor_ids - official_statistics_ids
        raise ValueError(
            f"Behavioral anchors out of sync with curricula.py: missing={sorted(missing)} extra={sorted(extra)}"
        )

    for competency_id, levels in BEHAVIORAL_ANCHORS.items():
        if set(levels) != {1, 2, 3, 4, 5}:
            raise ValueError(f"{competency_id} must define anchors for exactly levels 1-5")
        for level, record in levels.items():
            if set(record) != _REQUIRED_ANCHOR_KEYS:
                raise ValueError(f"{competency_id} level {level} anchor record has the wrong shape")
            if not isinstance(record["descriptor"], str) or not record["descriptor"].strip():
                raise ValueError(f"{competency_id} level {level} has an empty descriptor")
            if not record["source"] or not record["status"]:
                raise ValueError(f"{competency_id} level {level} is missing source or status")
            if not isinstance(record["version"], int) or record["version"] < 1:
                raise ValueError(f"{competency_id} level {level} must have a version >= 1")


def get_anchor(competency_id: str, level: float) -> dict | None:
    """Return a copy of the anchor record nearest to `level` (round-half-up,
    clamped to 1-5) -- {descriptor, source, status, reviewed_by, version} --
    or None if this competency has no anchors yet (any curriculum outside
    ANCHOR_COVERAGE) or `level` rounds below 1 (no evidence yet -- there is
    nothing observed to describe). Returns a copy so a caller mutating the
    result can never corrupt the canonical record."""
    levels = BEHAVIORAL_ANCHORS.get(competency_id)
    if not levels:
        return None
    level_int = int(level + 0.5)
    if level_int < 1:
        return None
    return dict(levels[min(level_int, 5)])


validate_anchors()
