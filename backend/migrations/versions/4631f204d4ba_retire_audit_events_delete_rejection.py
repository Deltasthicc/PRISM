"""retire audit events delete rejection

Revision ID: 4631f204d4ba
Revises: 036de46dd515
Create Date: 2026-09-02 11:22:47.185316

Package U's migration (036de46dd515) made PostgreSQL reject BOTH UPDATE and
DELETE against audit_events. That was a real integrated defect, found by
Codex's cold immutable audit (LANE2_SYNC.md, 2026-09-01): audit_events is
the only category `scripts/retention_job.py` has ever registered
(`CATEGORY_TABLES`), so the unconditional DELETE rejection makes the
retention-enforcement job permanently unusable for its one real target the
moment any cited maximum retention is ever added -- the two Lane 2
mechanisms directly contradicted each other. It only went unnoticed because
`security.retention.RETENTION_POLICIES` currently cites no maximum for any
category, so the job is a provable no-op today; the defect was latent, not
absent.

This migration retires ONLY the DELETE rejection, restoring the ability to
run lawful, cited retention enforcement against audit_events. The UPDATE
rejection stays: nothing in this project ever needs to update an audit
event after it is written, and blocking UPDATE at the database level closes
a real gap (a bug or direct-database-access mutation bypassing the app
layer) with no cost to any real workflow.

Naming this precisely, per the same audit: a trigger that blocks UPDATE but
allows DELETE is NOT "append-only" -- append-only means rows are never
removed either. The only genuine append-only guarantee this project makes
is at the application layer: `security.data_rights.delete_subject_data()`
and `RETENTION_CLASSIFICATION` never delete audit_events on a subject
request, full stop. The database-level trigger below is a narrower,
honestly-scoped safety net -- "no direct mutation of an existing audit row"
-- not a substitute for that application-layer boundary, and deletion
through the dedicated, cited, minimum-retention-checked retention job
remains possible and intentional.

Scope carried over unchanged from 036de46dd515: this is still a bug-catching
safety net for the application's own connection role, not a security
boundary against a malicious actor with the app's own database credentials
(the OWNER role can DROP/DISABLE this trigger). SQLite is still out of
scope and this migration is a genuine no-op there.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4631f204d4ba'
down_revision: Union[str, None] = '036de46dd515'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("DROP TRIGGER IF EXISTS audit_events_reject_delete ON audit_events;")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION audit_events_reject_mutation()
        RETURNS TRIGGER AS $$
        BEGIN
            RAISE EXCEPTION
                'audit_events rows must not be modified after insert (see '
                'docs/contracts/data-authorization.md section 6.3): % is not permitted. '
                'This database-level check blocks UPDATE only -- deletion remains '
                'possible and is governed by scripts/retention_job.py under a cited '
                'maximum retention, not by this trigger.',
                TG_OP;
        END;
        $$ LANGUAGE plpgsql;
        """
    )


def downgrade() -> None:
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
        CREATE TRIGGER audit_events_reject_delete
        BEFORE DELETE ON audit_events
        FOR EACH ROW EXECUTE FUNCTION audit_events_reject_mutation();
        """
    )
