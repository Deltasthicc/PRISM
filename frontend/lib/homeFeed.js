// Pure helpers for the home feed and the admin announcements page, kept free
// of React so they can be unit tested.

export const KIND_LABELS = {
  announcement: 'Announcement',
  achievement: 'Achievement',
  new_content: 'New content',
};

export const AUDIENCE_LABELS = {
  all: 'Everyone',
  learner: 'Learners',
  trainer: 'Trainers',
};

// Status text is always shown as words, never colour alone.
export const STATUS_LABELS = {
  draft: 'Draft (not visible)',
  published: 'Published (visible)',
  unpublished: 'Unpublished (hidden)',
  expired: 'Expired (hidden)',
};

export function formatFeedDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

/** True when the feed has no items at all in any of its three sections. */
export function isFeedEmpty(feed) {
  if (!feed) return true;
  return (
    (feed.announcements || []).length === 0 &&
    (feed.new_courses || []).length === 0 &&
    (feed.my_achievements || []).length === 0
  );
}

/** Convert a <input type="datetime-local"> value to an ISO string, or null. */
export function localInputToIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}
