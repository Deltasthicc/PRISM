import { request } from './client';

// Admin announcements and the in-app home feed (backend/routes/announcements.py).
// "Notifications" here means this in-app feed only: nothing is pushed or
// emailed. Authoring is organization_admin-only (enforced server-side); the
// feed is scoped to the signed-in player (403 for anyone else's id).
export const announcementsApi = {
  list: () => request('/learning/announcements'),
  create: ({ title, body, kind, audience, expiresAt, publish }) =>
    request('/learning/announcements', {
      method: 'POST',
      body: {
        title,
        body,
        kind,
        audience,
        expires_at: expiresAt || null,
        publish: Boolean(publish),
      },
    }),
  publish: (announcementId) =>
    request(`/learning/announcements/${encodeURIComponent(announcementId)}/publish`, { method: 'POST' }),
  unpublish: (announcementId) =>
    request(`/learning/announcements/${encodeURIComponent(announcementId)}/unpublish`, { method: 'POST' }),
  getHomeFeed: (playerId) => request(`/learning/home/feed?player_id=${encodeURIComponent(playerId)}`),
};
