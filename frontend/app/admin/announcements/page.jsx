'use client';

import { useEffect, useState } from 'react';
import { Megaphone } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { announcementsApi } from '@/lib/api/announcements';
import {
  AUDIENCE_LABELS,
  KIND_LABELS,
  STATUS_LABELS,
  formatFeedDate,
  localInputToIso,
} from '@/lib/homeFeed';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

// Admin authoring surface for the in-app home feed
// (backend/routes/announcements.py). "Notifications" means this feed only --
// nothing is pushed or emailed. Not role-gated in the UI yet:
// ANNOUNCEMENT_MANAGE is enforced server-side (403 for anyone who is not an
// organization_admin), the same known gap as /admin/cohorts. There is no
// delete: unpublishing is the retire path and keeps history.

const STATUS_TONE = {
  draft: 'default',
  published: 'success',
  unpublished: 'warning',
  expired: 'warning',
};

const SELECT_CLASS =
  'bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]';

export default function AdminAnnouncementsPage() {
  const { ready } = useRequireAuth();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [kind, setKind] = useState('announcement');
  const [audience, setAudience] = useState('all');
  const [expiresLocal, setExpiresLocal] = useState('');
  const [publishNow, setPublishNow] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState('');

  const [busyId, setBusyId] = useState(null);
  const [actionError, setActionError] = useState('');

  async function refresh() {
    setLoading(true);
    setLoadError('');
    try {
      const data = await announcementsApi.list();
      setItems(data || []);
    } catch (cause) {
      setLoadError(cause.message || 'Could not load announcements.');
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
    if (!title.trim() || !body.trim()) return;
    setCreating(true);
    setCreateError('');
    try {
      await announcementsApi.create({
        title: title.trim(),
        body: body.trim(),
        kind,
        audience,
        expiresAt: localInputToIso(expiresLocal),
        publish: publishNow,
      });
      setTitle('');
      setBody('');
      setKind('announcement');
      setAudience('all');
      setExpiresLocal('');
      setPublishNow(false);
      await refresh();
    } catch (cause) {
      setCreateError(cause.message || 'Could not create the announcement.');
    } finally {
      setCreating(false);
    }
  }

  async function handleToggle(item) {
    setBusyId(item.announcement_id);
    setActionError('');
    try {
      if (item.is_published) {
        await announcementsApi.unpublish(item.announcement_id);
      } else {
        await announcementsApi.publish(item.announcement_id);
      }
      await refresh();
    } catch (cause) {
      setActionError(cause.message || 'Could not update the announcement.');
    } finally {
      setBusyId(null);
    }
  }

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Megaphone size={12} aria-hidden="true" />
          Admin
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Announcements</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Write notices for the in-app home feed. Drafts are visible only to admins. Unpublishing hides an
          announcement but keeps its history; announcements cannot be deleted.
        </p>
      </div>

      <Panel>
        <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">New announcement</h2>
        <form onSubmit={handleCreate} className="flex flex-col gap-3">
          <Input
            id="announcement-title"
            label="Title"
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
          <Input
            id="announcement-body"
            label="Message"
            textarea
            rows={4}
            value={body}
            maxLength={4000}
            onChange={(e) => setBody(e.target.value)}
            required
          />
          <div className="flex gap-3 flex-wrap">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="announcement-kind" className="font-sans text-xs font-semibold text-[#444651]">
                Type
              </label>
              <select id="announcement-kind" value={kind} onChange={(e) => setKind(e.target.value)} className={SELECT_CLASS}>
                {Object.entries(KIND_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="announcement-audience" className="font-sans text-xs font-semibold text-[#444651]">
                Audience
              </label>
              <select
                id="announcement-audience"
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
                className={SELECT_CLASS}
              >
                {Object.entries(AUDIENCE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <Input
              id="announcement-expires"
              label="Expires (optional)"
              type="datetime-local"
              value={expiresLocal}
              onChange={(e) => setExpiresLocal(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-2 font-sans text-sm text-[#131b2e]">
            <input
              type="checkbox"
              checked={publishNow}
              onChange={(e) => setPublishNow(e.target.checked)}
              className="h-4 w-4"
            />
            Publish immediately (otherwise saved as a draft)
          </label>
          {createError && (
            <p role="alert" className="font-sans text-xs text-[#b3261e]">
              {createError}
            </p>
          )}
          <Button type="submit" disabled={creating} className="self-start">
            {creating ? 'Saving…' : publishNow ? 'Publish announcement' : 'Save draft'}
          </Button>
        </form>
      </Panel>

      {loading && (
        <p role="status" className="font-sans text-sm text-[#757682] text-center mt-4">
          Loading announcements…
        </p>
      )}
      {!loading && loadError && (
        <div className="flex flex-col gap-2 items-start">
          <p role="alert" className="font-sans text-sm text-[#b3261e]">
            {loadError}
          </p>
          <Button type="button" variant="ghost" onClick={refresh} className="text-xs px-3 py-2">
            Retry
          </Button>
        </div>
      )}
      {!loading && !loadError && items.length === 0 && (
        <p className="font-sans text-sm text-[#757682] text-center">No announcements yet — create one above.</p>
      )}
      {actionError && (
        <p role="alert" className="font-sans text-xs text-[#b3261e]">
          {actionError}
        </p>
      )}

      {!loading && !loadError && items.length > 0 && (
        <ul className="flex flex-col gap-3">
          {items.map((item) => (
            <li key={item.announcement_id}>
              <Panel>
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div className="min-w-0">
                    <h3 className="font-sans text-sm font-bold text-[#131b2e]">{item.title}</h3>
                    <div className="flex items-center gap-2 flex-wrap mt-1">
                      <Badge tone={STATUS_TONE[item.status] || 'default'}>
                        {STATUS_LABELS[item.status] || item.status}
                      </Badge>
                      <Badge>{KIND_LABELS[item.kind] || item.kind}</Badge>
                      <Badge>For: {AUDIENCE_LABELS[item.audience] || item.audience}</Badge>
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant={item.is_published ? 'ghost' : 'primary'}
                    disabled={busyId === item.announcement_id}
                    onClick={() => handleToggle(item)}
                    className="text-xs px-3 py-2"
                    aria-label={`${item.is_published ? 'Unpublish' : 'Publish'} announcement: ${item.title}`}
                  >
                    {busyId === item.announcement_id ? 'Working…' : item.is_published ? 'Unpublish' : 'Publish'}
                  </Button>
                </div>
                <p className="font-sans text-xs text-[#444651] mt-2 whitespace-pre-line">{item.body}</p>
                <p className="font-mono text-[10px] text-[#757682] mt-2">
                  Created {formatFeedDate(item.created_at)}
                  {item.published_at ? ` · Published ${formatFeedDate(item.published_at)}` : ''}
                  {item.expires_at ? ` · Expires ${formatFeedDate(item.expires_at)}` : ''}
                </p>
              </Panel>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
