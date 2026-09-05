"""Tests for security/retention.py -- Package L."""
from __future__ import annotations

import pytest

from security.data_rights import RETENTION_CLASSIFICATION
from security.retention import (
    RETENTION_POLICIES,
    RetentionPolicy,
    RetentionPolicyViolation,
    assert_minimum_retention_satisfied,
)


def test_every_classification_used_by_data_rights_has_a_policy():
    # Prevents drift: if data_rights.py ever introduces a new classification
    # string, this fails loudly instead of silently leaving it unregistered.
    used_classifications = set(RETENTION_CLASSIFICATION.values())
    assert used_classifications <= set(RETENTION_POLICIES)


def test_audit_events_have_the_cited_cert_in_minimum():
    policy = RETENTION_POLICIES["retain_append_only_security_log_duration_policy_pending"]
    assert policy.minimum_retention_days == 180
    assert "CERT-In" in policy.minimum_retention_source
    assert policy.maximum_retention_days is None


def test_subject_owned_categories_have_no_fabricated_duration():
    for category in (
        "delete_with_verified_subject_request",
        "scrub_with_verified_subject_request",
    ):
        policy = RETENTION_POLICIES[category]
        assert policy.minimum_retention_days is None
        assert policy.maximum_retention_days is None


def test_policy_rejects_a_duration_without_its_source():
    with pytest.raises(ValueError, match="must both be set"):
        RetentionPolicy(
            category="x", minimum_retention_days=30, minimum_retention_source=None,
            maximum_retention_days=None, maximum_retention_source=None, notes="",
        )
    with pytest.raises(ValueError, match="must both be set"):
        RetentionPolicy(
            category="x", minimum_retention_days=None, minimum_retention_source="cite",
            maximum_retention_days=None, maximum_retention_source=None, notes="",
        )


def test_policy_rejects_negative_durations():
    with pytest.raises(ValueError, match="not be negative"):
        RetentionPolicy(
            category="x", minimum_retention_days=-1, minimum_retention_source="cite",
            maximum_retention_days=None, maximum_retention_source=None, notes="",
        )


def test_policy_rejects_a_minimum_that_exceeds_the_maximum():
    with pytest.raises(ValueError, match="exceeds maximum_retention_days"):
        RetentionPolicy(
            category="x", minimum_retention_days=200, minimum_retention_source="cite",
            maximum_retention_days=100, maximum_retention_source="cite",
            notes="",
        )


def test_policy_rejects_a_boolean_duration():
    # bool is an int subclass -- True/False must not silently become a
    # 1-day/0-day retention duration.
    with pytest.raises(ValueError, match="non-boolean whole number"):
        RetentionPolicy(
            category="x", minimum_retention_days=None, minimum_retention_source=None,
            maximum_retention_days=True, maximum_retention_source="cite", notes="",
        )
    with pytest.raises(ValueError, match="non-boolean whole number"):
        RetentionPolicy(
            category="x", minimum_retention_days=False, minimum_retention_source="cite",
            maximum_retention_days=None, maximum_retention_source=None, notes="",
        )


def test_policy_rejects_a_fractional_duration():
    with pytest.raises(ValueError, match="non-boolean whole number"):
        RetentionPolicy(
            category="x", minimum_retention_days=None, minimum_retention_source=None,
            maximum_retention_days=30.5, maximum_retention_source="cite", notes="",
        )


def test_policy_rejects_an_empty_or_whitespace_category():
    with pytest.raises(ValueError, match="must not be empty"):
        RetentionPolicy(
            category="   ", minimum_retention_days=None, minimum_retention_source=None,
            maximum_retention_days=None, maximum_retention_source=None, notes="",
        )


def test_policy_rejects_an_empty_or_whitespace_source():
    with pytest.raises(ValueError, match="must not be empty"):
        RetentionPolicy(
            category="x", minimum_retention_days=30, minimum_retention_source="   ",
            maximum_retention_days=None, maximum_retention_source=None, notes="",
        )
    with pytest.raises(ValueError, match="must not be empty"):
        RetentionPolicy(
            category="x", minimum_retention_days=None, minimum_retention_source=None,
            maximum_retention_days=30, maximum_retention_source="", notes="",
        )


