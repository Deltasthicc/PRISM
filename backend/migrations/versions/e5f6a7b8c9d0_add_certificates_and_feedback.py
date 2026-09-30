"""add certificates and course_feedback

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-30 00:00:00.000000

SIH26075 CC-02/CC-05/CC-11: real completion certificates (issued
automatically in routes/course_enrollment.py's complete() for an internal
course) and one-per-(trainee, course) feedback with real update-in-place
semantics. See models/certificate.py and models/feedback.py.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'certificates',
        sa.Column('certificate_id', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('course_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('verification_code', sa.String(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked', sa.Boolean(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_reason', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
        sa.PrimaryKeyConstraint('certificate_id'),
    )
    op.create_index(op.f('ix_certificates_player_id'), 'certificates', ['player_id'], unique=False)
    # A single unique index, not a separate table-level UniqueConstraint
    # plus an index -- matching models/certificate.py's
    # `Column(unique=True, index=True)` exactly, which SQLAlchemy resolves
    # to one unique Index, not both. The two-object version drifted from
    # the ORM model on PostgreSQL (caught by
    # test_alembic_check_reports_clean_after_upgrade_on_postgresql).
    op.create_index(op.f('ix_certificates_verification_code'), 'certificates', ['verification_code'], unique=True)

    op.create_table(
        'course_feedback',
        sa.Column('feedback_id', sa.String(), nullable=False),
        sa.Column('player_id', sa.String(), nullable=False),
        sa.Column('course_id', sa.String(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=False),
        sa.Column('comment', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ),
        sa.ForeignKeyConstraint(['course_id'], ['courses.course_id'], ),
        sa.PrimaryKeyConstraint('feedback_id'),
        sa.UniqueConstraint('player_id', 'course_id', name='uq_course_feedback_player_course'),
        sa.CheckConstraint('rating >= 1 AND rating <= 5', name='ck_course_feedback_rating_range'),
    )
    op.create_index(op.f('ix_course_feedback_player_id'), 'course_feedback', ['player_id'], unique=False)
    op.create_index(op.f('ix_course_feedback_course_id'), 'course_feedback', ['course_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_course_feedback_course_id'), table_name='course_feedback')
    op.drop_index(op.f('ix_course_feedback_player_id'), table_name='course_feedback')
    op.drop_table('course_feedback')
    op.drop_index(op.f('ix_certificates_verification_code'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_player_id'), table_name='certificates')
    op.drop_table('certificates')
