"""add dsa_submissions

Revision ID: d2e3f4a5b6c7
Revises: a1b2c3d4e5f6
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd2e3f4a5b6c7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('dsa_submissions',
    sa.Column('submission_id', sa.String(), nullable=False),
    sa.Column('player_id', sa.String(), nullable=False),
    sa.Column('problem_id', sa.String(), nullable=False),
    sa.Column('competency_id', sa.String(), nullable=False),
    sa.Column('difficulty', sa.String(), nullable=False),
    sa.Column('code', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('passed_count', sa.Integer(), nullable=True),
    sa.Column('total_count', sa.Integer(), nullable=True),
    sa.Column('first_failure', sa.JSON(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
    sa.PrimaryKeyConstraint('submission_id'),
    )
    op.create_index(op.f('ix_dsa_submissions_player_id'), 'dsa_submissions', ['player_id'], unique=False)
    op.create_index(op.f('ix_dsa_submissions_problem_id'), 'dsa_submissions', ['problem_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_dsa_submissions_problem_id'), table_name='dsa_submissions')
    op.drop_index(op.f('ix_dsa_submissions_player_id'), table_name='dsa_submissions')
    op.drop_table('dsa_submissions')
