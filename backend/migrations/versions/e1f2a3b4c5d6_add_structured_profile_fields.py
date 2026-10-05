"""add structured profile fields to learner_profiles

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-05 00:00:00.000000

SIH26075 PS75-02: qualifications, work experience, interests, skills and
certificates earned elsewhere, as validated JSON lists. All self-declared;
existing rows read as empty lists.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("qualifications", "work_experience", "interests", "skills", "external_certificates")


def upgrade() -> None:
    with op.batch_alter_table("learner_profiles") as batch_op:
        for name in _COLUMNS:
            batch_op.add_column(sa.Column(name, sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("learner_profiles") as batch_op:
        for name in reversed(_COLUMNS):
            batch_op.drop_column(name)
