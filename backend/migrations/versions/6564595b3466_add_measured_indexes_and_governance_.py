"""add measured indexes and governance constraints

Revision ID: 6564595b3466
Revises: 640603a37f2f
Create Date: 2026-09-04 01:41:33.273767

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "6564595b3466"
down_revision: Union[str, None] = "640603a37f2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _reject_incompatible_existing_rows() -> None:
    """Fail before DDL with a useful message instead of a backend-specific
    CHECK-constraint-violation error partway through the migration."""

    connection = op.get_bind()
    invalid_queries = {
        "role_targets.target_level outside 1..5": """
            SELECT COUNT(*) FROM role_targets
            WHERE target_level < 1 OR target_level > 5
        """,
        "role_targets invalid validity window": """
            SELECT COUNT(*) FROM role_targets
            WHERE valid_to IS NOT NULL
              AND valid_from IS NOT NULL
              AND valid_to <= valid_from
        """,
        "evidence_records unknown evidence_type": """
            SELECT COUNT(*) FROM evidence_records
            WHERE evidence_type NOT IN (
                'self_report', 'diagnostic', 'observed_practice',
                'reviewer', 'provider_imported'
            )
        """,
        "evidence_records.value outside 0..5": """
            SELECT COUNT(*) FROM evidence_records
            WHERE value IS NOT NULL AND (value < 0 OR value > 5)
        """,
        "source_versions.version_number below 1": """
            SELECT COUNT(*) FROM source_versions WHERE version_number < 1
        """,
    }
    failures = []
    for description, query in invalid_queries.items():
        count = connection.execute(sa.text(query)).scalar_one()
        if count:
            failures.append(f"{description} ({count} rows)")
    if failures:
        raise RuntimeError(
            "Cannot apply governance constraints; repair existing rows first: "
            + "; ".join(failures)
        )


def _existing_index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def _existing_check_constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {constraint["name"] for constraint in inspector.get_check_constraints(table_name)}


def upgrade() -> None:
    _reject_incompatible_existing_rows()
    inspector = sa.inspect(op.get_bind())

    # role_targets/evidence_records/source_versions are exactly the three
    # tables `2baf7d4bd8a2`'s legacy-adoption path can hand this migration a
    # pre-existing copy of, already built from *today's* model metadata
    # (which now includes these same indexes/constraints via
    # `__table_args__`) -- `Base.metadata.create_all()` always reflects
    # currently-deployed model code, so an adopted table can already have
    # exactly what this migration is about to add. Every `create_index`/
    # `create_check_constraint` call below is guarded so this migration is
    # idempotent against that adopted-with-current-schema case, not just
    # the fresh/never-create_all()'d case. `game_sessions`/`submissions`
    # have no adoption path, so their indexes are created unconditionally.
    def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
        if name not in _existing_index_names(inspector, table):
            op.create_index(name, table, columns, unique=False)

    # Every index below matches the exact WHERE/ORDER BY shape one of Lane
    # 2's db/repositories.py latest-row lookups issues, and was kept only
    # after a representative ~120k-row PostgreSQL EXPLAIN (ANALYZE, BUFFERS)
    # comparison showed a real access-path improvement (Package 4;
    # LANE2_SYNC.md carries the exact before/after planner costs) --
    # candidates that did not show a materially better plan were not added.
    _create_index_if_missing(
        "ix_competency_assessments_lookup_newest",
        "competency_assessments",
        ["player_id", "curriculum_slug", "created_at", "assessment_id"],
    )
    _create_index_if_missing(
        "ix_evidence_records_lookup_newest",
        "evidence_records",
        ["player_id", "competency_id", "evidence_type", "recorded_at", "evidence_id"],
    )
    op.create_index(
        "ix_game_sessions_player_id", "game_sessions", ["player_id"], unique=False
    )
    _create_index_if_missing(
        "ix_role_targets_lookup_newest",
        "role_targets",
        ["role", "competency_id", "valid_from", "created_at", "target_id"],
    )
    _create_index_if_missing(
        "ix_source_versions_lookup_newest",
        "source_versions",
        ["material_id", "version_number", "created_at", "source_version_id"],
    )
    op.create_index(
        "ix_submissions_player_id", "submissions", ["player_id"], unique=False
    )

    # Alembic 1.14 does not autogenerate CHECK constraints (confirmed: this
    # revision's own `alembic revision --autogenerate` run detected all six
    # indexes above but none of these five constraints); these named,
    # cross-dialect constraints are a reviewed manual addition to the
    # generated revision. Batch operations keep the same revision usable on
    # SQLite, which cannot ALTER TABLE ... ADD CONSTRAINT directly.
    # Each `batch_alter_table` block only opens (and, on SQLite, only pays
    # for the copy/rename table rebuild) when at least one of its
    # constraints is actually missing -- an adopted table that already has
    # every constraint from `create_all()` should not be rewritten for
    # nothing, and an unconditionally-opened empty batch would still risk
    # re-triggering the FK-enforcement re-check the copy step performs
    # (Package Y) for no reason.
    role_target_checks = _existing_check_constraint_names(inspector, "role_targets")
    role_target_missing = {
        "ck_role_targets_target_level_1_5": "target_level BETWEEN 1 AND 5",
        "ck_role_targets_valid_window": (
            "valid_to IS NULL OR valid_from IS NULL OR valid_to > valid_from"
        ),
    }
    role_target_missing = {
        name: expression
        for name, expression in role_target_missing.items()
        if name not in role_target_checks
    }
    if role_target_missing:
        with op.batch_alter_table("role_targets") as batch_op:
            for name, expression in role_target_missing.items():
                batch_op.create_check_constraint(name, expression)

    evidence_checks = _existing_check_constraint_names(inspector, "evidence_records")
    evidence_missing = {
        "ck_evidence_records_type": (
            "evidence_type IN ('self_report', 'diagnostic', 'observed_practice', "
            "'reviewer', 'provider_imported')"
        ),
        "ck_evidence_records_value_0_5": "value IS NULL OR value BETWEEN 0 AND 5",
    }
    evidence_missing = {
        name: expression
        for name, expression in evidence_missing.items()
        if name not in evidence_checks
    }
    if evidence_missing:
        with op.batch_alter_table("evidence_records") as batch_op:
            for name, expression in evidence_missing.items():
                batch_op.create_check_constraint(name, expression)

    if "ck_source_versions_version_positive" not in _existing_check_constraint_names(
        inspector, "source_versions"
    ):
        with op.batch_alter_table("source_versions") as batch_op:
            batch_op.create_check_constraint(
                "ck_source_versions_version_positive", "version_number >= 1"
            )


def downgrade() -> None:
    with op.batch_alter_table("source_versions") as batch_op:
        batch_op.drop_constraint(
            "ck_source_versions_version_positive", type_="check"
        )
    with op.batch_alter_table("evidence_records") as batch_op:
        batch_op.drop_constraint("ck_evidence_records_value_0_5", type_="check")
        batch_op.drop_constraint("ck_evidence_records_type", type_="check")
    with op.batch_alter_table("role_targets") as batch_op:
        batch_op.drop_constraint("ck_role_targets_valid_window", type_="check")
        batch_op.drop_constraint("ck_role_targets_target_level_1_5", type_="check")

    op.drop_index("ix_submissions_player_id", table_name="submissions")
    op.drop_index("ix_source_versions_lookup_newest", table_name="source_versions")
    op.drop_index("ix_role_targets_lookup_newest", table_name="role_targets")
    op.drop_index("ix_game_sessions_player_id", table_name="game_sessions")
    op.drop_index("ix_evidence_records_lookup_newest", table_name="evidence_records")
    op.drop_index(
        "ix_competency_assessments_lookup_newest", table_name="competency_assessments"
    )
