'use client';

import { useCallback, useEffect, useState } from 'react';
import { Library } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { contentLibraryApi, formatBytes, kindLabel } from '@/lib/api/contentLibrary';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// Trainee-facing library: published materials the server says this player may
// see (no course link, or enrolled in the linked course). Files are fetched
// with the bearer token and saved from a blob -- they are never opened inline.
export default function LibraryPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const playerId = player?.player_id;

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [downloadingId, setDownloadingId] = useState(null);
  const [downloadError, setDownloadError] = useState('');

  const load = useCallback(async () => {
    if (!playerId) return;
    setLoading(true);
    setLoadError('');
    try {
      setItems((await contentLibraryApi.listForTrainee(playerId)) || []);
    } catch (cause) {
      setLoadError(cause.message || 'Could not load the library.');
    } finally {
      setLoading(false);
    }
  }, [playerId]);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function handleDownload(item) {
    setDownloadingId(item.content_id);
    setDownloadError('');
    try {
      await contentLibraryApi.download(item.content_id, playerId, item.original_filename);
    } catch (cause) {
      setDownloadError(`${item.title}: ${cause.message || 'Download failed.'}`);
    } finally {
      setDownloadingId(null);
    }
  }

  if (!ready || !player) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Library size={12} aria-hidden="true" />
          Learning
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Content library</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Recorded lectures, presentations and study materials from your trainers. Downloaded files
          are saved to your device, not opened in the browser.
        </p>
      </div>

      {loading && (
        <p role="status" className="font-sans text-sm text-[#757682] text-center mt-4">
          Loading the library…
        </p>
      )}

      {!loading && loadError && (
        <div role="alert" className="flex items-center gap-3">
          <p className="font-sans text-sm text-[#b3261e]">{loadError}</p>
          <Button variant="ghost" onClick={load}>
            Retry
          </Button>
        </div>
      )}

      {downloadError && (
        <p role="alert" className="font-sans text-sm text-[#b3261e]">
          {downloadError}
        </p>
      )}

      {!loading && !loadError && items.length === 0 && (
        <p className="font-sans text-sm text-[#757682] text-center">
          No materials are available to you yet. Materials appear here once a trainer publishes them
          (some require enrollment in the trainer&apos;s course).
        </p>
      )}

      {!loading &&
        !loadError &&
        items.map((item) => (
          <Panel key={item.content_id}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <h2 className="font-sans text-sm font-bold text-[#131b2e] break-words">{item.title}</h2>
                <p className="font-mono text-[10px] text-[#8a8f9d] break-all">
                  {item.original_filename} · {formatBytes(item.size_bytes)}
                  {item.course_title ? ` · Course: ${item.course_title}` : ''}
                </p>
                {item.description && (
                  <p className="font-sans text-xs text-[#444651] mt-1 break-words">{item.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3">
                <Badge tone="accent">{kindLabel(item.kind)}</Badge>
                <Button
                  variant="ghost"
                  onClick={() => handleDownload(item)}
                  disabled={downloadingId === item.content_id}
                  aria-label={`Download ${item.title}`}
                >
                  {downloadingId === item.content_id ? 'Downloading…' : 'Download'}
                </Button>
              </div>
            </div>
          </Panel>
        ))}
    </div>
  );
}
