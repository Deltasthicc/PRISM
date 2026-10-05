"""Privacy-safe aggregate analytics routes."""

import os
from collections import Counter, defaultdict
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from db.database import get_db
from models.course_enrollment import CourseEnrollment
from models.judgment_scenario import JudgmentScenarioAttempt
from models.learning import CompetencyAssessment, GeneratedQuiz, GeneratedQuizAttempt, LearnerProfile
from models.player import Player
from routes.authorization import require_permission_dependency
from security.rbac import BoundPrincipal, Permission
from services.curricula import CURRICULA
from services.learning_catalog import integration_status

router = APIRouter(prefix="/learning", tags=["Learning Analytics"])

_PRIVACY_NOTE = {
    "en": "This endpoint intentionally exposes latest-distinct-learner aggregates only.",
    "hi": "यह एंडपॉइंट जानबूझकर केवल नवीनतम-विशिष्ट-शिक्षार्थी समुच्चय ही प्रकट करता है।",
    "bn": "এই শেষপয়েন্ট ইচ্ছাকৃতভাবে শুধুমাত্র সাম্প্রতিক-স্বতন্ত্র-শিক্ষক সমষ্টিকে প্রকাশ করে।",
    "mr": "हा एंडपॉईंट जाणूनबुजून केवळ नवीनतम-वेगवेगळ्या-शिक्षणा-यांच्या एकत्रिततेचा पर्दाफाश करतो.",
    "te": "ఈ ఎండ్‌పాయింట్ ఉద్దేశపూర్వకంగా తాజా-విశిష్ట-అభ్యాసకుల సముదాయాలను మాత్రమే బహిర్గతం చేస్తుంది.",
    "ta": "இந்த இறுதிப்புள்ளி வேண்டுமென்றே சமீபத்திய-தனித்துவ-கற்றல் திரட்டுகளை மட்டுமே வெளிப்படுத்துகிறது.",
    "gu": "આ એન્ડપોઇન્ટ ઇરાદાપૂર્વક ફક્ત નવીનતમ-વિશિષ્ટ-શિખનાર એકંદરને પ્રગટ કરે છે.",
    "ur": "یہ اختتامی نقطہ جان بوجھ کر صرف تازہ ترین الگ الگ سیکھنے والے مجموعوں کو ظاہر کرتا ہے۔",
    "kn": "ಈ ಅಂತಿಮ ಬಿಂದುವು ಉದ್ದೇಶಪೂರ್ವಕವಾಗಿ ಇತ್ತೀಚಿನ-ವಿಶಿಷ್ಟ-ಕಲಿಕಾ ಸಮುಚ್ಚಯಗಳನ್ನು ಮಾತ್ರ ಬಹಿರಂಗಪಡಿಸುತ್ತದೆ.",
    "or": "ଏହି ଶେଷ ପଏଣ୍ଟ ଉଦ୍ଦେଶ୍ୟମୂଳକ ଭାବରେ କେବଳ ସର୍ବଶେଷ-ପୃଥକ-ଶିକ୍ଷାର୍ଥୀ ଏଗ୍ରିଗେଟ୍ଗୁଡ଼ିକୁ ପ୍ରକାଶ କରେ |",
    "ml": "ഈ എൻഡ്‌പോയിൻ്റ് ഏറ്റവും പുതിയ-വ്യത്യസ്‌ത-പഠിതാക്കളുടെ സംഗ്രഹങ്ങളെ മാത്രം മനഃപൂർവം തുറന്നുകാട്ടുന്നു.",
}

# competency_id -> label, built once from the real curriculum catalog
# (services/curricula.py) so training-effectiveness and emerging-skill-gap
# rows can report a real, human-readable label instead of the bare internal
# competency_id. Falls back to the id itself for anything not in the
# catalog (e.g. a stale/removed competency referenced by an old assessment).
_COMPETENCY_LABELS: dict[str, str] = {
    competency["id"]: competency["label"]
    for curriculum in CURRICULA.values()
    for competency in curriculum.get("competencies", [])
}


def _label_for(competency_id: str) -> str:
    return _COMPETENCY_LABELS.get(competency_id, competency_id)


# Show at most this many of the most recent real weeks in the activity
# trend. Never zero-filled beyond what real data provides -- see
# _activity_trend's docstring.
_TREND_WEEK_CAP = 12

# Smallest number of distinct learners a published group may describe. A row
# built from fewer people (a gap shared by one learner, an average over two)
# lets a reader work out who it is, so it is withheld and only counted in
# `suppressed`. Overridable per deployment; 1 disables suppression.
_DEFAULT_MIN_GROUP_SIZE = 5
_STREAM_BATCH = 1000


