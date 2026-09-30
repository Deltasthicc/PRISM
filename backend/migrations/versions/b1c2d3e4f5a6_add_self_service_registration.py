"""add self-service registration columns to identity_bindings

Revision ID: b1c2d3e4f5a6
Revises: 951dbad5f9f6
Create Date: 2026-09-30 00:00:00.000000

SIH26075 CC-01/CC-10: secure signup with a requested Trainee/Trainer role,
plus admin approval before a new account can act. See
`security/rbac.py::create_self_service_registration` /
`decide_self_registration` and `routes/registration.py`.

All five new columns are nullable and purely additive. Nothing here changes
`identity_bindings.active`'s existing meaning or any existing enforcement
path (`resolve_bound_principal`, `require_principal`) -- a binding created
through the pre-existing admin-only `create_identity_binding()` path leaves
all five NULL, exactly as before this migration. Only a new self-service
registration row populates `requested_role` and starts `active=False`; an
admin decision later stamps the remaining four columns via a dedicated
function, never by writing to `active` directly outside the existing,
unmodified `reactivate_identity_binding()`.

Batch mode (not a plain ALTER TABLE) for the same reason as
640603a37f2f_add_players_preferred_mode.py: SQLite cannot add a CHECK
constraint outside Alembic's copy-and-move batch strategy, and real column
+ constraint parity on both dialects is what keeps `alembic check` clean.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '951dbad5f9f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ROLE_CONSTRAINT_NAME = "ck_identity_bindings_requestable_role"
_DECISION_CONSTRAINT_NAME = "ck_identity_bindings_registration_decision"
# Historical snapshot, deliberately not imported from
# models.identity.SELF_SERVICE_REQUESTABLE_ROLES -- see
# 640603a37f2f's identical rationale for keeping migration DDL reproducible
# independent of a mutable application constant.
_REQUESTABLE_ROLES = ("learner", "trainer")
_DECISIONS = ("approved", "rejected")


def upgrade() -> None:
    with op.batch_alter_table("identity_bindings") as batch_op:
        batch_op.add_column(sa.Column("requested_role", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("registration_notes", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("registration_decision", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("registration_reviewed_by", sa.String(), nullable=True))
        batch_op.add_column(
            sa.Column("registration_reviewed_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_check_constraint(
            _ROLE_CONSTRAINT_NAME,
            "requested_role IS NULL OR requested_role IN ({})".format(
                ", ".join(f"'{value}'" for value in _REQUESTABLE_ROLES)
            ),
        )
        batch_op.create_check_constraint(
            _DECISION_CONSTRAINT_NAME,
            "registration_decision IS NULL OR registration_decision IN ({})".format(
                ", ".join(f"'{value}'" for value in _DECISIONS)
            ),
        )


def downgrade() -> None:
    with op.batch_alter_table("identity_bindings") as batch_op:
        batch_op.drop_constraint(_DECISION_CONSTRAINT_NAME, type_="check")
        batch_op.drop_constraint(_ROLE_CONSTRAINT_NAME, type_="check")
        batch_op.drop_column("registration_reviewed_at")
        batch_op.drop_column("registration_reviewed_by")
        batch_op.drop_column("registration_decision")
        batch_op.drop_column("registration_notes")
        batch_op.drop_column("requested_role")
