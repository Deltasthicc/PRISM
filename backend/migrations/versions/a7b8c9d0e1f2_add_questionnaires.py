"""add questionnaires, questionnaire_questions and questionnaire_attempts

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-05 00:00:00.000000

SIH26075 PS75-08: trainer-authored MCQ questionnaires with deadlines. See
models/questionnaire.py.
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
        'questionnaires',
        sa.Column('questionnaire_id', sa.String(), nullable=False),
        sa.Column('trainer_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.String(length=2000), nullable=False),
        sa.Column('audience_type', sa.String(), nullable=False),
        sa.Column('audience_id', sa.String(), nullable=False),
        sa.Column('opens_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_published', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("audience_type IN ('cohort', 'course')", name='ck_questionnaire_audience_type'),
        sa.CheckConstraint('opens_at IS NULL OR due_at > opens_at', name='ck_questionnaire_due_after_opens'),
        sa.ForeignKeyConstraint(['trainer_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('questionnaire_id'),
    )
    op.create_index(op.f('ix_questionnaires_trainer_id'), 'questionnaires', ['trainer_id'], unique=False)
    op.create_index(op.f('ix_questionnaires_audience_id'), 'questionnaires', ['audience_id'], unique=False)
    op.create_index(op.f('ix_questionnaires_is_published'), 'questionnaires', ['is_published'], unique=False)

    op.create_table(
        'questionnaire_questions',
        sa.Column('question_id', sa.String(), nullable=False),
        sa.Column('questionnaire_id', sa.String(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.String(length=1000), nullable=False),
        sa.Column('options', sa.JSON(), nullable=False),
        sa.Column('correct_index', sa.Integer(), nullable=False),
        sa.CheckConstraint('correct_index >= 0', name='ck_questionnaire_question_correct_index'),
        sa.CheckConstraint('position >= 0', name='ck_questionnaire_question_position'),
        sa.ForeignKeyConstraint(['questionnaire_id'], ['questionnaires.questionnaire_id'], ),
        sa.PrimaryKeyConstraint('question_id'),
        sa.UniqueConstraint('questionnaire_id', 'position', name='uq_questionnaire_question_position'),
    )
    op.create_index(
        op.f('ix_questionnaire_questions_questionnaire_id'),
        'questionnaire_questions',
        ['questionnaire_id'],
        unique=False,
    )

    op.create_table(
        'questionnaire_attempts',
        sa.Column('attempt_id', sa.String(), nullable=False),
        sa.Column('questionnaire_id', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('answers', sa.JSON(), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False),
        sa.Column('max_score', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('is_late', sa.Boolean(), nullable=False),
        sa.CheckConstraint('score >= 0 AND score <= max_score', name='ck_questionnaire_attempt_score'),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
        sa.ForeignKeyConstraint(['questionnaire_id'], ['questionnaires.questionnaire_id'], ),
        sa.PrimaryKeyConstraint('attempt_id'),
        sa.UniqueConstraint(
            'questionnaire_id', 'player_id', name='uq_questionnaire_attempt_questionnaire_player'
        ),
    )
    op.create_index(
        op.f('ix_questionnaire_attempts_questionnaire_id'),
        'questionnaire_attempts',
        ['questionnaire_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_questionnaire_attempts_player_id'), 'questionnaire_attempts', ['player_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_questionnaire_attempts_player_id'), table_name='questionnaire_attempts')
    op.drop_index(op.f('ix_questionnaire_attempts_questionnaire_id'), table_name='questionnaire_attempts')
    op.drop_table('questionnaire_attempts')
    op.drop_index(op.f('ix_questionnaire_questions_questionnaire_id'), table_name='questionnaire_questions')
    op.drop_table('questionnaire_questions')
    op.drop_index(op.f('ix_questionnaires_is_published'), table_name='questionnaires')
    op.drop_index(op.f('ix_questionnaires_audience_id'), table_name='questionnaires')
    op.drop_index(op.f('ix_questionnaires_trainer_id'), table_name='questionnaires')
    op.drop_table('questionnaires')
