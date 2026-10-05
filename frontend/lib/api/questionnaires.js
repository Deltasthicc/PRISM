import { request } from './client';

// Trainer-authored questionnaires with deadlines (backend/routes/questionnaires.py,
// SIH26075 PS75-08). Every call names the acting trainer/player explicitly;
// the server validates it against the authenticated principal. Deadlines are
// enforced by the server clock only -- nothing here sends a "submitted at".
const BASE = '/learning/questionnaires';
const enc = encodeURIComponent;

export const questionnairesApi = {
  // --- trainer ---
  create: (payload) => request(BASE, { method: 'POST', body: payload }),
  update: (questionnaireId, payload) =>
    request(`${BASE}/${enc(questionnaireId)}`, { method: 'PUT', body: payload }),
  listMine: (trainerId) => request(`${BASE}/mine?trainer_id=${enc(trainerId)}`),
  results: (questionnaireId, trainerId) =>
    request(`${BASE}/${enc(questionnaireId)}/results?trainer_id=${enc(trainerId)}`),
  publish: (questionnaireId, trainerId) =>
    request(`${BASE}/${enc(questionnaireId)}/publish`, { method: 'POST', body: { trainer_id: trainerId } }),
  unpublish: (questionnaireId, trainerId) =>
    request(`${BASE}/${enc(questionnaireId)}/unpublish`, { method: 'POST', body: { trainer_id: trainerId } }),
  extendDeadline: (questionnaireId, trainerId, dueAtIso) =>
    request(`${BASE}/${enc(questionnaireId)}/extend-deadline`, {
      method: 'POST',
      body: { trainer_id: trainerId, due_at: dueAtIso },
    }),

  // --- trainee ---
  available: (playerId) => request(`${BASE}/available?player_id=${enc(playerId)}`),
  get: (questionnaireId, playerId) =>
    request(`${BASE}/${enc(questionnaireId)}?player_id=${enc(playerId)}`),
  submit: (questionnaireId, playerId, answers) =>
    request(`${BASE}/${enc(questionnaireId)}/submit`, {
      method: 'POST',
      body: { player_id: playerId, answers },
    }),
};
