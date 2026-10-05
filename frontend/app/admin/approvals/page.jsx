'use client';

import { useCallback, useEffect, useState } from 'react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { registrationAdmin } from '@/lib/api/registrationAdmin';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Panel from '@/components/ui/Panel';

// Admin review of self-service registrations (PS75-11). Not role-gated in the
// UI: the list and decision calls require organization_admin on the server and
// answer 403 to anyone else, which is shown below as an error.
//
// Approving activates the local account binding only. It does not create or
// elevate a role in the identity provider, so the page says so next to every
// request: an approved person with no matching role granted there can sign in
// but has no permissions.

const ROLE_LABEL = { learner: 'Trainee', trainer: 'Trainer' };

export default function AdminApprovalsPage() {
  const { ready } = useRequireAuth();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [rowErrors, setRowErrors] = useState({});
  const [notes, setNotes] = useState({});
  const [lastDecision, setLastDecision] = useState('');

  const refresh = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    try {
      setRows((await registrationAdmin.listPending()) || []);
    } catch (cause) {
      setLoadError(
        cause.code === 403
          ? 'Your account is not allowed to review registrations. This needs the organization administrator role.'
          : cause.message || 'Could not load pending registrations.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ready) refresh();
  }, [ready, refresh]);

  async function decide(row, decision) {
    setBusyId(row.binding_id);
    setRowErrors((current) => ({ ...current, [row.binding_id]: '' }));
    try {
      await registrationAdmin.decide(row.binding_id, decision, notes[row.binding_id] || '');
      setLastDecision(
        `${decision === 'approved' ? 'Approved' : 'Rejected'} ${row.full_name || row.username || 'the request'}.`
      );
      await refresh();
    } catch (cause) {
      setRowErrors((current) => ({
        ...current,
        [row.binding_id]:
          cause.code === 404
            ? 'This request was already decided or no longer exists. Refresh to see the current list.'
            : cause.message || 'The decision could not be saved.',
      }));
    } finally {
      setBusyId(null);
    }
  }

  if (!ready || loading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading registrations...</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Badge tone="accent">Administration</Badge>
        <h1 className="font-sans text-lg font-bold text-[#00236f] mt-3">Registration approvals</h1>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-3xl">
          People who signed in with the organization account and asked to join. Details below are
          self-declared and unverified. Approving activates the account here; the matching role must
          also be granted to the same identity-provider account, otherwise the person has no
          permissions.
        </p>
      </header>

      <div aria-live="polite" className="font-sans text-sm text-[#0d3b12]">
        {lastDecision}
      </div>

      {loadError ? (
        <div role="alert" className="flex flex-col items-start gap-3">
          <p className="font-sans text-sm text-[#b3261e]">{loadError}</p>
          <Button variant="ghost" onClick={refresh}>
            Retry
          </Button>
        </div>
      ) : rows.length === 0 ? (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">No registrations are waiting for a decision.</p>
        </Panel>
      ) : (
        <ul className="flex flex-col gap-4">
          {rows.map((row) => {
            const who = row.full_name || row.username || 'Unnamed applicant';
            const busy = busyId === row.binding_id;
            return (
              <li key={row.binding_id}>
                <Panel>
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="font-sans text-base font-bold text-[#131b2e]">{who}</h2>
                      <p className="font-sans text-xs text-[#757682] mt-1">
                        Username: {row.username || 'not recorded'} &middot; Requested {new Date(row.created_at).toLocaleString()}
                      </p>
                    </div>
                    <Badge tone="warning">Wants to join as {ROLE_LABEL[row.requested_role] || row.requested_role}</Badge>
                  </div>

                  <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2 mt-4 font-sans text-sm">
                    <div>
                      <dt className="text-xs text-[#757682]">Designation</dt>
                      <dd className="text-[#131b2e]">{row.designation || 'Not provided'}</dd>
                    </div>
                    <div>
                      <dt className="text-xs text-[#757682]">Department</dt>
                      <dd className="text-[#131b2e]">{row.department || 'Not provided'}</dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-xs text-[#757682]">Note from the applicant</dt>
                      <dd className="text-[#131b2e]">{row.registration_notes || 'None'}</dd>
                    </div>
                    <div className="sm:col-span-2">
                      <dt className="text-xs text-[#757682]">Identity-provider account to grant the role to</dt>
                      <dd className="text-[#131b2e] font-mono text-xs break-all">{row.subject_id}</dd>
                    </div>
                  </dl>

                  <label className="flex flex-col gap-1.5 mt-4">
                    <span className="font-sans text-xs font-semibold text-[#444651]">Decision note (optional)</span>
                    <input
                      type="text"
                      maxLength={1000}
                      value={notes[row.binding_id] || ''}
                      onChange={(event) => setNotes((current) => ({ ...current, [row.binding_id]: event.target.value }))}
                      className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
                    />
                  </label>

                  {rowErrors[row.binding_id] && (
                    <p role="alert" className="font-sans text-sm text-[#b3261e] mt-3">
                      {rowErrors[row.binding_id]}
                    </p>
                  )}

                  <div className="flex gap-2 mt-4">
                    <Button disabled={busy} onClick={() => decide(row, 'approved')} aria-label={`Approve ${who}`}>
                      {busy ? 'Saving...' : 'Approve'}
                    </Button>
                    <Button variant="ghost" disabled={busy} onClick={() => decide(row, 'rejected')} aria-label={`Reject ${who}`}>
                      Reject
                    </Button>
                  </div>
                </Panel>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
