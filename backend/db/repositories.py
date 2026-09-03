"""Lane 2 shared read-only repository queries.

Other lanes should call these instead of re-deriving ordering/tie-breaking
rules from a model directly -- docs/contracts/data-authorization.md is the
authoritative semantics document; this module is the single implementation
of it. Nothing here is a route. Lane 5 owns wiring a query like
get_latest_assessment() into an actual HTTP endpoint
(docs/contracts/data-authorization.md section 4's contracted
`GET /learning/assessment/{player_id}/latest` is not implemented yet) and
into backend/routes/learning.py's existing pathway lookup, which today
orders by `created_at` only and does not yet use the `assessment_id`
tie-breaker below -- see LANE2_SYNC.md's Package H entry.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import case, or_
from sqlalchemy.orm import Session

from models.governance import EVIDENCE_TYPES, EvidenceRecord, RoleTarget, SourceVersion
from models.learning import CompetencyAssessment


def _require_key(value: str, field: str) -> str:
    """Reject an absent lookup key without silently normalizing identity data."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _newest_first(timestamp_column, id_column):
    """Portable newest-first ordering with a deterministic null/ID policy."""
    return (
        case((timestamp_column.is_(None), 1), else_=0).asc(),
        timestamp_column.desc(),
        id_column.desc(),
    )


def get_latest_assessment(
    db: Session, player_id: str, curriculum_slug: str
) -> CompetencyAssessment | None:
    """Return the single latest assessment row for one (player_id,
    curriculum_slug) stream, per docs/contracts/data-authorization.md
    section 4's exact ordering:

    1. non-null `created_at` sorts before null `created_at`;
    2. `created_at` descending; then
    3. `assessment_id` descending as the final, always-deterministic
       tie-breaker.

    Returns None when the stream has no assessment at all -- callers must
    not treat that the same as an assessment with zero self-ratings
    (CODEX.md "Architecture invariants": "no evidence" is not low ability).
    """
    return (
        db.query(CompetencyAssessment)
        .filter(
            CompetencyAssessment.player_id == player_id,
            CompetencyAssessment.curriculum_slug == curriculum_slug,
        )
        .order_by(
            case((CompetencyAssessment.created_at.is_(None), 1), else_=0).asc(),
            CompetencyAssessment.created_at.desc(),
            CompetencyAssessment.assessment_id.desc(),
        )
        .first()
    )


def get_current_role_target(
    db: Session,
    role: str,
    competency_id: str,
    *,
    as_of: datetime | None = None,
) -> RoleTarget | None:
    """Return the current exact-role target for one competency.

    The validity interval is half-open: ``valid_from <= as_of < valid_to``;
    a null ``valid_to`` means no scheduled end. A null ``valid_from`` is not
    eligible because its start cannot be established. When malformed or
    overlapping rows exist, the most recent ``valid_from``, then
    ``created_at``, then ``target_id`` wins deterministically.

    This deliberately performs an exact role lookup. Role/designation/
    department precedence, aliases and the ``"*"`` fallback are Lane 3
    policy and must not be smuggled into the storage layer.
    """
    role = _require_key(role, "role")
    competency_id = _require_key(competency_id, "competency_id")
    instant = as_of or datetime.now(timezone.utc)
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("as_of must be timezone-aware")

    return (
        db.query(RoleTarget)
        .filter(
            RoleTarget.role == role,
            RoleTarget.competency_id == competency_id,
            RoleTarget.valid_from.is_not(None),
            RoleTarget.valid_from <= instant,
            or_(RoleTarget.valid_to.is_(None), RoleTarget.valid_to > instant),
        )
        .order_by(
            RoleTarget.valid_from.desc(),
            *_newest_first(RoleTarget.created_at, RoleTarget.target_id),
        )
        .first()
    )


def get_latest_evidence(
    db: Session,
    player_id: str,
    competency_id: str,
    evidence_type: str,
) -> EvidenceRecord | None:
    """Return one learner's latest evidence row for one type and competency.

    Null ``recorded_at`` values sort behind timestamped records and
    ``evidence_id`` is the deterministic final tie-breaker. Authorization is
    intentionally not inferred here: a route must first resolve a verified
    principal and enforce own-player or privileged scope.
    """
    player_id = _require_key(player_id, "player_id")
    competency_id = _require_key(competency_id, "competency_id")
    if evidence_type not in EVIDENCE_TYPES:
        raise ValueError(f"evidence_type must be one of {EVIDENCE_TYPES}, got {evidence_type!r}")

    return (
        db.query(EvidenceRecord)
        .filter(
            EvidenceRecord.player_id == player_id,
            EvidenceRecord.competency_id == competency_id,
            EvidenceRecord.evidence_type == evidence_type,
        )
        .order_by(*_newest_first(EvidenceRecord.recorded_at, EvidenceRecord.evidence_id))
        .first()
    )


def get_latest_source_version(db: Session, material_id: str) -> SourceVersion | None:
    """Return the highest stored version for exactly one learning material.

    ``version_number`` is authoritative. ``created_at`` and
    ``source_version_id`` only make accidental duplicate version numbers
    deterministic; this function does not pretend those duplicates are
    valid or approved content.
    """
    material_id = _require_key(material_id, "material_id")
    return (
        db.query(SourceVersion)
        .filter(SourceVersion.material_id == material_id)
        .order_by(
            SourceVersion.version_number.desc(),
            *_newest_first(SourceVersion.created_at, SourceVersion.source_version_id),
        )
        .first()
    )