def test_policy_allows_empty_notes_but_not_a_non_string():
    # notes is free text and legitimately empty for some entries -- only its
    # type is enforced, not non-emptiness.
    RetentionPolicy(
        category="x", minimum_retention_days=None, minimum_retention_source=None,
        maximum_retention_days=None, maximum_retention_source=None, notes="",
    )
    with pytest.raises(ValueError, match="must be a string"):
        RetentionPolicy(
            category="x", minimum_retention_days=None, minimum_retention_source=None,
            maximum_retention_days=None, maximum_retention_source=None, notes=None,
        )


def test_real_registry_policies_still_satisfy_the_hardened_validation():
    # Every real entry in RETENTION_POLICIES must still construct cleanly
    # under the new validation -- this module-level import already exercises
    # that at collection time, but assert it explicitly too.
    for policy in RETENTION_POLICIES.values():
        assert isinstance(policy.category, str) and policy.category.strip()


def test_assert_minimum_retention_satisfied_allows_old_enough_rows():
    assert_minimum_retention_satisfied(
        "retain_append_only_security_log_duration_policy_pending", row_age_days=181
    )
    assert_minimum_retention_satisfied(
        "retain_append_only_security_log_duration_policy_pending", row_age_days=180
    )


def test_assert_minimum_retention_satisfied_blocks_too_young_rows():
    with pytest.raises(RetentionPolicyViolation, match="minimum retention is 180 days"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=179
        )
    with pytest.raises(RetentionPolicyViolation):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=0
        )


def test_assert_minimum_retention_satisfied_is_a_noop_when_no_minimum_exists():
    # Categories with no cited floor never block a deletion on age grounds.
    assert_minimum_retention_satisfied("delete_with_verified_subject_request", row_age_days=0)
    assert_minimum_retention_satisfied("scrub_with_verified_subject_request", row_age_days=0)


def test_assert_minimum_retention_satisfied_rejects_unknown_category():
    with pytest.raises(ValueError, match="unknown retention category"):
        assert_minimum_retention_satisfied("not_a_real_category", row_age_days=1000)


def test_assert_minimum_retention_satisfied_rejects_negative_age():
    with pytest.raises(ValueError, match="must not be negative"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=-1
        )


def test_assert_minimum_retention_satisfied_rejects_nan():
    # float('nan') compares False against every bound (`nan < 0` and
    # `nan < 180` are both False), so a naive comparison-only guard would
    # silently treat NaN as "old enough to delete". It must be rejected
    # outright instead.
    with pytest.raises(ValueError, match="must be finite"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=float("nan")
        )


def test_assert_minimum_retention_satisfied_rejects_infinity():
    with pytest.raises(ValueError, match="must be finite"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=float("inf")
        )
    with pytest.raises(ValueError, match="must be finite"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=float("-inf")
        )


def test_assert_minimum_retention_satisfied_rejects_bool():
    # bool is an int subclass; True/False must not be accepted as a day count.
    with pytest.raises(TypeError, match="must be a real number"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=True
        )
    with pytest.raises(TypeError, match="must be a real number"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days=False
        )


def test_assert_minimum_retention_satisfied_rejects_non_numeric():
    with pytest.raises(TypeError, match="must be a real number"):
        assert_minimum_retention_satisfied(
            "retain_append_only_security_log_duration_policy_pending", row_age_days="181"
        )


def test_assert_minimum_retention_satisfied_accepts_an_injected_policies_registry():
    # scripts.retention_job passes its own synthetic policies through here so
    # its tests can prove the deletion mechanism without adding a fabricated
    # duration to the real registry -- this must actually check the injected
    # dict, not silently fall back to the real one.
    synthetic = {
        "synthetic_category": RetentionPolicy(
            category="synthetic_category",
            minimum_retention_days=10,
            minimum_retention_source="test only",
            maximum_retention_days=None,
            maximum_retention_source=None,
            notes="",
        ),
    }
    with pytest.raises(RetentionPolicyViolation, match="minimum retention is 10 days"):
        assert_minimum_retention_satisfied("synthetic_category", 5, policies=synthetic)
    assert_minimum_retention_satisfied("synthetic_category", 15, policies=synthetic)
    # And the real registry has no "synthetic_category" at all.
    with pytest.raises(ValueError, match="unknown retention category"):
        assert_minimum_retention_satisfied("synthetic_category", 15)
