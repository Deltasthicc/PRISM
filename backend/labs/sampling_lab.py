"""Bounded sampling-design lab for the Official Statistics domain (PS-08).

Why sampling and not CPI or data quality: SIH26101_TEAM_ORCHESTRATION.md
section 5 allows any of the three, and services/behavioral_anchors.py already
defines os_sampling_design's Level 2 anchor as "Can calculate a simple random
sample size for a given confidence level and margin of error." This lab tests
exactly that behavior, so a passed task is evidence against a competency that
already exists in the taxonomy, with a target, anchors and a pathway position
-- which is what closes SIH26101_WINNING_PLAYBOOK.md section 1's
target -> evidence -> gap -> practice -> reassessment loop.

Safety posture (SIH26101_MASTER_CHECKLIST.md section 4.4,
SIH26101_TEAM_ORCHESTRATION.md section 5 Lane 3 acceptance evidence):

- No learner code is accepted or executed. The learner submits one number per
  task; the expected value is recomputed here from a fixed formula.
- The task set is a module-level constant. A learner cannot define a task,
  supply a formula, or change a scenario's parameters.
- Every submitted value passes through _bounded_number(), which rejects NaN,
  infinity and anything outside a task's declared range before arithmetic
  runs. There is no unbounded loop or learner-controlled allocation anywhere
  in this module.

This module computes and explains only. It never writes to the database --
persisting an attempt is Lane 2/5 territory; evidence_payload() just returns
the row shape Lane 2's EvidenceRecord expects.
"""
from __future__ import annotations

import math

LAB_ID = "sampling-design-lab"
LAB_VERSION = "prototype-v1"
COMPETENCY_ID = "os_sampling_design"

# The sample-size formulas below are standard statistics, but "passing this
# task demonstrates level N" is a team judgment, not a validated mapping --
# so the level claim carries the documented assurance label (CODEX.md
# architectural invariants; SIH26101_MASTER_CHECKLIST.md section 3.3).
LEVEL_CLAIM_ASSURANCE = "PROVISIONAL"

# Two-sided z scores for the confidence levels this lab offers. A learner
# cannot introduce a new confidence level -- tasks reference these keys only.
Z_SCORES = {90: 1.645, 95: 1.96, 99: 2.576}

# Absolute bound on any submitted answer. Sample sizes and allocations are
# counts of people/units; nothing legitimate approaches this, and it keeps a
# hostile submission from reaching the arithmetic below at all.
MAX_ANSWER = 10_000_000


class LabInputError(ValueError):
    """Raised when a submission is malformed, out of range, or for an unknown
    task. Routes should surface this as a 422, never a 500."""


TASKS: dict[str, dict] = {
    "srs-basic": {
        "task_id": "srs-basic",
        "title": "Simple random sample size",
        "demonstrated_level": 2,
        "kind": "sample_size_simple",
        "prompt": (
            "A district statistical office needs to estimate the proportion of households "
            "with internet access. Assume the most conservative population proportion "
            "(p = 0.5), and require 95% confidence with a margin of error of +/- 5 "
            "percentage points. The population is large enough that no finite population "
            "correction is needed. What is the minimum sample size?"
        ),
        "parameters": {"confidence": 95, "margin_of_error": 0.05, "proportion": 0.5},
        "answer_label": "Minimum number of households to sample",
        "tolerance": 1.0,
    },
    "srs-finite-population": {
        "task_id": "srs-finite-population",
        "title": "Sample size with finite population correction",
        "demonstrated_level": 3,
        "kind": "sample_size_fpc",
        "prompt": (
            "The same survey is now run in a district with only 50,000 households in the "
            "sampling frame. Keep 95% confidence, a +/- 5 percentage point margin of error "
            "and p = 0.5, but apply the finite population correction. What is the minimum "
            "sample size now?"
        ),
        "parameters": {
            "confidence": 95,
            "margin_of_error": 0.05,
            "proportion": 0.5,
            "population": 50_000,
        },
        "answer_label": "Minimum number of households to sample",
        "tolerance": 1.0,
    },
    "proportional-allocation": {
        "task_id": "proportional-allocation",
        "title": "Proportional allocation across strata",
        "demonstrated_level": 3,
        "kind": "proportional_allocation",
        "prompt": (
            "A state survey stratifies 100,000 households into Rural (45,000), "
            "Urban (30,000) and Peri-urban (25,000). A total sample of 1,200 households "
            "is allocated proportionally to stratum size. How many households are "
            "allocated to the Rural stratum?"
        ),
        "parameters": {
            "total_sample": 1_200,
            "strata": [
                {"name": "Rural", "size": 45_000},
                {"name": "Urban", "size": 30_000},
                {"name": "Peri-urban", "size": 25_000},
            ],
            "target_stratum": "Rural",
        },
        "answer_label": "Households allocated to the Rural stratum",
        "tolerance": 1.0,
    },
}


