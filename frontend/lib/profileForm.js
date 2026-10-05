// Pure helpers for the structured profile editor (PS75-02). Kept free of React
// so the cleaning rules the server will also enforce can be unit tested.

export const EMPTY_STRUCTURED = {
  qualifications: [],
  work_experience: [],
  interests: [],
  skills: [],
  external_certificates: [],
};

export const BLANK_QUALIFICATION = { degree: '', institution: '', year: '' };
export const BLANK_EXPERIENCE = { title: '', organization: '', start_year: '', end_year: '', description: '' };
export const BLANK_CERTIFICATE = { name: '', issuer: '', year: '', credential_id: '' };

export function parseTags(text) {
  const seen = new Set();
  const tags = [];
  for (const raw of String(text || '').split(',')) {
    const tag = raw.trim();
    if (tag && !seen.has(tag.toLowerCase())) {
      seen.add(tag.toLowerCase());
      tags.push(tag);
    }
  }
  return tags;
}

export function tagsToText(tags) {
  return (tags || []).join(', ');
}

function yearOrNull(value) {
  if (value === '' || value === null || value === undefined) return null;
  const year = Number(value);
  return Number.isInteger(year) ? year : null;
}

function trimmed(value) {
  return String(value || '').trim();
}

// Drops rows whose required field is blank and normalises years, so the
// request only contains entries the server will accept.
export function cleanStructured(profile) {
  return {
    qualifications: (profile.qualifications || [])
      .filter((row) => trimmed(row.degree))
      .map((row) => ({ degree: trimmed(row.degree), institution: trimmed(row.institution), year: yearOrNull(row.year) })),
    work_experience: (profile.work_experience || [])
      .filter((row) => trimmed(row.title))
      .map((row) => ({
        title: trimmed(row.title),
        organization: trimmed(row.organization),
        start_year: yearOrNull(row.start_year),
        end_year: yearOrNull(row.end_year),
        description: trimmed(row.description),
      })),
    interests: profile.interests || [],
    skills: profile.skills || [],
    external_certificates: (profile.external_certificates || [])
      .filter((row) => trimmed(row.name))
      .map((row) => ({
        name: trimmed(row.name),
        issuer: trimmed(row.issuer),
        year: yearOrNull(row.year),
        credential_id: trimmed(row.credential_id),
      })),
  };
}

// Returns a message for the first problem the server would reject, or ''.
export function structuredProblem(profile) {
  for (const row of profile.work_experience || []) {
    const start = yearOrNull(row.start_year);
    const end = yearOrNull(row.end_year);
    if (trimmed(row.title) && start && end && end < start) {
      return `Work experience "${trimmed(row.title)}": the end year is before the start year.`;
    }
  }
  for (const [label, rows] of [
    ['Qualification', profile.qualifications],
    ['Work experience', profile.work_experience],
    ['Certificate', profile.external_certificates],
  ]) {
    for (const row of rows || []) {
      for (const key of ['year', 'start_year', 'end_year']) {
        const raw = row[key];
        if (raw === '' || raw === null || raw === undefined) continue;
        const year = Number(raw);
        if (!Number.isInteger(year) || year < 1950 || year > 2100) {
          return `${label}: years must be between 1950 and 2100.`;
        }
      }
    }
  }
  return '';
}
