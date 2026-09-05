"""Regenerates backend/tests/fixtures/golden_pathways/*.json.

Golden fixtures pin `learning_engine.analyse_competencies()`'s output for a
fixed set of inputs, so `test_competency_golden_fixtures.py` catches any
unintended drift -- SIH26101_TEAM_ORCHESTRATION.md section 5, Lane 3
acceptance evidence: "Golden policy fixtures produce stable gaps and
pathways."

This is a manual tool, never imported by the test suite and never run by CI.
Regenerating a fixture is a deliberate act tied to a reviewed, intentional
policy change (a new blend weight, a new priority threshold, new anchor
text) -- not something that should happen silently. Run it, then read the
diff (`git diff backend/tests/fixtures/`) before committing; a diff you
cannot explain from a real code change means something drifted by accident,
not on purpose.

Usage:
    cd backend
    .venv/Scripts/python.exe tests/fixtures/generate_golden_fixtures.py

`courses` is deliberately excluded from what gets pinned: it comes from
Lane 5's services/learning_catalog.py (an env-var-dependent, cross-lane
concern), not from anything this lane owns or can promise stable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.learning_engine import analyse_competencies

FIXTURES_DIR = Path(__file__).parent / "golden_pathways"

# Each scenario is chosen to pin one specific, doc-required behavior --- not
# just "whatever the code currently does". See the paired comment for what
# each one proves and docs/contracts/competency-evidence.md for the fields.
SCENARIOS = {
    "no_evidence_beginner": {
        "description": (
            "Zero self-ratings, zero measured scores, no role signal. Proves "
            "the unassessed tier, the NO EVIDENCE state, and that pathway "
            "ordering is stable from gap + curriculum order alone when every "
            "competency ties on evidence (CLAUDE.md invariant 3)."
        ),
        "input": {
            "curriculum_slug": "official-statistics",
            "self_ratings": {},
            "measured_scores": {},
            "experience_level": "beginner",
        },
    },
    "self_report_only_advanced": {
        "description": (
            "Self-ratings only, advanced experience, no measured evidence. "
            "Proves confidence='low' for self-report-only coverage and the "
            "experience cap (5) versus role/curriculum target interaction."
        ),
        "input": {
            "curriculum_slug": "official-statistics",
            "self_ratings": {
                "os_statistical_foundations": 3.0,
                "os_data_quality": 1.5,
            },
            "measured_scores": {},
            "experience_level": "advanced",
        },
    },
    "blended_with_role_target_override": {
        "description": (
            "Both evidence types present (65/35 blend) plus a job_role that "
            "overrides the curriculum-default target. Proves the blend "
            "formula, role_target_source='internal-prototype', and "
            "matched_field='job_role' together, deterministically."
        ),
        "input": {
            "curriculum_slug": "official-statistics",
            "self_ratings": {"os_official_statistics": 4.0},
            "measured_scores": {"os_official_statistics": 2.0},
            "experience_level": "expert",
            "job_role": "Statistical Officer",
        },
    },
    "department_and_assignment_targeting": {
        "description": (
            "No job_role/designation -- only current_assignment and "
            "department are set. Proves RESOLUTION_ORDER's two lower-"
            "precedence fields actually select a target on their own."
        ),
        "input": {
            "curriculum_slug": "official-statistics",
            "self_ratings": {},
            "measured_scores": {},
            "experience_level": "intermediate",
            "current_assignment": "Household Survey Round",
            "department": "Statistics Division",
        },
    },
    "mixed_coverage_multi_step_pathway": {
        "description": (
            "A realistic mix -- some competencies assessed, some not, across "
            "several prerequisite chains. Proves the pathway stays "
            "prerequisite-first and stable with a real multi-step ordering, "
            "not just in a degenerate all-or-nothing case."
        ),
        "input": {
            "curriculum_slug": "official-statistics",
            "self_ratings": {
                "os_statistical_foundations": 4.0,
                "os_data_collection": 2.0,
                "os_visualization": 1.0,
            },
            "measured_scores": {
                "os_statistical_foundations": 3.5,
                "os_sampling_design": 1.0,
            },
            "experience_level": "advanced",
            "designation": "Data Analyst",
        },
    },
    "ps02_breadth_competency_unanchored": {
        "description": (
            "Targets a PS-02 breadth competency (added for full named-scope "
            "coverage) that has no behavioral anchor yet. Proves anchor "
            "null-handling and per-competency provenance stay stable "
            "independent of anchor coverage."
        ),
        "input": {
            "curriculum_slug": "official-statistics",
            "self_ratings": {"os_price_statistics": 2.5},
            "measured_scores": {},
            "experience_level": "intermediate",
        },
    },
}


def generate() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    for name, scenario in SCENARIOS.items():
        result = analyse_competencies(**scenario["input"])
        result.pop("courses", None)  # Lane 5's concern; see module docstring.

        fixture = {
            "description": scenario["description"],
            "input": scenario["input"],
            "expected": result,
        }
        path = FIXTURES_DIR / f"{name}.json"
        path.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(FIXTURES_DIR.parents[2])}")


if __name__ == "__main__":
    generate()
