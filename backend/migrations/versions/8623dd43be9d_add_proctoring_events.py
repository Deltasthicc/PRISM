"""add proctoring_events

Revision ID: 8623dd43be9d
Revises: c456ff178c61
Create Date: 2026-09-12 00:30:06.298297

Persists real exam-integrity signals (face count, phone detection, tab
switch, fullscreen exit) that the client already judged as violations --
see models/proctoring.py for the full rationale and the privacy boundary
(no video/image ever reaches the backend, only the resulting event).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8623dd43be9d'
down_revision: Union[str, None] = 'c456ff178c61'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('proctoring_events',
    sa.Column('event_id', sa.String(), nullable=False),
    sa.Column('player_id', sa.String(), nullable=False),
    sa.Column('attempt_id', sa.String(), nullable=False),
    sa.Column('violation_type', sa.String(), nullable=False),
    sa.Column('detail', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
    sa.PrimaryKeyConstraint('event_id')
    )
    op.create_index(op.f('ix_proctoring_events_attempt_id'), 'proctoring_events', ['attempt_id'], unique=False)
    op.create_index(op.f('ix_proctoring_events_created_at'), 'proctoring_events', ['created_at'], unique=False)
    op.create_index(op.f('ix_proctoring_events_player_id'), 'proctoring_events', ['player_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_proctoring_events_player_id'), table_name='proctoring_events')
    op.drop_index(op.f('ix_proctoring_events_created_at'), table_name='proctoring_events')
    op.drop_index(op.f('ix_proctoring_events_attempt_id'), table_name='proctoring_events')
    op.drop_table('proctoring_events')
