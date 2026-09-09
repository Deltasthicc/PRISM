"""add dsa_submissions.language

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-09-09 00:00:00.000000

Adds `dsa_submissions.language` now that the sandbox judges Python, Java,
C++, C# and JavaScript submissions (services/dsa_lang_gen.py), not just
Python -- every submission needs to record which language it was written in
for the record to be a complete, honest audit trail.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, None] = 'd2e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NOT NULL with a server_default so this matches
    # models.dsa_submission.DsaSubmission.language exactly (nullable=False)
    # -- `alembic check` compares the model against the live schema, and a
    # nullable column here would drift from that model forever.
    with op.batch_alter_table("dsa_submissions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "language", sa.String(), nullable=False, server_default=sa.text("'python'")
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("dsa_submissions") as batch_op:
        batch_op.drop_column("language")
