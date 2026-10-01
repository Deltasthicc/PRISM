'use client';

import { useEffect, useState } from 'react';
import { Users } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { cohorts } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

// Admin console for real trainer/cohort assignment
// (backend/routes/cohorts.py). Not role-gated in the UI yet --
// COHORT_MANAGE is enforced server-side (403 for anyone without
// organization_admin), the same known gap already noted on
// /trainer/courses and the pre-existing trainer-review/host-session pages.

export default function AdminCohortsPage() {
  const { ready } = useRequireAuth();
  const [cohortList, setCohortList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [name, setName] = useState('');
  const [trainerUsername, setTrainerUsername] = useState('');
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const [expandedId, setExpandedId] = useState(null);
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(false);
  const [newMemberUsername, setNewMemberUsername] = useState('');
  const [memberError, setMemberError] = useState('');

  async function refresh() {
    setLoading(true);
    setLoadError('');
    try {
      const data = await cohorts.listAll();
      setCohortList(data || []);
    } catch (cause) {
      setLoadError(cause.message || 'Could not load cohorts.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!ready) return;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  async function handleCreate(event) {
    event.preventDefault();
    if (!name.trim() || !trainerUsername.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      const trainerId = await cohorts.lookupPlayerIdByUsername(trainerUsername);
      await cohorts.create(name.trim(), trainerId);
      setName('');
      setTrainerUsername('');
      await refresh();
    } catch (cause) {
      setCreateError(cause.code === 404 ? `No account found for "${trainerUsername}".` : cause.message || 'Could not create the cohort.');
    } finally {
      setCreating(false);
    }
  }

  async function toggleExpand(cohortId) {
    if (expandedId === cohortId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(cohortId);
    setMembersLoading(true);
    setMemberError('');
    try {
      const data = await cohorts.listMembers(cohortId);
      setMembers(data || []);
    } catch (cause) {
      setMemberError(cause.message || 'Could not load members.');
    } finally {
      setMembersLoading(false);
    }
  }

  async function handleAddMember(cohortId) {
    if (!newMemberUsername.trim()) return;
    setMemberError('');
    try {
      const playerId = await cohorts.lookupPlayerIdByUsername(newMemberUsername);
      await cohorts.addMember(cohortId, playerId);
      setNewMemberUsername('');
      const data = await cohorts.listMembers(cohortId);
      setMembers(data || []);
      await refresh();
    } catch (cause) {
      setMemberError(cause.code === 404 ? `No account found for "${newMemberUsername}".` : cause.message || 'Could not add member.');
    }
  }

  async function handleRemoveMember(cohortId, playerId) {
    try {
      await cohorts.removeMember(cohortId, playerId);
      const data = await cohorts.listMembers(cohortId);
      setMembers(data || []);
      await refresh();
    } catch (cause) {
      setMemberError(cause.message || 'Could not remove member.');
    }
  }

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Users size={12} />
          Admin
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Cohorts</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Assign a cohort of trainees to a trainer for scoped participation and performance visibility.
        </p>
      </div>

      <Panel>
        <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">New cohort</h2>
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <Input id="cohort-name" label="Cohort name" value={name} onChange={(e) => setName(e.target.value)} required />
          <Input
            id="cohort-trainer"
            label="Trainer username"
            value={trainerUsername}
            onChange={(e) => setTrainerUsername(e.target.value)}
            required
          />
          {createError && <p className="font-sans text-xs text-[#b3261e]">{createError}</p>}
          <Button type="submit" disabled={creating} className="self-start">
            {creating ? 'Creating…' : 'Create cohort'}
          </Button>
        </form>
      </Panel>

      {loading && <p className="font-sans text-sm text-[#757682] text-center mt-4">Loading cohorts…</p>}
      {!loading && loadError && <p className="font-sans text-sm text-[#b3261e]">{loadError}</p>}
      {!loading && !loadError && cohortList.length === 0 && (
        <p className="font-sans text-sm text-[#757682] text-center">No cohorts yet — create one above.</p>
      )}

      {!loading &&
        !loadError &&
        cohortList.map((cohort) => (
          <Panel key={cohort.cohort_id}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <h3 className="font-sans text-sm font-bold text-[#131b2e]">{cohort.name}</h3>
                <p className="font-mono text-[10px] text-[#8a8f9d]">
                  trainer: {cohort.trainer_id} · {cohort.member_count} member{cohort.member_count === 1 ? '' : 's'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => toggleExpand(cohort.cohort_id)}
                className="font-sans text-xs text-[#00236f] underline"
              >
                {expandedId === cohort.cohort_id ? 'Hide members' : 'Manage members'}
              </button>
            </div>

            {expandedId === cohort.cohort_id && (
              <div className="mt-3 pt-3 border-t border-[#c5c5d3]/30 flex flex-col gap-2">
                {membersLoading && <p className="font-sans text-xs text-[#757682]">Loading members…</p>}
                {!membersLoading &&
                  members.map((member) => (
                    <div key={member.player_id} className="flex items-center justify-between gap-2">
                      <span className="font-sans text-xs text-[#131b2e]">{member.username}</span>
                      <button
                        type="button"
                        onClick={() => handleRemoveMember(cohort.cohort_id, member.player_id)}
                        className="font-sans text-xs text-[#b3261e] underline"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                {!membersLoading && members.length === 0 && (
                  <p className="font-sans text-xs text-[#757682]">No members yet.</p>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <input
                    value={newMemberUsername}
                    onChange={(e) => setNewMemberUsername(e.target.value)}
                    placeholder="Trainee username"
                    className="flex-1 px-3 py-2 rounded-lg border border-[#c5c5d3]/60 font-sans text-xs outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
                  />
                  <Button type="button" onClick={() => handleAddMember(cohort.cohort_id)} className="text-xs px-3 py-2">
                    Add
                  </Button>
                </div>
                {memberError && <p className="font-sans text-xs text-[#b3261e]">{memberError}</p>}
              </div>
            )}
          </Panel>
        ))}
    </div>
  );
}
