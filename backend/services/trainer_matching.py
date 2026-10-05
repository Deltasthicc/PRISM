"""Trainer-to-subject matching (SIH26075 PS75-14): which trainers are suitable
to teach a competency.

This is the reverse direction of the learner gap engine: instead of "how far
is this learner from the target", it asks "what stored evidence do we hold
that this trainer can teach this competency". It is deterministic, uses no
AI/LLM, and every number in a result is reproducible from the stored facts
gathered by `gather_facts()` plus the constants in this module.

Honesty rules (CLAUDE.md invariants 3 and 6):

* A declared expertise row is the trainer's own, UNVERIFIED claim. It earns at
  most `DECLARED_MAX_POINTS` of the 100 points on its own, so a claim nobody
  has corroborated with real teaching activity can never outrank corroborated
  activity at the same declared level.
* A trainer with no declared row and no published course for the competency is
  `NO_EVIDENCE`: score is `None` (never 0), they are listed after every scored
  trainer, and they are never hidden.
* A component that cannot be computed (e.g. a mean rating from fewer than
  `MIN_RATINGS_FOR_MEAN` ratings) is `available=False` and earns 0 points; the
  response says why instead of guessing. The mean rating is withheld below that
  threshold both for privacy (a single learner's rating would be identifiable)
  and because a mean of one or two ratings is not meaningful.

Score = sum of points earned over the components below (maximum 100). Changing
any weight or cap is a scoring-policy change and requires bumping
`MATCH_POLICY_VERSION`.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Iterable

from sqlalchemy import literal
from sqlalchemy.orm import Session

from models.course import Course
from models.course_enrollment import CourseEnrollment
from models.feedback import CourseFeedback
from models.learning import LearnerProfile
from models.player import Player
from models.trainer_expertise import TrainerExpertise
from services.curricula import CURRICULA

MATCH_POLICY_VERSION = "trainer-match-v1"
MIN_RATINGS_FOR_MEAN = 3
RATING_UNAVAILABLE_REASON = f"fewer than {MIN_RATINGS_FOR_MEAN} ratings"

# Component weights (points out of 100). Declared components total
# DECLARED_MAX_POINTS; activity components total the remainder.
WEIGHT_DECLARED_LEVEL = 35.0
WEIGHT_DECLARED_BASIS = 10.0
WEIGHT_DECLARED_YEARS = 10.0
WEIGHT_PUBLISHED_COURSES = 15.0
WEIGHT_LEARNERS_COMPLETED = 20.0
WEIGHT_MEAN_RATING = 10.0
DECLARED_MAX_POINTS = WEIGHT_DECLARED_LEVEL + WEIGHT_DECLARED_BASIS + WEIGHT_DECLARED_YEARS  # 55

# Saturation caps: the quantity at which a component earns its full weight.
LEVEL_MAX = 5
YEARS_CAP = 10
PUBLISHED_COURSES_CAP = 3
LEARNERS_COMPLETED_CAP = 20

# How strongly each declared basis supports a teaching claim. These are
# policy constants, not verification: the basis text itself is unchecked.
BASIS_FACTOR = {"degree": 1.0, "certification": 1.0, "experience": 0.75, "other": 0.5}

EVIDENCE_DECLARED_ONLY = "DECLARED_ONLY"
EVIDENCE_DECLARED_AND_ACTIVITY = "DECLARED_AND_ACTIVITY"
EVIDENCE_ACTIVITY_ONLY = "ACTIVITY_ONLY"
EVIDENCE_NONE = "NO_EVIDENCE"

SELF_DECLARED_NOTICE = (
    "Declared levels, bases and years are self-declared by each trainer and have not "
    "been verified against any credential. They are combined with real platform "
    "activity (published courses, learner completions, ratings); they are not "
    "an assessment of the trainer."
)


@lru_cache(maxsize=1)
def competency_catalog() -> dict[str, str]:
    """competency_id -> English label, across every curriculum."""
    return {
        competency["id"]: competency["label"]
        for curriculum in CURRICULA.values()
        for competency in curriculum["competencies"]
    }


@dataclass(frozen=True)
class DeclaredExpertise:
    level: int
    basis: str
    basis_detail: str
    years_teaching: int


@dataclass(frozen=True)
class TrainerFacts:
    """Every stored fact the score depends on, and nothing else."""

    trainer_id: str
    declared: DeclaredExpertise | None = None
    published_courses: int = 0
    learners_completed: int = 0
    rating_count: int = 0
    rating_sum: int = 0
    username: str = ""
    full_name: str = ""


def _round(value: float) -> float:
    return round(value, 2)


def _component(
    key: str,
    label: str,
    weight: float,
    *,
    raw: Any,
    fraction: float | None,
    note: str,
) -> dict[str, Any]:
    available = fraction is not None
    return {
        "key": key,
        "label": label,
        "weight": weight,
        "raw_value": raw,
        "fraction": _round(fraction) if available else None,
        "points": _round(weight * fraction) if available else 0.0,
        "available": available,
        "note": note,
    }


def evidence_level(facts: TrainerFacts) -> str:
    has_declared = facts.declared is not None
    has_activity = facts.published_courses > 0
    if has_declared and has_activity:
        return EVIDENCE_DECLARED_AND_ACTIVITY
    if has_declared:
        return EVIDENCE_DECLARED_ONLY
    if has_activity:
        return EVIDENCE_ACTIVITY_ONLY
    return EVIDENCE_NONE


def mean_rating(facts: TrainerFacts) -> tuple[float | None, str | None]:
    if facts.rating_count < MIN_RATINGS_FOR_MEAN:
        return None, RATING_UNAVAILABLE_REASON
    return _round(facts.rating_sum / facts.rating_count), None


def score_trainer(facts: TrainerFacts) -> dict[str, Any]:
    """Pure function: stored facts in, explainable result out."""
    level = evidence_level(facts)
    mean, mean_reason = mean_rating(facts)
    declared = facts.declared

    components = [
        _component(
            "declared_level",
            "Self-declared teaching level",
            WEIGHT_DECLARED_LEVEL,
            raw=declared.level if declared else None,
            fraction=(declared.level / LEVEL_MAX) if declared else None,
            note=f"level / {LEVEL_MAX}; self-declared, unverified"
            if declared
            else "no declared expertise for this competency",
        ),
        _component(
            "declared_basis",
            "Basis of the declared claim",
            WEIGHT_DECLARED_BASIS,
            raw=declared.basis if declared else None,
            fraction=BASIS_FACTOR[declared.basis] if declared else None,
            note="degree/certification 1.0, experience 0.75, other 0.5; the named basis is unverified"
            if declared
            else "no declared expertise for this competency",
        ),
        _component(
            "declared_years",
            "Self-declared years teaching",
            WEIGHT_DECLARED_YEARS,
            raw=declared.years_teaching if declared else None,
            fraction=(min(declared.years_teaching, YEARS_CAP) / YEARS_CAP) if declared else None,
            note=f"min(years, {YEARS_CAP}) / {YEARS_CAP}; self-declared, unverified"
            if declared
            else "no declared expertise for this competency",
        ),
        _component(
            "published_courses",
            "Published courses on this competency",
            WEIGHT_PUBLISHED_COURSES,
            raw=facts.published_courses,
            fraction=min(facts.published_courses, PUBLISHED_COURSES_CAP) / PUBLISHED_COURSES_CAP,
            note=f"min(count, {PUBLISHED_COURSES_CAP}) / {PUBLISHED_COURSES_CAP}",
        ),
        _component(
            "learners_completed",
            "Distinct learners who completed those courses",
            WEIGHT_LEARNERS_COMPLETED,
            raw=facts.learners_completed,
            fraction=min(facts.learners_completed, LEARNERS_COMPLETED_CAP) / LEARNERS_COMPLETED_CAP,
            note=f"min(count, {LEARNERS_COMPLETED_CAP}) / {LEARNERS_COMPLETED_CAP}; the trainer's own enrolment is excluded",
        ),
        _component(
            "mean_rating",
            "Mean learner rating of those courses",
            WEIGHT_MEAN_RATING,
            raw=mean,
            fraction=((mean - 1) / 4) if mean is not None else None,
            note="(mean - 1) / 4" if mean is not None else (mean_reason or ""),
        ),
    ]

    score: float | None
    if level == EVIDENCE_NONE:
        score = None
    else:
        score = _round(sum(component["points"] for component in components))

    return {
        "trainer_id": facts.trainer_id,
        "username": facts.username,
        "full_name": facts.full_name,
        "evidence_level": level,
        "score": score,
        "components": components if level != EVIDENCE_NONE else [],
        "facts": {
            "declared": (
                {
                    "declared_level": declared.level,
                    "basis": declared.basis,
                    "basis_detail": declared.basis_detail,
                    "years_teaching": declared.years_teaching,
                    "self_declared": True,
                    "verified": False,
                }
                if declared
                else None
            ),
            "published_courses": facts.published_courses,
            "learners_completed": facts.learners_completed,
            "rating_count": facts.rating_count,
            "mean_rating": mean,
            "mean_rating_reason": mean_reason,
        },
        "rationale": _rationale(facts, level, score, mean, mean_reason),
    }


def _rationale(
    facts: TrainerFacts,
    level: str,
    score: float | None,
    mean: float | None,
    mean_reason: str | None,
) -> list[str]:
    if level == EVIDENCE_NONE:
        return [
            "No evidence for this competency: the trainer has not declared expertise in it "
            "and has no published course on it. This is not a low score; there is simply "
            "nothing to score."
        ]
    lines: list[str] = []
    declared = facts.declared
    if declared:
        detail = f" ({declared.basis_detail})" if declared.basis_detail else ""
        lines.append(
            f"Self-declared (unverified) teaching level {declared.level} of {LEVEL_MAX}, "
            f"basis: {declared.basis}{detail}, {declared.years_teaching} year(s) teaching."
        )
    else:
        lines.append("No declared expertise for this competency; scored on platform activity only.")
    if facts.published_courses:
        lines.append(f"{facts.published_courses} published course(s) targeting this competency.")
    else:
        lines.append(
            "No published course on this competency, so the score rests on the unverified "
            f"declaration alone and cannot exceed {DECLARED_MAX_POINTS:g} of 100."
        )
    if facts.published_courses:
        lines.append(f"{facts.learners_completed} distinct learner(s) completed those courses.")
    if mean is not None:
        lines.append(f"Mean learner rating {mean} of 5 across {facts.rating_count} ratings.")
    elif facts.published_courses:
        lines.append(f"Mean rating not shown: {mean_reason} ({facts.rating_count} so far).")
    lines.append(f"Score {score:g} of 100 under policy {MATCH_POLICY_VERSION}.")
    return lines


def rank_trainers(facts_list: Iterable[TrainerFacts]) -> list[dict[str, Any]]:
    """Score everyone, scored trainers first by (-score, trainer_id), then all
    NO_EVIDENCE trainers by trainer_id. Ties never depend on input order."""
    results = [score_trainer(facts) for facts in facts_list]
    scored = sorted(
        (r for r in results if r["score"] is not None),
        key=lambda r: (-r["score"], r["trainer_id"]),
    )
    unscored = sorted(
        (r for r in results if r["score"] is None),
        key=lambda r: r["trainer_id"],
    )
    for position, result in enumerate(scored, start=1):
        result["rank"] = position
    for result in unscored:
        result["rank"] = None
    return scored + unscored


def policy_description() -> dict[str, Any]:
    return {
        "policy_version": MATCH_POLICY_VERSION,
        "max_points": 100,
        "declared_max_points": DECLARED_MAX_POINTS,
        "weights": {
            "declared_level": WEIGHT_DECLARED_LEVEL,
            "declared_basis": WEIGHT_DECLARED_BASIS,
            "declared_years": WEIGHT_DECLARED_YEARS,
            "published_courses": WEIGHT_PUBLISHED_COURSES,
            "learners_completed": WEIGHT_LEARNERS_COMPLETED,
            "mean_rating": WEIGHT_MEAN_RATING,
        },
        "min_ratings_for_mean": MIN_RATINGS_FOR_MEAN,
    }


def gather_facts(db: Session, competency_id: str) -> list[TrainerFacts]:
    """Read the stored facts for every candidate trainer.

    Candidates are players who have either declared any expertise or authored
    any course (published or not) -- i.e. people the platform has a reason to
    consider a trainer. They are included even when they have nothing for
    *this* competency, so NO_EVIDENCE rows are shown rather than hidden.
    Activity counts only PUBLISHED internal courses; a trainer's own
    enrolments and ratings on their own courses are excluded.
    """

    candidate_ids = {row[0] for row in db.query(TrainerExpertise.trainer_id).distinct()}
    candidate_ids |= {row[0] for row in db.query(Course.trainer_id).distinct()}
    if not candidate_ids:
        return []

    declared = {
        row.trainer_id: DeclaredExpertise(
            level=row.declared_level,
            basis=row.basis,
            basis_detail=row.basis_detail or "",
            years_teaching=row.years_teaching,
        )
        for row in db.query(TrainerExpertise).filter(TrainerExpertise.competency_id == competency_id)
    }

    published = (
        db.query(Course.course_id, Course.trainer_id)
        .filter(Course.competency_id == competency_id, Course.is_published.is_(True))
        .all()
    )
    course_count: dict[str, int] = {}
    for _, trainer_id in published:
        course_count[trainer_id] = course_count.get(trainer_id, 0) + 1

    completers: dict[str, set[str]] = {}
    completion_rows = (
        db.query(Course.trainer_id, CourseEnrollment.player_id)
        .join(CourseEnrollment, CourseEnrollment.course_id == literal("internal::") + Course.course_id)
        .filter(
            Course.competency_id == competency_id,
            Course.is_published.is_(True),
            CourseEnrollment.provider == "internal",
            CourseEnrollment.status == "completed",
            CourseEnrollment.player_id != Course.trainer_id,
        )
        .all()
    )
    for trainer_id, player_id in completion_rows:
        completers.setdefault(trainer_id, set()).add(player_id)

    rating_stats: dict[str, tuple[int, int]] = {}
    rating_rows = (
        db.query(Course.trainer_id, CourseFeedback.rating)
        .join(CourseFeedback, CourseFeedback.course_id == Course.course_id)
        .filter(
            Course.competency_id == competency_id,
            Course.is_published.is_(True),
            CourseFeedback.player_id != Course.trainer_id,
        )
        .all()
    )
    for trainer_id, rating in rating_rows:
        count, total = rating_stats.get(trainer_id, (0, 0))
        rating_stats[trainer_id] = (count + 1, total + rating)

    names = {
        player_id: username
        for player_id, username in db.query(Player.player_id, Player.username).filter(
            Player.player_id.in_(candidate_ids)
        )
    }
    full_names = {
        player_id: full_name or ""
        for player_id, full_name in db.query(LearnerProfile.player_id, LearnerProfile.full_name).filter(
            LearnerProfile.player_id.in_(candidate_ids)
        )
    }

    return [
        TrainerFacts(
            trainer_id=trainer_id,
            declared=declared.get(trainer_id),
            published_courses=course_count.get(trainer_id, 0),
            learners_completed=len(completers.get(trainer_id, ())),
            rating_count=rating_stats.get(trainer_id, (0, 0))[0],
            rating_sum=rating_stats.get(trainer_id, (0, 0))[1],
            username=names.get(trainer_id, ""),
            full_name=full_names.get(trainer_id, ""),
        )
        for trainer_id in sorted(candidate_ids)
    ]


def match_trainers(db: Session, competency_id: str) -> dict[str, Any]:
    catalog = competency_catalog()
    return {
        **policy_description(),
        "competency_id": competency_id,
        "competency_label": catalog.get(competency_id, competency_id),
        "notice": SELF_DECLARED_NOTICE,
        "trainers": rank_trainers(gather_facts(db, competency_id)),
    }
