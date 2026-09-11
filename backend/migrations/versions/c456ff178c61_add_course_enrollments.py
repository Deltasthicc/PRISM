"""add course_enrollments

Revision ID: c456ff178c61
Revises: f4a5b6c7d8e9
Create Date: 2026-09-11 00:00:00.000000

Tracks a real enroll/complete lifecycle for services/learning_catalog.py's
recommend_courses() output, which was computed correctly but never actually
reachable by a learner -- see models/course_enrollment.py for the full
rationale.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c456ff178c61'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('course_enrollments',
    sa.Column('enrollment_id', sa.String(), nullable=False),
    sa.Column('player_id', sa.String(), nullable=False),
    sa.Column('course_id', sa.String(), nullable=False),
    sa.Column('provider', sa.String(), nullable=False),
    sa.Column('competency_id', sa.String(), nullable=False),
    sa.Column('title', sa.String(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('enrolled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
    sa.PrimaryKeyConstraint('enrollment_id'),
    sa.UniqueConstraint('player_id', 'course_id', name='uq_course_enrollment_player_course'),
    )
    op.create_index(op.f('ix_course_enrollments_player_id'), 'course_enrollments', ['player_id'], unique=False)
    op.create_index(op.f('ix_course_enrollments_course_id'), 'course_enrollments', ['course_id'], unique=False)
    op.create_index(op.f('ix_course_enrollments_competency_id'), 'course_enrollments', ['competency_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_course_enrollments_competency_id'), table_name='course_enrollments')
    op.drop_index(op.f('ix_course_enrollments_course_id'), table_name='course_enrollments')
    op.drop_index(op.f('ix_course_enrollments_player_id'), table_name='course_enrollments')
    op.drop_table('course_enrollments')