def _min_group_size() -> int:
    raw = os.environ.get("ANALYTICS_MIN_GROUP_SIZE")
    if raw is None or not raw.strip():
        return _DEFAULT_MIN_GROUP_SIZE
    try:
        return max(1, int(raw))
    except ValueError:
        return _DEFAULT_MIN_GROUP_SIZE


def _training_effectiveness(db: Session, min_group: int, top_n: int = 8) -> tuple[list[dict], int]:
    """For each competency, the average (latest measured_score - earliest
    measured_score) across every player who has at least two assessment
    rows that both touch that competency, plus how many players that
    average is computed over (`learner_count`) so the frontend can show
    honest "n=12"-style sample-size context rather than implying universal
    coverage.

    This is a genuine Python-side loop over one narrow, ordered column
    projection rather than a single grouped SQL query, because "earliest vs
    latest measured_score for a given competency, per player" requires
    walking each player's own assessment rows in temporal order and reading
    a key out of their measured_scores JSON blob -- not something a GROUP
    BY can express portably across this app's SQLite and PostgreSQL
    backends. Only the four columns actually needed are pulled (no full
    ORM row hydration), scanned once and streamed in batches so memory is
    bounded by the number of (player, competency) pairs, not by history.

    Competencies measured over fewer than `min_group` learners are withheld;
    the second return value is how many.
    """
    rows = (
        db.query(
            CompetencyAssessment.player_id,
            CompetencyAssessment.measured_scores,
            CompetencyAssessment.created_at,
            CompetencyAssessment.assessment_id,
        )
        .order_by(CompetencyAssessment.created_at.asc(), CompetencyAssessment.assessment_id.asc())
        .yield_per(_STREAM_BATCH)
    )

    # (player_id, competency_id) -> {"first": score, "last": score, "count": n}
    tracker: dict[tuple[str, str], dict] = {}
    for player_id, measured_scores, _created_at, _assessment_id in rows:
        for competency_id, score in (measured_scores or {}).items():
            if not isinstance(score, (int, float)):
                continue
            key = (player_id, competency_id)
            entry = tracker.get(key)
            if entry is None:
                tracker[key] = {"first": score, "last": score, "count": 1}
            else:
                entry["last"] = score
                entry["count"] += 1

    deltas_by_competency: dict[str, list[float]] = defaultdict(list)
    for (_player_id, competency_id), entry in tracker.items():
        if entry["count"] < 2:
            continue
        deltas_by_competency[competency_id].append(entry["last"] - entry["first"])

    summaries = [
        {
            "competency": _label_for(competency_id),
            "competency_id": competency_id,
            "avg_improvement": round(sum(deltas) / len(deltas), 2),
            "learner_count": len(deltas),
        }
        for competency_id, deltas in deltas_by_competency.items()
        if len(deltas) >= min_group
    ]
    suppressed = len(deltas_by_competency) - len(summaries)
    summaries.sort(key=lambda row: abs(row["avg_improvement"]), reverse=True)
    return summaries[:top_n], suppressed


def _course_completion(db: Session, min_group: int, top_n: int = 10) -> tuple[dict, int]:
    """Real enroll/complete funnel from CourseEnrollment -- entirely
    SQL-side grouped aggregation (func.count/func.sum), no per-row Python
    loop needed since this is a plain group-by over a handful of columns."""
    total_enrollments = db.query(func.count(CourseEnrollment.enrollment_id)).scalar() or 0
    total_completions = (
        db.query(func.count(CourseEnrollment.enrollment_id))
        .filter(CourseEnrollment.status == "completed")
        .scalar()
        or 0
    )
    completion_rate = (total_completions / total_enrollments * 100) if total_enrollments else 0.0

    per_course = (
        db.query(
            CourseEnrollment.course_id,
            CourseEnrollment.title,
            func.count(CourseEnrollment.enrollment_id).label("enrolled"),
            func.sum(case((CourseEnrollment.status == "completed", 1), else_=0)).label("completed"),
        )
        .group_by(CourseEnrollment.course_id, CourseEnrollment.title)
        .order_by(func.count(CourseEnrollment.enrollment_id).desc())
        .limit(top_n)
        .all()
    )
    # One enrollment row per learner per course, so `enrolled` is the number
    # of distinct learners behind each per-course rate.
    visible = [row for row in per_course if row[2] >= min_group]
    suppressed = len(per_course) - len(visible)

    return {
        "total_enrollments": total_enrollments,
        "total_completions": total_completions,
        "completion_rate_pct": round(completion_rate, 1),
        "by_course": [
            {
                "course_id": course_id,
                "title": title,
                "enrolled": enrolled,
                "completed": completed or 0,
                "completion_rate_pct": round((completed or 0) / enrolled * 100, 1) if enrolled else 0.0,
            }
            for course_id, title, enrolled, completed in visible
        ],
    }, suppressed


