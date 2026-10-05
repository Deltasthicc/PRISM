"""add trainer_expertise

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-05 00:00:00.000000

SIH26075 PS75-07/PS75-14: a trainer's self-declared teaching expertise per
competency, the declared input to trainer-to-subject matching. See
models/trainer_expertise.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trainer_expertise',
        sa.Column('expertise_id', sa.String(), nullable=False),
        sa.Column('trainer_id', sa.String(), nullable=False),
        sa.Column('competency_id', sa.String(), nullable=False),
        sa.Column('declared_level', sa.Integer(), nullable=False),
        sa.Column('basis', sa.String(), nullable=False),
        sa.Column('basis_detail', sa.String(), nullable=False),
        sa.Column('years_teaching', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "declared_level >= 1 AND declared_level <= 5",
            name='ck_trainer_expertise_declared_level_range',
        ),
        sa.CheckConstraint(
            "basis IN ('degree', 'certification', 'experience', 'other')",
            name='ck_trainer_expertise_basis_values',
        ),
        sa.CheckConstraint('years_teaching >= 0', name='ck_trainer_expertise_years_nonnegative'),
        sa.ForeignKeyConstraint(['trainer_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('expertise_id'),
        sa.UniqueConstraint('trainer_id', 'competency_id', name='uq_trainer_expertise_trainer_competency'),
    )
    op.create_index(op.f('ix_trainer_expertise_trainer_id'), 'trainer_expertise', ['trainer_id'], unique=False)
    op.create_index(op.f('ix_trainer_expertise_competency_id'), 'trainer_expertise', ['competency_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_trainer_expertise_competency_id'), table_name='trainer_expertise')
    op.drop_index(op.f('ix_trainer_expertise_trainer_id'), table_name='trainer_expertise')
    op.drop_table('trainer_expertise')
