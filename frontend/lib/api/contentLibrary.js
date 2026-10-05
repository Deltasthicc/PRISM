// Trainer content library API (backend/routes/content_library.py, PS75-10).
// A separate module so this feature does not edit lib/api/client.js; the
// browser still reaches the backend only through the shared request helpers
// (plus the one authenticated blob download below, which cannot use JSON).

import { request, requestMultipart } from './client';
import { API_BASE_URL } from '../config';
import { getValidAccessToken } from '../auth/oidc';

export const CONTENT_KINDS = [
  { value: 'recorded_lecture', label: 'Recorded lecture' },
  { value: 'presentation', label: 'Presentation' },
  { value: 'study_material', label: 'Study material' },
];

export function kindLabel(kind) {
  return CONTENT_KINDS.find((entry) => entry.value === kind)?.label || kind;
}

// Mirrors the server allowlist and default cap for early feedback only. The
// server is authoritative: it re-checks extension, content and size.
export const ALLOWED_EXTENSIONS = ['pdf', 'pptx', 'docx', 'txt', 'md', 'mp4', 'webm', 'mp3'];
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

export function fileExtension(name) {
  const base = String(name || '').split(/[\\/]/).pop();
  const dot = base.lastIndexOf('.');
  return dot > 0 ? base.slice(dot + 1).toLowerCase() : '';
}

/** Returns an error message for an unusable file, or '' if it looks fine. */
export function validateFileHint(file) {
  if (!file) return 'Choose a file to upload.';
  if (!ALLOWED_EXTENSIONS.includes(fileExtension(file.name))) {
    return `Unsupported file type. Allowed: ${ALLOWED_EXTENSIONS.join(', ')}.`;
  }
  if (file.size === 0) return 'The selected file is empty.';
  if (file.size > MAX_UPLOAD_BYTES) {
    return `File is too large (limit ${formatBytes(MAX_UPLOAD_BYTES)}).`;
  }
  return '';
}

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const BASE = '/learning/library/items';

async function downloadError(response) {
  const data = await response.json().catch(() => ({}));
  const error = new Error(
    (typeof data?.detail === 'string' && data.detail) ||
      (response.status === 404
        ? 'This file is not available to you.'
        : `Download failed (${response.status})`)
  );
  error.code = response.status;
  return error;
}

export const contentLibraryApi = {
  upload: (trainerId, { title, description, kind, courseId, file }) => {
    const form = new FormData();
    form.append('trainer_id', trainerId);
    form.append('title', title);
    form.append('description', description || '');
    form.append('kind', kind);
    if (courseId) form.append('course_id', courseId);
    form.append('file', file);
    return requestMultipart(BASE, form);
  },

  listMine: (trainerId) => request(`${BASE}/mine?trainer_id=${encodeURIComponent(trainerId)}`),

  publish: (contentId, trainerId) =>
    request(`${BASE}/${encodeURIComponent(contentId)}/publish`, {
      method: 'POST',
      body: { trainer_id: trainerId },
    }),

  unpublish: (contentId, trainerId) =>
    request(`${BASE}/${encodeURIComponent(contentId)}/unpublish`, {
      method: 'POST',
      body: { trainer_id: trainerId },
    }),

  remove: (contentId, trainerId) =>
    request(`${BASE}/${encodeURIComponent(contentId)}?trainer_id=${encodeURIComponent(trainerId)}`, {
      method: 'DELETE',
    }),

  listForTrainee: (playerId) => request(`${BASE}?player_id=${encodeURIComponent(playerId)}`),

  // A plain <a href> cannot send the Authorization header, so fetch the file
  // with the bearer token (when there is one) and save it from a blob.
  download: async (contentId, playerId, filename) => {
    let response;
    try {
      const accessToken = await getValidAccessToken();
      response = await fetch(
        `${API_BASE_URL}${BASE}/${encodeURIComponent(contentId)}/download?player_id=${encodeURIComponent(playerId)}`,
        { headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined }
      );
    } catch (cause) {
      const error = new Error('Could not reach the backend. Is it running?');
      error.code = 0;
      error.cause = cause;
      throw error;
    }
    if (!response.ok) throw await downloadError(response);

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    try {
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = filename || 'download';
      anchor.rel = 'noopener';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } finally {
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
    }
  },
};
