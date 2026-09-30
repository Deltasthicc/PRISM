"""Real, verifiable completion certificates (SIH26075 CC-02/CC-11).

Issuance itself lives in routes/course_enrollment.py's complete() handler
(a certificate is a side effect of a real internal-course completion, not
a route anyone can call directly to mint one) -- this file only owns
reading and verifying certificates that already exist.

The verification endpoint is deliberately public: the entire point of a
certificate is that a third party (an employer, another trainee, a
program auditor) can confirm it is real without holding a PRISM account,
by the same code printed on the certificate itself. It returns only what
is safe to disclose to an unauthenticated caller -- never the owning
player's identity, an internal certificate_id, or anything else beyond
whether the code is a real, currently-valid certificate.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.certificate import Certificate
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/certificates", tags=["Certificates"])


class CertificateResponse(BaseModel):
    certificate_id: str
    course_id: str
    title: str
    verification_code: str
    issued_at: datetime
    revoked: bool


class VerificationResponse(BaseModel):
    valid: bool
    title: str | None = None
    issued_at: datetime | None = None
    revoked: bool | None = None
    detail: str | None = None


def _serialize(cert: Certificate) -> CertificateResponse:
    return CertificateResponse(
        certificate_id=cert.certificate_id,
        course_id=cert.course_id,
        title=cert.title,
        verification_code=cert.verification_code,
        issued_at=cert.issued_at,
        revoked=cert.revoked,
    )


@router.get("", response_model=list[CertificateResponse])
def list_my_certificates(
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.CERTIFICATE_READ)),
    db: Session = Depends(get_db),
) -> list[CertificateResponse]:
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    rows = (
        db.query(Certificate)
        .filter(Certificate.player_id == player_id)
        .order_by(Certificate.issued_at.desc())
        .all()
    )
    return [_serialize(row) for row in rows]


# Unauthenticated by design -- see module docstring. Not mounted under a
# Permission dependency at all, matching the "verification is public"
# requirement rather than merely granting every role read access.
@router.get("/verify/{verification_code}", response_model=VerificationResponse)
def verify_certificate(verification_code: str, db: Session = Depends(get_db)) -> VerificationResponse:
    cert = (
        db.query(Certificate)
        .filter(Certificate.verification_code == verification_code)
        .one_or_none()
    )
    if cert is None:
        return VerificationResponse(valid=False, detail="No certificate matches this code.")
    if cert.revoked:
        return VerificationResponse(
            valid=False, title=cert.title, issued_at=cert.issued_at, revoked=True,
            detail="This certificate has been revoked.",
        )
    return VerificationResponse(valid=True, title=cert.title, issued_at=cert.issued_at, revoked=False)
