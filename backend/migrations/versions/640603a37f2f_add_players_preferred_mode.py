"""add players preferred_mode

Revision ID: 640603a37f2f
Revises: 4631f204d4ba
Create Date: 2026-09-02 20:42:29.284017

Adds `players.preferred_mode`, the base scaffold for the team's two-mode
decision (WhatsApp thread, 2 Sep 2026): a non-gamified, KCM/Mission
Karmayogi-oriented "professional" mode as the default/base experience, with
the existing dungeon/XP/combat layer preserved as an explicit "quest"
opt-in -- never the default a government-official learner lands in.

This is a presentation/audience discriminator only, never an authorization
decision -- see models/enums.py's `LearningMode` docstring. It does not
gate any route, permission or competency-engine behavior; the gap
analysis/adaptive-assessment engine runs identically regardless of this
value. Which curricula are offered per mode is Lane 3's decision
(`services/curricula.py`), not encoded here; which route/page a learner
lands on is Lane 1/5's decision, not encoded here either. Lane 2 only
stores the value.

A plain `String` column with a `CHECK` constraint (not a native PostgreSQL
`ENUM` type) so a future third mode is a cheap, ordinary migration --
widening a `CHECK` constraint's allowed set, not the more invasive
`ALTER TYPE ... ADD VALUE` a native enum would need.

`server_default` backfills every existing row to "professional" at
ADD COLUMN time -- the correct default for a government-facing platform
where the professional workspace, not the game, is the base product.

Unlike 036de46dd515/4631f204d4ba's PostgreSQL-only trigger (which has no
SQLite equivalent at all, so those migrations dialect-gate to a no-op),
this migration runs for real on both dialects via Alembic's batch mode --
SQLite's own ALTER TABLE cannot add a CHECK constraint directly, but batch
mode's copy-and-move strategy can. Real parity here (not a SQLite no-op
paired with `ensure_columns()`) is what keeps `alembic check` clean on a
fresh SQLite database too, since -- unlike a trigger -- an added column is
part of SQLAlchemy's own comparable table metadata, so any gap between
what this migration creates and what the ORM model declares is a real,
autogenerate-detectable drift on every dialect, not just PostgreSQL.
`db/database.py`'s `ensure_columns()` (called from `main.py`'s startup)
still separately covers a pre-existing SQLite demo file created before this
migration existed, since that file was never migrated through Alembic to
begin with.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models.enums import DEFAULT_LEARNING_MODE, LEARNING_MODE_VALUES


# revision identifiers, used by Alembic.
revision: str = '640603a37f2f'
down_revision: Union[str, None] = '4631f204d4ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT_NAME = "ck_players_preferred_mode_known_value"


def upgrade() -> None:
    allowed = ", ".join(f"'{value}'" for value in LEARNING_MODE_VALUES)
    with op.batch_alter_table("players") as batch_op:
        batch_op.add_column(
            sa.Column(
                "preferred_mode",
                sa.String(),
                nullable=False,
                server_default=DEFAULT_LEARNING_MODE,
            )
        )
        batch_op.create_check_constraint(
            _CONSTRAINT_NAME,
            f"preferred_mode IN ({allowed})",
        )


def downgrade() -> None:
    with op.batch_alter_table("players") as batch_op:
        batch_op.drop_constraint(_CONSTRAINT_NAME, type_="check")
        batch_op.drop_column("preferred_mode")
