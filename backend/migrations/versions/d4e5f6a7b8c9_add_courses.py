"""add courses

Revision ID: d4e5f6a7b8c9
Revises: b1c2d3e4f5a6
Create Date: 2026-09-30 00:00:00.000000

A real, trainer-authored course table (SIH26075 CC-03/CC-06/CC-09). See
models/course.py's docstring for how this relates to (and deliberately does
not replace) the pre-existing "igot"/"nssta" CourseEnrollment provider rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'courses',
        sa.Column('course_id', sa.String(), nullable=False),
        sa.Column('trainer_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=False),
        sa.Column('competency_id', sa.String(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['trainer_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('course_id'),
    )
    op.create_index(op.f('ix_courses_trainer_id'), 'courses', ['trainer_id'], unique=False)
    op.create_index(op.f('ix_courses_competency_id'), 'courses', ['competency_id'], unique=False)
    op.create_index(op.f('ix_courses_is_published'), 'courses', ['is_published'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_courses_is_published'), table_name='courses')
    op.drop_index(op.f('ix_courses_competency_id'), table_name='courses')
    op.drop_index(op.f('ix_courses_trainer_id'), table_name='courses')
    op.drop_table('courses')