def _bounded_number(value: object, *, field: str) -> float:
    """Reject anything that is not a finite, in-range number before it reaches
    the arithmetic below."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LabInputError(f"{field} must be a number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise LabInputError(f"{field} must be a finite number")
    if numeric < 0 or numeric > MAX_ANSWER:
        raise LabInputError(f"{field} must be between 0 and {MAX_ANSWER}")
    return numeric


def _simple_sample_size(confidence: int, margin_of_error: float, proportion: float) -> tuple[float, list[dict]]:
    z = Z_SCORES[confidence]
    numerator = (z**2) * proportion * (1 - proportion)
    raw = numerator / (margin_of_error**2)
    steps = [
        {
            "label": "Choose the z score",
            "detail": f"{confidence}% confidence corresponds to a two-sided z of {z}.",
        },
        {
            "label": "Apply n0 = z^2 * p * (1 - p) / e^2",
            "detail": (
                f"({z}^2 x {proportion} x {1 - proportion}) / {margin_of_error}^2 "
                f"= {numerator:.4f} / {margin_of_error**2:.4f} = {raw:.2f}"
            ),
        },
        {
            "label": "Round up to a whole respondent",
            "detail": f"A partial household cannot be sampled, so n0 = {raw:.2f} rounds up to {math.ceil(raw)}.",
        },
    ]
    return raw, steps


def _finite_population_sample_size(
    confidence: int, margin_of_error: float, proportion: float, population: int
) -> tuple[float, list[dict]]:
    raw, steps = _simple_sample_size(confidence, margin_of_error, proportion)
    corrected = raw / (1 + (raw - 1) / population)
    steps.append(
        {
            "label": "Apply the finite population correction n = n0 / (1 + (n0 - 1) / N)",
            "detail": (
                f"{raw:.2f} / (1 + ({raw:.2f} - 1) / {population:,}) = {corrected:.2f}, "
                f"which rounds up to {math.ceil(corrected)}. The correction matters because "
                "sampling a meaningful share of a finite frame reduces the variance."
            ),
        }
    )
    return corrected, steps


def _proportional_allocation(
    total_sample: int, strata: list[dict], target_stratum: str
) -> tuple[float, list[dict]]:
    population = sum(stratum["size"] for stratum in strata)
    target = next(stratum for stratum in strata if stratum["name"] == target_stratum)
    share = target["size"] / population
    allocation = total_sample * share
    steps = [
        {
            "label": "Total the strata",
            "detail": " + ".join(f"{s['name']} {s['size']:,}" for s in strata) + f" = {population:,}",
        },
        {
            "label": f"Find the {target_stratum} share",
            "detail": f"{target['size']:,} / {population:,} = {share:.4f}",
        },
        {
            "label": "Allocate proportionally",
            "detail": f"{total_sample:,} x {share:.4f} = {allocation:.2f}",
        },
    ]
    return allocation, steps


def list_tasks() -> list[dict]:
    """Public task list -- prompts and parameters only, never expected answers."""
    return [
        {
            "task_id": task["task_id"],
            "title": task["title"],
            "prompt": task["prompt"],
            "answer_label": task["answer_label"],
            "demonstrated_level": task["demonstrated_level"],
            "level_claim_assurance": LEVEL_CLAIM_ASSURANCE,
            "competency_id": COMPETENCY_ID,
        }
        for task in TASKS.values()
    ]


def expected_answer(task_id: str) -> tuple[float, list[dict]]:
    """Recompute a task's expected answer and its worked steps. Deterministic:
    the same task_id always produces the same number and the same explanation."""
    task = TASKS.get(task_id)
    if not task:
        raise LabInputError(f"Unknown lab task: {task_id}")

    parameters = task["parameters"]
    if task["kind"] == "sample_size_simple":
        raw, steps = _simple_sample_size(
            parameters["confidence"], parameters["margin_of_error"], parameters["proportion"]
        )
    elif task["kind"] == "sample_size_fpc":
        raw, steps = _finite_population_sample_size(
            parameters["confidence"],
            parameters["margin_of_error"],
            parameters["proportion"],
            parameters["population"],
        )
    else:
        raw, steps = _proportional_allocation(
            parameters["total_sample"], parameters["strata"], parameters["target_stratum"]
        )
    return float(math.ceil(raw)), steps


def evidence_payload(task_id: str) -> dict:
    """The EvidenceRecord-shaped row a passed attempt justifies
    (backend/models/governance.py, Lane 2). Returned for a caller to persist;
    this module never writes it itself."""
    task = TASKS[task_id]
    return {
        "competency_id": COMPETENCY_ID,
        "evidence_type": "observed_practice",
        "value": task["demonstrated_level"],
        "detail": f"{LAB_ID}:{task_id}",
    }


def evaluate_submission(task_id: str, submitted_answer: object) -> dict:
    """Grade one submitted answer and always return the worked explanation.

    The steps are returned whether the learner was right or wrong: the point
    of a lab is the learning feedback, not the verdict
    (SIH26101_TEAM_ORCHESTRATION.md section 5: "The lab has resource bounds,
    learning feedback and no arbitrary code execution on the API host").
    """
    task = TASKS.get(task_id)
    if not task:
        raise LabInputError(f"Unknown lab task: {task_id}")

    submitted = _bounded_number(submitted_answer, field="submitted_answer")
    expected, steps = expected_answer(task_id)
    tolerance = task["tolerance"]
    correct = abs(submitted - expected) <= tolerance

    if correct:
        feedback = (
            f"Correct. {expected:.0f} is the minimum that satisfies the stated precision; "
            "a smaller sample widens the confidence interval beyond the required margin."
        )
    elif submitted < expected:
        feedback = (
            f"Too small. {submitted:.0f} would not hold the stated margin of error -- "
            f"the required minimum is {expected:.0f}. Check the steps below."
        )
    else:
        feedback = (
            f"Larger than required. {submitted:.0f} is defensible but spends field budget "
            f"for no extra precision; {expected:.0f} already meets the requirement."
        )

    return {
        "lab_id": LAB_ID,
        "lab_version": LAB_VERSION,
        "task_id": task_id,
        "competency_id": COMPETENCY_ID,
        "submitted": submitted,
        "expected": expected,
        "tolerance": tolerance,
        "correct": correct,
        "demonstrated_level": task["demonstrated_level"] if correct else None,
        "level_claim_assurance": LEVEL_CLAIM_ASSURANCE,
        "steps": steps,
        "feedback": feedback,
        # Evidence only exists when the learner actually demonstrated the
        # behavior -- a failed attempt is never recorded as a low ability
        # judgment (CLAUDE.md architectural invariant #3).
        "evidence": evidence_payload(task_id) if correct else None,
    }