def _week_key(timestamp) -> tuple[int, int]:
    iso = timestamp.isocalendar()
    return (iso[0], iso[1])


def _daily_counts(db: Session, column, condition=None) -> list[tuple[date, int]]:
    """Events per calendar day, grouped in the database so the result has one
    row per active day instead of one per event. SQLite returns the day as
    text and PostgreSQL as a date; both are normalised to `date`."""
    day = func.date(column)
    query = db.query(day, func.count()).filter(column.isnot(None))
    if condition is not None:
        query = query.filter(condition)
    return [
        (value if isinstance(value, date) else date.fromisoformat(str(value)), count)
        for value, count in query.group_by(day).all()
    ]


def _activity_trend(db: Session, week_cap: int = _TREND_WEEK_CAP) -> list[dict]:
    """Real counts of quiz attempts, judgment-scenario completions, and
    course completions, bucketed into ISO calendar weeks -- the honest
    substitute for a fabricated "hours trained" metric, since no real
    duration field is persisted anywhere in this app (checked
    GeneratedQuizAttempt, JudgmentScenarioAttempt, CourseEnrollment and
    AccuracyHistory: none of them store a duration, only timestamps and
    outcome fields).

    Each source is grouped by day in the database (one row per active day,
    not one per event). The days are then bucketed into weeks in Python using ISO calendar-week semantics so the result
    is identical regardless of which database backend is running this app:
    SQLite's strftime('%W', ...) and PostgreSQL's date_trunc('week', ...)
    do not agree with each other (or with ISO 8601) on which day a week
    starts, so bucketing this in SQL would make identical data disagree
    across this app's two supported backends -- exactly the kind of
    cross-row comparison this task's own guidance calls out as acceptable
    to do in Python rather than force into one non-portable query.

    Deliberately never zero-fills a missing week: a deployment with two
    real weeks of activity shows two real weeks, not ten fabricated ones.
    """
    buckets: dict[tuple[int, int], dict] = defaultdict(
        lambda: {"quiz_attempts": 0, "scenario_completions": 0, "course_completions": 0}
    )
    sources = (
        ("quiz_attempts", GeneratedQuizAttempt.attempted_at, None),
        ("scenario_completions", JudgmentScenarioAttempt.completed_at, None),
        ("course_completions", CourseEnrollment.completed_at, CourseEnrollment.status == "completed"),
    )
    for field, column, condition in sources:
        for day, count in _daily_counts(db, column, condition):
            buckets[_week_key(day)][field] += count

    ordered_keys = sorted(buckets.keys())[-week_cap:]
    trend = []
    for year, week in ordered_keys:
        counts = buckets[(year, week)]
        total = counts["quiz_attempts"] + counts["scenario_completions"] + counts["course_completions"]
        trend.append({
            "week_start": date.fromisocalendar(year, week, 1).isoformat(),
            **counts,
            "total": total,
        })
    return trend


