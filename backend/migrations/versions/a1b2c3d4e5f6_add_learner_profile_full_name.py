"""add learner_profiles full_name

Revision ID: a1b2c3d4e5f6
Revises: c29341762ab8
Create Date: 2026-09-09 00:00:00.000000

Adds `learner_profiles.full_name`. Previously the officer's display name was
entirely front-end-fabricated ("Dr. Rajesh Sharma" hardcoded in
CreateProfilePage.jsx) and never persisted -- this makes it a real, dynamic,
per-learner field like every other profile column.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c29341762ab8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable, no server-side default -- matches every sibling column on
    # this table (designation, department, etc.), all of which rely on the
    # ORM-level Python default ("") applied on insert, not a DB-level one.
    # An existing row backfilled by this ALTER TABLE gets NULL, which every
    # reader already treats the same as "" (see AcademyHub.jsx's
    # EMPTY_PROFILE spread and CompetencyQuizPage.jsx's `|| ''` fallbacks).
    with op.batch_alter_table("learner_profiles") as batch_op:
        batch_op.add_column(sa.Column("full_name", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("learner_profiles") as batch_op:
        batch_op.drop_column("full_name")
