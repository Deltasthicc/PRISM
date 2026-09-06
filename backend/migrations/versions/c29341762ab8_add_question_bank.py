"""add question bank

Revision ID: c29341762ab8
Revises: 6564595b3466
Create Date: 2026-09-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c29341762ab8'
down_revision: Union[str, None] = '6564595b3466'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('question_bank_items',
    sa.Column('item_id', sa.String(), nullable=False),
    sa.Column('curriculum_slug', sa.String(), nullable=False),
    sa.Column('competency_id', sa.String(), nullable=False),
    sa.Column('difficulty', sa.String(), nullable=False),
    sa.Column('question', sa.String(), nullable=False),
    sa.Column('options', sa.JSON(), nullable=False),
    sa.Column('answer_index', sa.Integer(), nullable=False),
    sa.Column('explanation', sa.String(), nullable=False),
    sa.Column('bloom_level', sa.String(), nullable=True),
    sa.Column('source_name', sa.String(), nullable=False),
    sa.Column('source_excerpt', sa.String(), nullable=False),
    sa.Column('source_url', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('item_id'),
    )
    op.create_index(op.f('ix_question_bank_items_curriculum_slug'), 'question_bank_items', ['curriculum_slug'], unique=False)
    op.create_index(op.f('ix_question_bank_items_competency_id'), 'question_bank_items', ['competency_id'], unique=False)

    op.create_table('question_bank_attempts',
    sa.Column('attempt_id', sa.String(), nullable=False),
    sa.Column('player_id', sa.String(), nullable=False),
    sa.Column('item_id', sa.String(), nullable=False),
    sa.Column('selected_index', sa.Integer(), nullable=False),
    sa.Column('correct', sa.Integer(), nullable=False),
    sa.Column('answered_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['question_bank_items.item_id'], ),
    sa.PrimaryKeyConstraint('attempt_id'),
    sa.UniqueConstraint('player_id', 'item_id', name='uq_question_bank_attempt_player_item'),
    )
    op.create_index(op.f('ix_question_bank_attempts_player_id'), 'question_bank_attempts', ['player_id'], unique=False)
    op.create_index(op.f('ix_question_bank_attempts_item_id'), 'question_bank_attempts', ['item_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_question_bank_attempts_item_id'), table_name='question_bank_attempts')
    op.drop_index(op.f('ix_question_bank_attempts_player_id'), table_name='question_bank_attempts')
    op.drop_table('question_bank_attempts')
    op.drop_index(op.f('ix_question_bank_items_competency_id'), table_name='question_bank_items')
    op.drop_index(op.f('ix_question_bank_items_curriculum_slug'), table_name='question_bank_items')
    op.drop_table('question_bank_items')
