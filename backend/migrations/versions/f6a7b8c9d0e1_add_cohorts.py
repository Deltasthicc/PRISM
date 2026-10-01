"""add cohorts and cohort_memberships

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-01 00:00:00.000000

SIH26075 CC-08/PS75-09: real trainer/cohort assignment, closing the gap
security/rbac.py's trainer permission comment has documented since Lane 2
first wrote it. See models/cohort.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cohorts',
        sa.Column('cohort_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('trainer_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['trainer_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('cohort_id'),
    )
    op.create_index(op.f('ix_cohorts_trainer_id'), 'cohorts', ['trainer_id'], unique=False)

    op.create_table(
        'cohort_memberships',
        sa.Column('membership_id', sa.String(), nullable=False),
        sa.Column('cohort_id', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('added_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['cohort_id'], ['cohorts.cohort_id'], ),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('membership_id'),
        sa.UniqueConstraint('cohort_id', 'player_id', name='uq_cohort_membership_cohort_player'),
    )
    op.create_index(op.f('ix_cohort_memberships_cohort_id'), 'cohort_memberships', ['cohort_id'], unique=False)
    op.create_index(op.f('ix_cohort_memberships_player_id'), 'cohort_memberships', ['player_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cohort_memberships_player_id'), table_name='cohort_memberships')
    op.drop_index(op.f('ix_cohort_memberships_cohort_id'), table_name='cohort_memberships')
    op.drop_table('cohort_memberships')
    op.drop_index(op.f('ix_cohorts_trainer_id'), table_name='cohorts')
    op.drop_table('cohorts')
