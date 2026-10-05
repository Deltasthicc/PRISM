"""add announcements

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-05 00:00:00.000000

SIH26075 PS75-13: admin-authored announcements for the in-app home feed.
See models/announcement.py.
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
        'announcements',
        sa.Column('announcement_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('body', sa.String(length=4000), nullable=False),
        sa.Column('kind', sa.String(), nullable=False),
        sa.Column('audience', sa.String(), nullable=False),
        sa.Column('created_by', sa.String(), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('announcement', 'achievement', 'new_content')",
            name='ck_announcements_kind',
        ),
        sa.CheckConstraint(
            "audience IN ('all', 'learner', 'trainer')",
            name='ck_announcements_audience',
        ),
        sa.PrimaryKeyConstraint('announcement_id'),
    )
    op.create_index(
        'ix_announcements_published', 'announcements', ['is_published', 'published_at'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_announcements_published', table_name='announcements')
    op.drop_table('announcements')
