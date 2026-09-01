"""Retention policy registry -- Package L.

`security.data_rights.RETENTION_CLASSIFICATION` says WHAT category a table
belongs to (delete-on-request, scrub-on-request, retain-append-only). This
module says the one thing that classification alone doesn't: whether a
category has a known MINIMUM retention duration (a floor -- don't delete
before this) or a known MAXIMUM retention duration (a ceiling -- must not be
kept forever). Today, exactly one category has an actual cited minimum;
nothing has a cited maximum. This module does not invent one.

Read `docs/contracts/data-authorization.md` section 6.3 before changing
anything here -- retention duration claims are exactly the kind of thing
this project has repeatedly found other AI-generated plans fabricating.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RetentionPolicy:
    """What is actually known about how long one category's rows must, or
    must not, be kept -- never a claim of an automated job that enforces it.
    """

    category: str
    minimum_retention_days: int | None
    minimum_retention_source: str | None
    maximum_retention_days: int | None
    maximum_retention_source: str | None
    notes: str

    def __post_init__(self) -> None:
        if (self.minimum_retention_days is None) != (self.minimum_retention_source is None):
            raise ValueError(
                f"{self.category}: a minimum retention duration and its source "
                "must both be set, or both be None -- never one without the other"
            )
        if (self.maximum_retention_days is None) != (self.maximum_retention_source is None):
            raise ValueError(
                f"{self.category}: a maximum retention duration and its source "
                "must both be set, or both be None -- never one without the other"
            )
        if self.minimum_retention_days is not None and self.minimum_retention_days < 0:
            raise ValueError(f"{self.category}: minimum_retention_days must not be negative")
        if self.maximum_retention_days is not None and self.maximum_retention_days < 0:
            raise ValueError(f"{self.category}: maximum_retention_days must not be negative")
        if (
            self.minimum_retention_days is not None
            and self.maximum_retention_days is not None
            and self.minimum_retention_days > self.maximum_retention_days
        ):
            raise ValueError(
                f"{self.category}: minimum_retention_days ({self.minimum_retention_days}) "
                f"exceeds maximum_retention_days ({self.maximum_retention_days}) -- "
                "no valid retention window would exist"
            )


# The CERT-In citation below is a MINIMUM (a floor): it requires certain ICT
# logs to be kept for at least 180 days, not a rule that they must be
# deleted at 180 days. Confusing a floor for a ceiling would make an
# "expiry job" built from this module delete data CERT-In requires be kept --
# see the deliberately named guard function below, which only ever enforces
# the floor.
#
# Applicability caveat, carried over from SIH26101_MASTER_CHECKLIST.md line
# 181: this direction targets government-operated ICT systems, and this
# repository's exact organizational ownership/applicability has NOT been
# confirmed with MoSPI/CERT-In. The citation is real; whether it legally
# binds this specific deployment is still BLOCKED-EXTERNAL/LEGAL.
_CERT_IN_DIRECTION_70B = (
    "CERT-In Directions under section 70B, 28.04.2022 "
    "(https://cert-in.org.in/PDF/CERT-In_Directions_70B_28.04.2022.pdf) -- "
    "rolling 180-day retention of specified ICT logs. Applicability to this "
    "specific deployment is unconfirmed; see SIH26101_MASTER_CHECKLIST.md line 181."
)

RETENTION_POLICIES: dict[str, RetentionPolicy] = {
    "delete_with_verified_subject_request": RetentionPolicy(
        category="delete_with_verified_subject_request",
        minimum_retention_days=None,
        minimum_retention_source=None,
        maximum_retention_days=None,
        maximum_retention_source=None,
        notes=(
            "Learner-owned records. No cited minimum or maximum. Retention today IS the "
            "verified-subject-request boundary itself: a row is kept indefinitely until "
            "security.data_rights.delete_subject_data() removes it on a verified request. "
            "There is no scheduled/automatic expiry, and none is claimed."
        ),
    ),
    "scrub_with_verified_subject_request": RetentionPolicy(
        category="scrub_with_verified_subject_request",
        minimum_retention_days=None,
        minimum_retention_source=None,
        maximum_retention_days=None,
        maximum_retention_source=None,
        notes=(
            "guild_topic_assignments JSON entries. Same reality as delete_with_verified_"
            "subject_request: scrubbed on request, never on a schedule."
        ),
    ),
    "retain_append_only_security_log_duration_policy_pending": RetentionPolicy(
        category="retain_append_only_security_log_duration_policy_pending",
        minimum_retention_days=180,
        minimum_retention_source=_CERT_IN_DIRECTION_70B,
        maximum_retention_days=None,
        maximum_retention_source=None,
        notes=(
            "audit_events. security.data_rights.delete_subject_data() already never deletes "
            "these (see RETENTION_CLASSIFICATION), so the 180-day floor is trivially satisfied "
            "today by 'never delete at all', not by an enforced schedule. No maximum retention "
            "is cited from any source -- do not invent an expiry job that deletes audit rows "
            "after any duration until a real maximum is sourced and approved."
        ),
    ),
}


class RetentionPolicyViolation(ValueError):
    """Raised when an operation would delete a row before its cited minimum
    retention has elapsed."""


def assert_minimum_retention_satisfied(category: str, row_age_days: float) -> None:
    """Refuse a deletion that would violate a cited minimum retention floor.

    This is a guard for future code that deletes rows programmatically (an
    expiry job, a cleanup script) -- it does not itself delete or schedule
    anything. `security.data_rights.delete_subject_data()` does not call
    this today because it already never deletes audit_events at all, which
    trivially satisfies any floor; this guard exists for whatever deletes
    rows next, so that "clean up old data" can never quietly violate a
    minimum retention requirement this project has already cited.
    """
    if category not in RETENTION_POLICIES:
        raise ValueError(f"unknown retention category: {category!r}")
    if row_age_days < 0:
        raise ValueError("row_age_days must not be negative")

    policy = RETENTION_POLICIES[category]
    if policy.minimum_retention_days is None:
        return
    if row_age_days < policy.minimum_retention_days:
        raise RetentionPolicyViolation(
            f"cannot delete a '{category}' row that is only {row_age_days:.1f} days old: "
            f"minimum retention is {policy.minimum_retention_days} days "
            f"({policy.minimum_retention_source})"
        )