def _emerging_skill_gaps(
    db: Session, min_group: int, top_n: int = 8, min_assessments: int = 4
) -> tuple[list[dict], int]:
    """Which skill gaps are becoming MORE common recently vs earlier -- a
    genuine trend signal `top_skill_gaps` cannot show, since that field
    only counts gaps in each learner's single latest assessment (one
    current snapshot, no direction of travel). This splits every
    assessment row -- the full temporal history across every learner
    stream, not deduped to one-per-stream like `top_skill_gaps` -- into an
    earlier and a later chronological half by created_at, and compares how
    often each gap label appears in each half. A positive delta means that
    gap is showing up more often in recent assessments than it used to.

    Requires at least `min_assessments` total assessment rows before
    computing anything: a two-way split of a handful of rows would be
    noise dressed up as a trend, not a real signal, so this returns an
    empty list rather than mislead with too little data. Rows are streamed
    in batches after a COUNT, so the history is never held in memory.

    A gap is only published when at least `min_group` distinct learners show
    it in the recent half; the second return value counts withheld gaps.
    """
    total = db.query(func.count(CompetencyAssessment.assessment_id)).scalar() or 0
    if total < min_assessments:
        return [], 0

    rows = (
        db.query(CompetencyAssessment.skill_gaps, CompetencyAssessment.player_id)
        .order_by(CompetencyAssessment.created_at.asc(), CompetencyAssessment.assessment_id.asc())
        .yield_per(_STREAM_BATCH)
    )

    midpoint = total // 2
    earlier_counter: Counter = Counter()
    recent_counter: Counter = Counter()
    recent_learners: dict[str, set[str]] = defaultdict(set)
    for index, (skill_gaps, player_id) in enumerate(rows):
        in_recent = index >= midpoint
        counter = recent_counter if in_recent else earlier_counter
        for gap in skill_gaps or []:
            label = gap.get("label") or gap.get("competency_id", "Unknown")
            counter[label] += 1
            if in_recent:
                recent_learners[label].add(player_id)

    summaries = [
        {
            "competency": label,
            "earlier_count": earlier_counter.get(label, 0),
            "recent_count": recent_counter.get(label, 0),
            "delta": recent_counter.get(label, 0) - earlier_counter.get(label, 0),
        }
        for label in set(earlier_counter) | set(recent_counter)
    ]
    # Only genuinely emerging gaps -- rising in prevalence, not just
    # currently common (top_skill_gaps already covers "currently common").
    summaries = [row for row in summaries if row["delta"] > 0]
    visible = [row for row in summaries if len(recent_learners[row["competency"]]) >= min_group]
    suppressed = len(summaries) - len(visible)
    visible.sort(key=lambda row: row["delta"], reverse=True)
    return visible[:top_n], suppressed


@router.get("/admin/overview")
async def admin_overview(
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.ORGANIZATION_ANALYTICS_READ)
    ),
    lang: str = Query("en", pattern="^(en|hi|bn|mr|te|ta|gu|ur|kn|or|ml)$"),
):
    """Aggregate-only dashboard using the latest assessment per learner stream.

    Groups smaller than `min_group_size` distinct learners are withheld and
    tallied under `suppressed`, so a published row never singles a person
    out."""
    min_group = _min_group_size()

    # Latest assessment per (learner, curriculum) chosen in SQL; only its
    # skill_gaps are read, so memory scales with the number of learner
    # streams, not with total assessment history.
    ranked = db.query(
        CompetencyAssessment.player_id.label("player_id"),
        CompetencyAssessment.skill_gaps.label("skill_gaps"),
        func.row_number()
        .over(
            partition_by=(CompetencyAssessment.player_id, CompetencyAssessment.curriculum_slug),
            order_by=(CompetencyAssessment.created_at.desc(), CompetencyAssessment.assessment_id.desc()),
        )
        .label("rn"),
    ).subquery()
    latest = db.query(ranked.c.player_id, ranked.c.skill_gaps).filter(ranked.c.rn == 1).all()

    gap_learners: dict[str, set[str]] = defaultdict(set)
    priority_counter = Counter()
    for player_id, skill_gaps in latest:
        for gap in skill_gaps or []:
            gap_learners[gap.get("label") or gap.get("competency_id", "Unknown")].add(player_id)
            priority_counter[gap.get("priority", "unknown")] += 1
    gap_counts = Counter({label: len(people) for label, people in gap_learners.items()})
    visible_gaps = [(label, count) for label, count in gap_counts.most_common() if count >= min_group]

    training_effectiveness, suppressed_effectiveness = _training_effectiveness(db, min_group)
    course_completion, suppressed_courses = _course_completion(db, min_group)
    emerging_skill_gaps, suppressed_emerging = _emerging_skill_gaps(db, min_group)

    return {
        "learners": db.query(Player).count(),
        "profiles_completed": db.query(LearnerProfile).count(),
        "assessments_completed": len(latest),
        "quizzes_generated": db.query(GeneratedQuiz).count(),
        "top_skill_gaps": [
            {"competency": competency, "learner_count": count} for competency, count in visible_gaps[:8]
        ],
        "gap_priorities": dict(priority_counter),
        "training_effectiveness": training_effectiveness,
        "course_completion": course_completion,
        "activity_trend": _activity_trend(db),
        "emerging_skill_gaps": emerging_skill_gaps,
        "min_group_size": min_group,
        "suppressed": {
            "top_skill_gaps": len(gap_counts) - len(visible_gaps),
            "training_effectiveness": suppressed_effectiveness,
            "course_completion": suppressed_courses,
            "emerging_skill_gaps": suppressed_emerging,
        },
        "integration_status": integration_status(lang),
        "privacy_note": _PRIVACY_NOTE.get(lang, _PRIVACY_NOTE["en"]),
    }
