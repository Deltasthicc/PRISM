"""add generated_quizzes.best_score/last_attempted_at

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-09-10 00:00:00.000000

Adds a denormalized best-attempt summary to `generated_quizzes` for the new
scored "take this quiz" flow (routes/learning_content.py's
POST /learning/quiz/{quiz_id}/submit). Deliberately NOT wired into
AccuracyHistory/the real competency vector -- a generated quiz's
`competency` field is free text, not a real curriculum competency_id, so
this stays a real, honest per-quiz score rather than fabricated curriculum
evidence.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f4a5b6c7d8e9'
down_revision: Union[str, None] = 'e3f4a5b6c7d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("generated_quizzes") as batch_op:
        batch_op.add_column(sa.Column("best_score", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("generated_quizzes") as batch_op:
        batch_op.drop_column("last_attempted_at")
        batch_op.drop_column("best_score")
