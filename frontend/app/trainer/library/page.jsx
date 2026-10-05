'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Library } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { courseCatalog } from '@/lib/api/client';
import {
  ALLOWED_EXTENSIONS,
  CONTENT_KINDS,
  MAX_UPLOAD_BYTES,
  contentLibraryApi,
  formatBytes,
  kindLabel,
  validateFileHint,
} from '@/lib/api/contentLibrary';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

const FIELD_CLASS =
  'bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 ' +
  'outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]';

// Trainer content library (backend/routes/content_library.py). The client
// checks below only give early feedback; the server re-validates type,
// content and size. CONTENT_LIBRARY_WRITE is enforced server-side (403 for a
// learner-only token), like the other trainer pages.
export default function TrainerLibraryPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const playerId = player?.player_id;

  const [items, setItems] = useState([]);
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [kind, setKind] = useState(CONTENT_KINDS[0].value);
  const [courseId, setCourseId] = useState('');
  const [file, setFile] = useState(null);
  const [fileError, setFileError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [notice, setNotice] = useState('');
  const fileInputRef = useRef(null);

  const [busyId, setBusyId] = useState(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);
  const [rowError, setRowError] = useState('');

  const refresh = useCallback(async () => {
    if (!playerId) return;
    setLoading(true);
    setLoadError('');
    try {
      const [mine, ownCourses] = await Promise.all([
        contentLibraryApi.listMine(playerId),
        courseCatalog.listMine(playerId).catch(() => []),
      ]);
      setItems(mine || []);
      setCourses(ownCourses || []);
    } catch (cause) {
      setLoadError(cause.message || 'Could not load your library.');
    } finally {
      setLoading(false);
    }
  }, [playerId]);

  useEffect(() => {
    if (ready) refresh();
  }, [ready, refresh]);

  function handleFileChange(event) {
    const chosen = event.target.files?.[0] || null;
    setFile(chosen);
    setFileError(chosen ? validateFileHint(chosen) : '');
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!playerId) return;
    const hint = validateFileHint(file);
    if (hint) {
      setFileError(hint);
      return;
    }
    if (!title.trim()) return;
    setUploading(true);
    setUploadError('');
    setNotice('');
    try {
      await contentLibraryApi.upload(playerId, {
        title: title.trim(),
        description: description.trim(),
        kind,
        courseId,
        file,
      });
      setTitle('');
      setDescription('');
      setCourseId('');
      setFile(null);
      setFileError('');
      if (fileInputRef.current) fileInputRef.current.value = '';
      setNotice('Uploaded as a draft. Publish it when trainees should see it.');
      await refresh();
    } catch (cause) {
      setUploadError(cause.message || 'Could not upload the file.');
    } finally {
      setUploading(false);
    }
  }

  async function runRowAction(item, action) {
    setBusyId(item.content_id);
    setRowError('');
    setNotice('');
    try {
      await action();
      await refresh();
    } catch (cause) {
      setRowError(`${item.title}: ${cause.message || 'The action failed.'}`);
    } finally {
      setBusyId(null);
      setConfirmDeleteId(null);
    }
  }

  const togglePublish = (item) =>
    runRowAction(item, () =>
      item.is_published
        ? contentLibraryApi.unpublish(item.content_id, playerId)
        : contentLibraryApi.publish(item.content_id, playerId)
    );

  const removeItem = (item) =>
    runRowAction(item, () => contentLibraryApi.remove(item.content_id, playerId));

  if (!ready || !player) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Library size={12} aria-hidden="true" />
          Trainer
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Content library</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Upload recorded lectures, presentations and study materials, then publish them for your
          trainees. Uploads start as drafts that only you can see.
        </p>
      </div>

      <Panel>
        <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">Upload a file</h2>
        <form onSubmit={handleUpload} className="flex flex-col gap-3">
          <Input
            id="library-title"
            label="Title"
            value={title}
            maxLength={200}
            onChange={(e) => setTitle(e.target.value)}
            required
          />
          <Input
            id="library-description"
            label="Description (optional)"
            textarea
            rows="3"
            maxLength={2000}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
          <div className="flex flex-col gap-1.5">
            <label htmlFor="library-kind" className="font-sans text-xs font-semibold text-[#444651]">
              Type of material
            </label>
            <select
              id="library-kind"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
              className={FIELD_CLASS}
            >
              {CONTENT_KINDS.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="library-course" className="font-sans text-xs font-semibold text-[#444651]">
              Link to one of your courses (optional)
            </label>
            <select
              id="library-course"
              value={courseId}
              onChange={(e) => setCourseId(e.target.value)}
              className={FIELD_CLASS}
              aria-describedby="library-course-help"
            >
              <option value="">No course (visible to all trainees once published)</option>
              {courses.map((course) => (
                <option key={course.course_id} value={course.course_id}>
                  {course.title}
                </option>
              ))}
            </select>
            <p id="library-course-help" className="font-sans text-xs text-[#757682]">
              If you pick a course, only trainees enrolled in it can open the file.
            </p>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="library-file" className="font-sans text-xs font-semibold text-[#444651]">
              File
            </label>
            <input
              id="library-file"
              ref={fileInputRef}
              type="file"
              accept={ALLOWED_EXTENSIONS.map((ext) => `.${ext}`).join(',')}
              onChange={handleFileChange}
              aria-describedby="library-file-help"
              aria-invalid={fileError ? 'true' : undefined}
              className="font-sans text-sm text-[#131b2e]"
            />
            <p id="library-file-help" className="font-sans text-xs text-[#757682]">
              Allowed: {ALLOWED_EXTENSIONS.join(', ')}. Up to {formatBytes(MAX_UPLOAD_BYTES)}. The
              server checks the type and size again.
            </p>
            {fileError && (
              <p role="alert" className="font-sans text-xs text-[#b3261e]">
                {fileError}
              </p>
            )}
          </div>
          {uploadError && (
            <p role="alert" className="font-sans text-xs text-[#b3261e]">
              {uploadError}
            </p>
          )}
          {notice && (
            <p role="status" className="font-sans text-xs text-[#1a7f4b]">
              {notice}
            </p>
          )}
          <Button type="submit" disabled={uploading || !title.trim() || !file || !!fileError} className="self-start">
            {uploading ? 'Uploading…' : 'Upload as draft'}
          </Button>
        </form>
      </Panel>

      <h2 className="font-sans text-sm font-bold text-[#131b2e]">Your files</h2>

      {loading && (
        <p role="status" className="font-sans text-sm text-[#757682] text-center mt-2">
          Loading your library…
        </p>
      )}

      {!loading && loadError && (
        <div role="alert" className="flex items-center gap-3">
          <p className="font-sans text-sm text-[#b3261e]">{loadError}</p>
          <Button variant="ghost" onClick={refresh}>
            Retry
          </Button>
        </div>
      )}

      {rowError && (
        <p role="alert" className="font-sans text-sm text-[#b3261e]">
          {rowError}
        </p>
      )}

      {!loading && !loadError && items.length === 0 && (
        <p className="font-sans text-sm text-[#757682] text-center">
          Nothing uploaded yet — add your first file above.
        </p>
      )}

      {!loading &&
        !loadError &&
        items.map((item) => (
          <Panel key={item.content_id}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <h3 className="font-sans text-sm font-bold text-[#131b2e] break-words">{item.title}</h3>
                <p className="font-mono text-[10px] text-[#8a8f9d] break-all">
                  {kindLabel(item.kind)} · {item.original_filename} · {formatBytes(item.size_bytes)}
                  {item.course_title ? ` · Course: ${item.course_title}` : ' · All trainees'}
                </p>
                {item.description && (
                  <p className="font-sans text-xs text-[#444651] mt-1 break-words">{item.description}</p>
                )}
              </div>
              <div className="flex items-center gap-3 flex-wrap">
                <Badge tone={item.is_published ? 'success' : 'warning'}>
                  {item.is_published ? 'Published' : 'Draft'}
                </Badge>
                <button
                  type="button"
                  onClick={() => togglePublish(item)}
                  disabled={busyId === item.content_id}
                  className="font-sans text-xs text-[#00236f] underline disabled:opacity-50"
                >
                  {item.is_published ? 'Unpublish' : 'Publish'}
                </button>
                {confirmDeleteId === item.content_id ? (
                  <span className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => removeItem(item)}
                      disabled={busyId === item.content_id}
                      className="font-sans text-xs font-semibold text-[#b3261e] underline disabled:opacity-50"
                    >
                      Confirm delete
                    </button>
                    <button
                      type="button"
                      onClick={() => setConfirmDeleteId(null)}
                      className="font-sans text-xs text-[#444651] underline"
                    >
                      Cancel
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setConfirmDeleteId(item.content_id)}
                    disabled={busyId === item.content_id}
                    aria-label={`Delete ${item.title}`}
                    className="font-sans text-xs text-[#b3261e] underline disabled:opacity-50"
                  >
                    Delete
                  </button>
                )}
              </div>
            </div>
          </Panel>
        ))}
    </div>
  );
}
