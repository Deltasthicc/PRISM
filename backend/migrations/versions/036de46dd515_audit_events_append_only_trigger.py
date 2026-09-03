"""audit events append only trigger

Revision ID: 036de46dd515
Revises: cf4271f204a3
Create Date: 2026-09-01 22:58:48.047190

security/audit.py and models/governance.py already document AuditEvent as
append-only ("there is no update path anywhere in this module, and no
route should ever UPDATE or DELETE a row here"), but until now that was
only an application-code convention -- nothing stopped a bug in a future
caller, or anyone with direct database access using the app's own role,
from silently mutating or deleting an audit row. This migration makes
PostgreSQL itself reject any UPDATE or DELETE against audit_events.

Scope, honestly stated: this is a bug-catching safety net for the
application's own connection role, not a security boundary against a
malicious actor. The app connects as the database OWNER role
(POSTGRES_USER in docker-compose.dev.yml), which can DROP or DISABLE this
trigger -- a compromised or malicious holder of the app's own database
credentials is not stopped by it. It does not add actor/purpose context,
does not survive a transaction rollback (Postgres triggers are not
autonomous transactions), and is not a compliance or "tamper-proof"
claim -- see LANE2_SYNC.md for the independent-audit review that scoped
this down from the originally proposed "capture every table's writes with
full context" trigger design, which this project rejected as unproven and
partially fabricated.

SQLite (the documented local zero-setup demo profile) has no equivalent
mechanism reachable through Alembic's cross-dialect API for this shape of
trigger and is explicitly out of scope here, the same way it is exempt
from the PostgreSQL-only migration-gated-startup policy in db/database.py.
This migration is a genuine no-op on SQLite so the shared Alembic chain
(including test_core_migrations.py, which runs upgrade/downgrade against
a real SQLite file) still passes.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '036de46dd515'
down_revision: Union[str, None] = 'cf4271f204a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_reject_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_events is append-only: % is not permitted by database policy',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_reject_update
        BEFORE UPDATE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_reject_mutation();
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_events_reject_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_reject_mutation();
        """
    )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS audit_events_reject_update ON audit_events;")
    op.execute("DROP TRIGGER IF EXISTS audit_events_reject_delete ON audit_events;")
    op.execute("DROP FUNCTION IF EXISTS audit_events_reject_mutation();")
