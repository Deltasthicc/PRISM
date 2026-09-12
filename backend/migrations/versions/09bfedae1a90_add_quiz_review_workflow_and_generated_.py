"""add quiz review workflow and generated quiz attempts

Revision ID: 09bfedae1a90
Revises: 8623dd43be9d
Create Date: 2026-09-12 13:59:26.000170

Adds the real trainer review/approval workflow (routes/quiz_review.py) --
every pre-existing quiz backfills as 'private' via the server default
below, exactly matching current behavior (only its own creator could ever
see it) so this migration changes no learner-visible behavior by itself.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09bfedae1a90'
down_revision: Union[str, None] = '8623dd43be9d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('generated_quiz_attempts',
    sa.Column('attempt_id', sa.String(), nullable=False),
    sa.Column('quiz_id', sa.String(), nullable=False),
    sa.Column('player_id', sa.String(), nullable=False),
    sa.Column('correct_count', sa.Integer(), nullable=False),
    sa.Column('total_questions', sa.Integer(), nullable=False),
    sa.Column('weighted_score', sa.Float(), nullable=False),
    sa.Column('attempted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
    sa.ForeignKeyConstraint(['quiz_id'], ['generated_quizzes.quiz_id'], ),
    sa.PrimaryKeyConstraint('attempt_id')
    )
    op.create_index(op.f('ix_generated_quiz_attempts_player_id'), 'generated_quiz_attempts', ['player_id'], unique=False)
    op.create_index(op.f('ix_generated_quiz_attempts_quiz_id'), 'generated_quiz_attempts', ['quiz_id'], unique=False)
    # server_default backfills every pre-existing row as 'private' -- without
    # it, adding a NOT NULL column to a table that may already have rows
    # fails outright (and on SQLite silently would not, masking the same
    # real problem on Postgres in CI/production).
    op.add_column('generated_quizzes', sa.Column('review_status', sa.String(), nullable=False, server_default='private'))
    op.add_column('generated_quizzes', sa.Column('submitted_for_review_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('generated_quizzes', sa.Column('reviewed_by', sa.String(), nullable=True))
    op.add_column('generated_quizzes', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('generated_quizzes', sa.Column('reviewer_notes', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('generated_quizzes', 'reviewer_notes')
    op.drop_column('generated_quizzes', 'reviewed_at')
    op.drop_column('generated_quizzes', 'reviewed_by')
    op.drop_column('generated_quizzes', 'submitted_for_review_at')
    op.drop_column('generated_quizzes', 'review_status')
    op.drop_index(op.f('ix_generated_quiz_attempts_quiz_id'), table_name='generated_quiz_attempts')
    op.drop_index(op.f('ix_generated_quiz_attempts_player_id'), table_name='generated_quiz_attempts')
    op.drop_table('generated_quiz_attempts')
