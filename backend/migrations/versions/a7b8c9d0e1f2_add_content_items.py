"""add content_items

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-05 00:00:00.000000

SIH26075 PS75-10: trainer content library (recorded lectures,
presentations, study materials). See models/content_library.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_items',
        sa.Column('content_id', sa.String(), nullable=False),
        sa.Column('trainer_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('course_id', sa.String(), nullable=True),
        sa.Column('original_filename', sa.String(), nullable=False),
        sa.Column('stored_name', sa.String(), nullable=False),
        sa.Column('media_type', sa.String(), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('recorded_lecture', 'presentation', 'study_material')",
            name='ck_content_items_kind',
        ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
        sa.ForeignKeyConstraint(['trainer_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('content_id'),
        sa.UniqueConstraint('stored_name'),
    )
    op.create_index(op.f('ix_content_items_trainer_id'), 'content_items', ['trainer_id'], unique=False)
    op.create_index(op.f('ix_content_items_course_id'), 'content_items', ['course_id'], unique=False)
    op.create_index(op.f('ix_content_items_is_published'), 'content_items', ['is_published'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_content_items_is_published'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_course_id'), table_name='content_items')
    op.drop_index(op.f('ix_content_items_trainer_id'), table_name='content_items')
    op.drop_table('content_items')
