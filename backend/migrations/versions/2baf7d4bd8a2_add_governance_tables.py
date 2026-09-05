"""add governance tables

Revision ID: 2baf7d4bd8a2
Revises: 65bc8695fadc
Create Date: 2026-08-31 21:18:03.974424

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2baf7d4bd8a2'
down_revision: Union[str, None] = '65bc8695fadc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_EXPECTED_COLUMNS = {
    "audit_events": {
        "audit_id",
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "details",
        "created_at",
    },
    "role_targets": {
        "target_id",
        "framework_version",
        "role",
        "competency_id",
        "target_level",
        "source",
        "approved_by",
        "valid_from",
        "valid_to",
        "created_at",
    },
    "evidence_records": {
        "evidence_id",
        "player_id",
        "competency_id",
        "evidence_type",
        "value",
        "detail",
        "recorded_at",
    },
    "source_versions": {
        "source_version_id",
        "material_id",
        "version_number",
        "sha256",
        "locator",
        "created_at",
    },
}

# These track what `Base.metadata.create_all()` actually produces for these
# four tables *today*, not a frozen snapshot of what it produced when this
# migration was first written. `create_all()` always reflects whichever
# `models/*.py` code is currently deployed -- there is no versioning of a
# "legacy create_all() database"'s shape other than "current model code" --
# so a later migration that adds an index/column/FK to one of these tables
# (e.g. `6564595b3466`'s composite indexes on `role_targets`/
# `evidence_records`/`source_versions`, Package 4) must update the matching
# dict below, or `_adopt_compatible_preexisting_tables()` will incorrectly
# refuse to adopt a perfectly current, self-consistent SQLite demo file.
_EXPECTED_INDEXES = {
    "audit_events": {"ix_audit_events_created_at"},
    "role_targets": {
        "ix_role_targets_competency_id",
        "ix_role_targets_role",
        "ix_role_targets_lookup_newest",  # Package 4
    },
    "evidence_records": {
        "ix_evidence_records_competency_id",
        "ix_evidence_records_player_id",
        "ix_evidence_records_lookup_newest",  # Package 4
    },
    "source_versions": {
        "ix_source_versions_material_id",
        "ix_source_versions_sha256",
        "ix_source_versions_lookup_newest",  # Package 4
    },
}

_EXPECTED_NOT_NULL = {
    "audit_events": {"audit_id", "actor", "action", "entity_type"},
    "role_targets": {
        "target_id",
        "framework_version",
        "role",
        "competency_id",
        "target_level",
        "source",
    },
    "evidence_records": {
        "evidence_id",
        "player_id",
        "competency_id",
        "evidence_type",
    },
    "source_versions": {"source_version_id", "version_number", "sha256"},
}

_EXPECTED_TYPE_AFFINITIES = {
    "audit_events": {
        "audit_id": "String",
        "actor": "String",
        "action": "String",
        "entity_type": "String",
        "entity_id": "String",
        "details": "JSON",
        "created_at": "DateTime",
    },
    "role_targets": {
        "target_id": "String",
        "framework_version": "String",
        "role": "String",
        "competency_id": "String",
        "target_level": "Integer",
        "source": "String",
        "approved_by": "String",
        "valid_from": "DateTime",
        "valid_to": "DateTime",
        "created_at": "DateTime",
    },
    "evidence_records": {
        "evidence_id": "String",
        "player_id": "String",
        "competency_id": "String",
        "evidence_type": "String",
        "value": "Integer",
        "detail": "String",
        "recorded_at": "DateTime",
    },
    "source_versions": {
        "source_version_id": "String",
        "material_id": "String",
        "version_number": "Integer",
        "sha256": "String",
        "locator": "String",
        "created_at": "DateTime",
    },
}

_EXPECTED_PRIMARY_KEYS = {
    "audit_events": {"audit_id"},
    "role_targets": {"target_id"},
    "evidence_records": {"evidence_id"},
    "source_versions": {"source_version_id"},
}

_EXPECTED_FOREIGN_KEYS = {
    "audit_events": set(),
    "role_targets": set(),
    "evidence_records": {("player_id", "players", "player_id")},
    "source_versions": {("material_id", "learning_materials", "material_id")},
}


def _adopt_compatible_preexisting_tables() -> bool:
    """Adopt tables created by the pre-migration startup path, or fail safely."""
    inspector = sa.inspect(op.get_bind())
    expected_tables = set(_EXPECTED_COLUMNS)
    present_tables = expected_tables.intersection(inspector.get_table_names())
    if not present_tables:
        return False
    if present_tables != expected_tables:
        missing = sorted(expected_tables - present_tables)
        raise RuntimeError(
            "Refusing to adopt a partial governance schema; missing tables: "
            + ", ".join(missing)
        )

    mismatches = []
    for table_name in sorted(expected_tables):
        inspected_columns = inspector.get_columns(table_name)
        columns = {column["name"] for column in inspected_columns}
        if columns != _EXPECTED_COLUMNS[table_name]:
            mismatches.append(f"{table_name} columns")

        not_null = {
            column["name"] for column in inspected_columns if not column["nullable"]
        }
        if not_null != _EXPECTED_NOT_NULL[table_name]:
            mismatches.append(f"{table_name} nullability")

        type_affinities = {
            column["name"]: column["type"]._type_affinity.__name__
            for column in inspected_columns
        }
        if type_affinities != _EXPECTED_TYPE_AFFINITIES[table_name]:
            mismatches.append(f"{table_name} column types")

        primary_key = set(
            inspector.get_pk_constraint(table_name)["constrained_columns"]
        )
        if primary_key != _EXPECTED_PRIMARY_KEYS[table_name]:
            mismatches.append(f"{table_name} primary key")

        indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        if indexes != _EXPECTED_INDEXES[table_name]:
            mismatches.append(f"{table_name} indexes")

        foreign_keys = {
            (
                foreign_key["constrained_columns"][0],
                foreign_key["referred_table"],
                foreign_key["referred_columns"][0],
            )
            for foreign_key in inspector.get_foreign_keys(table_name)
        }
        if foreign_keys != _EXPECTED_FOREIGN_KEYS[table_name]:
            mismatches.append(f"{table_name} foreign keys")

    if mismatches:
        raise RuntimeError(
            "Refusing to adopt an incompatible pre-existing governance schema: "
            + ", ".join(mismatches)
        )
    return True


def upgrade() -> None:
    if _adopt_compatible_preexisting_tables():
        return
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('audit_events',
    sa.Column('audit_id', sa.String(), nullable=False),
    sa.Column('actor', sa.String(), nullable=False),
    sa.Column('action', sa.String(), nullable=False),
    sa.Column('entity_type', sa.String(), nullable=False),
    sa.Column('entity_id', sa.String(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('audit_id')
    )
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)
    op.create_table('role_targets',
    sa.Column('target_id', sa.String(), nullable=False),
    sa.Column('framework_version', sa.String(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('competency_id', sa.String(), nullable=False),
    sa.Column('target_level', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('approved_by', sa.String(), nullable=True),
    sa.Column('valid_from', sa.DateTime(timezone=True), nullable=True),
    sa.Column('valid_to', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('target_id')
    )
    op.create_index(op.f('ix_role_targets_competency_id'), 'role_targets', ['competency_id'], unique=False)
    op.create_index(op.f('ix_role_targets_role'), 'role_targets', ['role'], unique=False)
    op.create_table('evidence_records',
    sa.Column('evidence_id', sa.String(), nullable=False),
    sa.Column('player_id', sa.String(), nullable=False),
    sa.Column('competency_id', sa.String(), nullable=False),
    sa.Column('evidence_type', sa.String(), nullable=False),
    sa.Column('value', sa.Integer(), nullable=True),
    sa.Column('detail', sa.String(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
    sa.PrimaryKeyConstraint('evidence_id')
    )
    op.create_index(op.f('ix_evidence_records_competency_id'), 'evidence_records', ['competency_id'], unique=False)
    op.create_index(op.f('ix_evidence_records_player_id'), 'evidence_records', ['player_id'], unique=False)
    op.create_table('source_versions',
    sa.Column('source_version_id', sa.String(), nullable=False),
    sa.Column('material_id', sa.String(), nullable=True),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('sha256', sa.String(), nullable=False),
    sa.Column('locator', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['material_id'], ['learning_materials.material_id'], ),
    sa.PrimaryKeyConstraint('source_version_id')
    )
    op.create_index(op.f('ix_source_versions_material_id'), 'source_versions', ['material_id'], unique=False)
    op.create_index(op.f('ix_source_versions_sha256'), 'source_versions', ['sha256'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_source_versions_sha256'), table_name='source_versions')
    op.drop_index(op.f('ix_source_versions_material_id'), table_name='source_versions')
    op.drop_table('source_versions')
    op.drop_index(op.f('ix_evidence_records_player_id'), table_name='evidence_records')
    op.drop_index(op.f('ix_evidence_records_competency_id'), table_name='evidence_records')
    op.drop_table('evidence_records')
    op.drop_index(op.f('ix_role_targets_role'), table_name='role_targets')
    op.drop_index(op.f('ix_role_targets_competency_id'), table_name='role_targets')
    op.drop_table('role_targets')
    op.drop_index(op.f('ix_audit_events_created_at'), table_name='audit_events')
    op.drop_table('audit_events')
    # ### end Alembic commands ###
