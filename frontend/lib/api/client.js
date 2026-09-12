// The single browser-to-backend boundary. Components and stores consume the
// stable frontend view models below and never depend on FastAPI wire shapes.

import { API_BASE_URL } from '../config';
import { TOPIC_GRAPH, TOPIC_LABELS } from '../statMap';
import { monsterForTopic } from '../sprites/monsterSprites';

const SESSION_KEY = 'prism-api-session';

let live = {
  playerId: null,
  sessionId: null,
  dungeon: null,
  combat: null,
};

function hydrateLiveState() {
  if (typeof window === 'undefined') return;
  try {
    live = { ...live, ...JSON.parse(window.localStorage.getItem(SESSION_KEY) || '{}') };
  } catch {
    window.localStorage.removeItem(SESSION_KEY);
  }
}

function persistLiveState() {
  if (typeof window !== 'undefined') {
    window.localStorage.setItem(SESSION_KEY, JSON.stringify(live));
  }
}

function clearLiveState() {
  live = { playerId: null, sessionId: null, dungeon: null, combat: null };
  if (typeof window !== 'undefined') window.localStorage.removeItem(SESSION_KEY);
}

hydrateLiveState();

const inFlightRequests = new Map();

// Collapses concurrent calls sharing the same key into a single underlying
// request. Without this, React StrictMode's dev-only double-invoke of
// effects (and any accidental fast double-click) fires two full round trips
// through the AI service for one logical action -- doubling latency and
// burning through Gemini's free-tier quota twice as fast.
function dedupe(key, run) {
  if (inFlightRequests.has(key)) return inFlightRequests.get(key);
  const promise = run().finally(() => inFlightRequests.delete(key));
  inFlightRequests.set(key, promise);
  return promise;
}

async function request(path, { method = 'GET', body, headers } = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch (cause) {
    const error = new Error('Could not reach the backend. Is it running?');
    error.code = 0;
    error.cause = cause;
    throw error;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((item) => item.msg).join(', ')
      : data?.detail;
    const error = new Error(data?.error || detail || `Request failed (${response.status})`);
    error.code = data?.code ?? response.status;
    throw error;
  }
  return data;
}

function rememberPlayer(player) {
  live.playerId = player.player_id;
  persistLiveState();
  return { player };
}

async function currentPlayer() {
  hydrateLiveState();
  if (!live.playerId) {
    const error = new Error('Not authenticated');
    error.code = 401;
    throw error;
  }
  // fetchMe() fires after every answer submission (see app/combat, app/boss)
  // plus once on app mount -- dedupe concurrent calls for the same player.
  return dedupe(`current-player:${live.playerId}`, () => request(`/game/player/${live.playerId}`));
}

function accuracyMap(player) {
  return Object.fromEntries(
    (player.accuracy_history || []).map((entry) => [entry.topic, entry.recent_accuracy])
  );
}

// Real, per-player room status now comes straight from the backend (see
// backend/routes/game.py::_annotate_rooms_for_player, returned whenever
// GET /game/dungeon/{id} is called with a player_id) -- generalized to every
// seeded curriculum, not just the DSA dungeon the old TOPIC_GRAPH-only
// client-side heuristic here used to support. This is now a thin passthrough
// that just names the fields the map UI expects; labels are resolved by the
// caller (frontend/app/dungeon/page.jsx) from the matching curriculum's
// competency list, not baked in here.
function normalizeDungeon(dungeon) {
  return {
    dungeon_id: dungeon.dungeon_id,
    name: dungeon.name,
    domain: dungeon.domain,
    curriculum_slug: dungeon.curriculum_slug ?? null,
    rooms: (dungeon.rooms || []).map((room) => ({
      ...room,
      status: room.status ?? (room.is_unlocked ? 'unlocked' : 'locked'),
      recent_accuracy: room.recent_accuracy ?? 0,
      completion: room.completion ?? 0,
    })),
    next_topic: dungeon.next_topic ?? null,
    boss_unlocked: Boolean(dungeon.boss_unlocked),
  };
}

async function startDungeonSession(requestedDungeonId) {
  // Keyed on the actual dungeon being requested, not a fixed name: switching
  // curricula (each with its own dungeon_id) must start its own session
  // rather than collapsing into whichever dungeon happened to be active.
  // getDungeon('') and enterRoom()'s no-session fallback intentionally both
  // resolve to the same 'session-start:' key so concurrent calls for the
  // *same* implied dungeon still collapse into one request.
  return dedupe(`session-start:${requestedDungeonId || 'default'}`, async () => {
    const player = await currentPlayer();
    let dungeon;
    try {
      dungeon = await request(`/game/dungeon/${requestedDungeonId}?player_id=${encodeURIComponent(player.player_id)}`);
    } catch (error) {
      if (error.code !== 404) throw error;
      const available = await request('/game/dungeons');
      if (!available.length) throw new Error('No dungeon has been seeded.');
      dungeon = await request(
        `/game/dungeon/${available[0].dungeon_id}?player_id=${encodeURIComponent(player.player_id)}`
      );
    }

    const session = await request('/game/session/start', {
      method: 'POST',
      body: { player_id: player.player_id, dungeon_id: dungeon.dungeon_id },
    });
    live.sessionId = session.session_id;
    live.dungeon = dungeon;
    persistLiveState();
    return normalizeDungeon(dungeon);
  });
}

// Demo mode: the backend's DISABLE_AUTH flag (backend/routes/authorization.py)
// grants every request full access regardless of any bearer token, so login
// here is just "does this username exist" -- no token to mint, no Keycloak
// round trip, nothing to wait on. This intentionally does not attach or
// track an Authorization header at all; re-enabling real auth later means
// restoring a token-minting step here, not just flipping DISABLE_AUTH off.
export const auth = {
  register: (username) =>
    request('/game/player/create', { method: 'POST', body: { username } }).then(rememberPlayer),

  // /game/player/by-username/{username} returns only {player_id, username}
  // (see routes/game.py) -- fetch the actual profile through
  // GET /player/{player_id} (currentPlayer()) right after.
  login: (username) =>
    request(`/game/player/by-username/${encodeURIComponent(username)}`).then(
      async ({ player_id: playerId }) => {
        live.playerId = playerId;
        persistLiveState();
        return { player: await currentPlayer() };
      }
    ),

  logout: async () => {
    clearLiveState();
    return { ok: true };
  },

  me: async () => rememberPlayer(await currentPlayer()),

  setHero: async (playerId, heroId) =>
    request(`/game/player/${playerId}/hero`, { method: 'POST', body: { hero_id: heroId } }),

  setPreferredMode: async (playerId, mode) =>
    request(`/game/player/${playerId}/mode`, { method: 'POST', body: { preferred_mode: mode } }),
};

export const game = {
  getDungeon: (dungeonId) => startDungeonSession(dungeonId),

  // Raw dungeon list (id/name/domain/slug/room_count) -- unlike getDungeon(),
  // does not start a session or fetch rooms. The Academy uses this purely to
  // map a curriculum slug (services/curricula.py) to its "START QUEST" link.
  listDungeons: () => request('/game/dungeons'),

  enterRoom: async (topic, dungeonId) => {
    // Each call to enterRoom(topic) triggers a real (potentially multi-second)
    // Gemini question-generation round trip -- collapse duplicate concurrent
    // calls for the same topic into one.
    return dedupe(`enterRoom:${topic}`, async () => {
      hydrateLiveState();
      // With one dungeon per curriculum now live (not just DSA), a cached
      // session from a previously-viewed curriculum must not be reused for a
      // different one -- that would silently fight the wrong domain's rooms.
      const needsNewSession =
        !live.sessionId || !live.dungeon || (dungeonId && live.dungeon.dungeon_id !== dungeonId);
      if (needsNewSession) await startDungeonSession(dungeonId || '');
      const room =
        topic === 'boss'
          ? live.dungeon.rooms.find((candidate) => candidate.is_boss)
          : live.dungeon.rooms.find((candidate) => candidate.topic === topic);
      if (!room) throw new Error(`No room exists for ${topic}.`);

      const response = await request('/game/room/enter', {
        method: 'POST',
        body: { session_id: live.sessionId, room_id: room.room_id },
      });
      // hits_required/hits_landed are recomputed server-side from real
      // AnswerSubmission rows on every call -- always the ground truth, so
      // there's no client-side "is this a continuing fight?" guess to get
      // wrong. The HP bar is hits remaining, not the old flat difficulty HP
      // pool, so it always reaches empty exactly when the room clears.
      const enemyHp = response.hits_required - response.hits_landed;
      live.combat = {
        roomId: room.room_id,
        topic,
        enemyHp,
        enemyHpMax: response.hits_required,
        playerHp: live.combat?.roomId === room.room_id ? live.combat.playerHp : 100,
      };
      persistLiveState();
      return {
        ...response.question,
        enemy_hp: enemyHp,
        enemy_hp_max: live.combat.enemyHpMax,
        enemy_name: monsterForTopic(topic).name,
      };
    });
  },

  submitAnswer: async (payload) => {
    const player = await currentPlayer();
    const result = await request('/game/answer/submit', {
      method: 'POST',
      body: { ...payload, player_id: player.player_id },
    });
    const damageTaken = result.verdict === 'incorrect' ? 18 : result.verdict === 'partial' ? 8 : 0;
    live.combat = live.combat || { enemyHp: 0, enemyHpMax: 0, playerHp: 100 };
    if (typeof result.hits_required === 'number') {
      live.combat.enemyHpMax = result.hits_required;
      live.combat.enemyHp = Math.max(0, result.hits_required - result.hits_landed);
    }
    live.combat.playerHp = Math.max(0, live.combat.playerHp - damageTaken);
    persistLiveState();
    return {
      ...result,
      player_hp_after: live.combat.playerHp,
      enemy_hp_after: live.combat.enemyHp,
    };
  },

  getPlayer: async (playerId) => {
    const player = await request(`/game/player/${playerId}`);
    return { ...player, topic_accuracies: accuracyMap(player) };
  },

  useHint: async (playerId, questionId) =>
    request('/game/hint/use', {
      method: 'POST',
      body: { player_id: playerId, question_id: questionId },
    }),

  joinGuildRaid: async (guildId) => {
    const player = await currentPlayer();
    let activeGuildId = guildId || player.guild_id;
    if (!activeGuildId) {
      const created = await request('/game/guild/create', {
        method: 'POST',
        body: { name: `${player.username}'s Guild`, creator_player_id: player.player_id },
      });
      activeGuildId = created.guild_id;
    }
    const joined = await request('/game/guild/raid/join', {
      method: 'POST',
      body: { guild_id: activeGuildId, player_id: player.player_id },
    });
    const [guild, status] = await Promise.all([
      request(`/game/guild/${activeGuildId}`),
      request(`/game/guild/raid/status?guild_id=${activeGuildId}`),
    ]);
    return {
      ...guild,
      raid_active: joined.raid_active,
      raid_boss_hp: Math.max(0, status.raid_boss_hp - status.raid_boss_damage),
      raid_boss_hp_max: status.raid_boss_hp,
      members: status.members.map((member) => ({
        ...member,
        topic: status.topic_assignments[member.player_id] || 'arrays',
      })),
    };
  },

  getLeaderboard: async () => ({ leaderboard: await request('/game/leaderboard') }),

  respawn: async () => {
    live.combat = null;
    persistLiveState();
    return { ok: true };
  },

  usePowerup: async (playerId, questionId) => {
    const result = await request('/game/powerup/use', {
      method: 'POST',
      body: { player_id: playerId, question_id: questionId },
    });
    // force_correct/force_correct_heal don't touch HP immediately -- they
    // queue a guaranteed-correct verdict the backend applies on the next
    // /answer/submit, which then reports the real hits_required/hits_landed.
    // heal_to_full is the one immediate effect (player HP has no server pool).
    if (live.combat && result.heal_to_full) {
      live.combat.playerHp = live.combat.playerHpMax ?? 100;
      persistLiveState();
    }
    return { ...result, enemy_hp_after: live.combat?.enemyHp, player_hp_after: live.combat?.playerHp };
  },
};

export const ai = {
  getDashboard: async (playerId) => {
    const data = await request(`/ai/dashboard/${playerId}`);
    const nodes = Object.entries(TOPIC_GRAPH).map(([topic]) => ({
      id: topic,
      label: TOPIC_LABELS[topic] || topic,
      accuracy: data.topic_accuracies?.[topic] ?? 0,
      status: data.graph_state?.[topic] || 'locked',
    }));
    const edges = Object.entries(TOPIC_GRAPH).flatMap(([target, prerequisites]) =>
      prerequisites.map((source) => ({ source, target }))
    );
    return { ...data, graph: { nodes, edges } };
  },

  // Real, access-filtered, cited retrieval (ai/retrieval.py, ai/assistant.py)
  // exposed via routes/ai_real.py. Abstains honestly (status
  // "insufficient_evidence") rather than inventing an answer when retrieval
  // finds nothing strong enough -- see ai/assistant.py's own docstring. No
  // player_id needed: DISABLE_AUTH's demo principal (routes/authorization.py)
  // covers every request in the shared demo deployment this app runs as.
  assistantQuery: (query, topK = 3) =>
    request('/ai/assistant/query', {
      method: 'POST',
      body: { query, top_k: topK },
    }),
};

// Bounded sampling-design virtual lab (backend/labs/sampling_lab.py, exposed
// via routes/sampling_lab.py). Real, resource-bounded, deterministic-answer
// tasks -- no learner code execution, and the task list never carries the
// expected value or the underlying formula's parameters.
export const samplingLab = {
  getTasks: () => request('/learning/sampling-lab/tasks'),

  submit: (playerId, taskId, value) =>
    request('/learning/sampling-lab/submit', {
      method: 'POST',
      body: { player_id: playerId, task_id: taskId, value },
    }),
};

// Real enroll/complete lifecycle for the iGOT/NSSTA course recommendations
// already computed by services/learning_catalog.py::recommend_courses() and
// returned in the `courses` field of learning.getPathway() -- see
// routes/course_enrollment.py for the "igot"/"nssta" simulated-provider
// contract and the provider_imported evidence it writes on completion.
export const courseEnrollment = {
  enroll: (playerId, courseId, title) =>
    request('/learning/catalogue/enroll', {
      method: 'POST',
      body: { player_id: playerId, course_id: courseId, title },
    }),

  complete: (enrollmentId, playerId) =>
    request(`/learning/catalogue/enrollments/${enrollmentId}/complete`, {
      method: 'POST',
      body: { player_id: playerId },
    }),

  list: (playerId) =>
    request(`/learning/catalogue/enrollments?player_id=${encodeURIComponent(playerId)}`),
};

// Real, persisted exam-integrity signal log (backend/routes/proctoring.py).
// The actual face/phone detection runs entirely client-side
// (components/ProctoringMonitor.jsx, via real in-browser ML models) -- this
// client only reports the resulting violation events, never a video frame or
// image. Deliberately a plain event log, not a pass/fail gate: see that
// route's docstring for the anti-fabrication rationale.
export const proctoring = {
  reportViolation: (playerId, attemptId, violationType, detail) =>
    request('/learning/proctoring/violations', {
      method: 'POST',
      body: { player_id: playerId, attempt_id: attemptId, violation_type: violationType, detail },
    }),

  listViolations: (playerId, attemptId) =>
    request(
      `/learning/proctoring/violations?player_id=${encodeURIComponent(playerId)}&attempt_id=${encodeURIComponent(attemptId)}`
    ),
};

// Multipart requests (file upload) can't go through request() above -- the
// browser must set its own multipart boundary in the Content-Type header,
// which request()'s hardcoded 'application/json' would clobber.
async function requestMultipart(path, formData) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method: 'POST', body: formData });
  } catch (cause) {
    const error = new Error('Could not reach the backend. Is it running?');
    error.code = 0;
    error.cause = cause;
    throw error;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(data?.detail)
      ? data.detail.map((item) => item.msg).join(', ')
      : data?.detail;
    const error = new Error(data?.error || detail || `Request failed (${response.status})`);
    error.code = data?.code ?? response.status;
    throw error;
  }
  return data;
}

// `uiLang` below is this app's own two-letter language code ('en'/'hi', see
// lib/i18n/LanguageContext.jsx) -- NOT the free-text "Output language" a quiz
// generation request also takes (that one names the language for an LLM
// prompt, e.g. "English"/"Hindi", and stays independent since a learner may
// want quiz content in a different language than their own UI chrome).
export const learning = {
  getCurricula: (uiLang = 'en') => request(`/learning/curricula?lang=${uiLang}`),

  getIntegrationStatus: (uiLang = 'en') => request(`/learning/integrations/status?lang=${uiLang}`),

  getProfile: (playerId) => request(`/learning/profile/${playerId}`),

  updateProfile: (playerId, profile) =>
    request(`/learning/profile/${playerId}`, { method: 'PUT', body: profile }),

  assess: (playerId, curriculumSlug, selfRatings, uiLang = 'en') =>
    request(`/learning/assessment/${playerId}?lang=${uiLang}`, {
      method: 'POST',
      body: { curriculum_slug: curriculumSlug, self_ratings: selfRatings },
    }),

  getPathway: (playerId, curriculumSlug, uiLang = 'en') =>
    request(`/learning/pathway/${playerId}?curriculum_slug=${encodeURIComponent(curriculumSlug)}&lang=${uiLang}`),

  generateQuiz: async ({ playerId, title, difficulty, language, questionCount, file }) => {
    const form = new FormData();
    form.append('player_id', playerId);
    form.append('title', title);
    form.append('difficulty', difficulty);
    form.append('language', language);
    form.append('question_count', String(questionCount));
    form.append('file', file);
    return requestMultipart('/learning/quiz/generate', form);
  },

  listQuizzes: (playerId) => request(`/learning/quiz/${playerId}`),

  getQuiz: (quizId, playerId) =>
    request(`/learning/quiz/detail/${quizId}?player_id=${encodeURIComponent(playerId)}`),

  // Scores a real attempt at a previously generated quiz -- time+difficulty
  // weighted (services/quiz_scoring.py), deliberately NOT written into the
  // curriculum competency vector (see schemas.learning.QuizSubmitResponse's
  // docstring): a generated quiz's `competency` field is free text, not a
  // real competency_id.
  submitGeneratedQuiz: (quizId, playerId, answers) =>
    request(`/learning/quiz/${quizId}/submit`, {
      method: 'POST',
      body: { player_id: playerId, answers },
    }),

  // Real trainer review/approval workflow (routes/quiz_review.py) -- a
  // learner's private quiz stays private by default; these are the opt-in
  // publish-for-others actions.
  submitQuizForReview: (quizId, playerId) =>
    request(`/learning/quiz/${quizId}/submit-for-review`, {
      method: 'POST',
      body: { player_id: playerId },
    }),

  getReviewQueue: () => request('/learning/quiz/review/queue'),

  reviewQuiz: (quizId, decision, notes) =>
    request(`/learning/quiz/${quizId}/review`, {
      method: 'POST',
      body: { decision, notes },
    }),

  getQuizLibrary: () => request('/learning/quiz/review/library'),

  getQuizAttempts: (quizId, playerId) =>
    request(`/learning/quiz/${quizId}/attempts?player_id=${encodeURIComponent(playerId)}`),

  getAdminOverview: (uiLang = 'en') => request(`/learning/admin/overview?lang=${uiLang}`),

  // Real, source-cited competency quiz (routes/competency_quiz.py) -- see
  // lib/competencyTopics.js for the fixed topic_id list this maps to.
  getCompetencyQuizTopics: () => request('/learning/competency-quiz/topics'),

  getCompetencyQuizQuestions: (topicId, count = 5) =>
    request(`/learning/competency-quiz/questions?topic_id=${encodeURIComponent(topicId)}&count=${count}`),

  // Practice exactly one competency (e.g. one Prerequisite Pathways room) --
  // the backend resolves it to its containing topic internally but scopes
  // the question pool to just this competency_id, not the whole topic.
  getPracticeQuestions: (competencyId, count = 5) =>
    request(`/learning/competency-quiz/questions?competency_id=${encodeURIComponent(competencyId)}&count=${count}`),

  submitCompetencyQuiz: (attemptId, topicId, answers, playerId) =>
    request('/learning/competency-quiz/submit', {
      method: 'POST',
      body: {
        attempt_id: attemptId,
        topic_id: topicId,
        answers,
        ...(playerId ? { player_id: playerId } : {}),
      },
    }),

  // Real code execution (routes/dsa_sandbox.py -> a real Judge0 instance --
  // never run in-process). Solving a problem here writes real evidence into
  // the same AccuracyHistory rows /dungeon's room-unlock logic and
  // /stats's competency pathway both already read.
  getDsaSandboxProblems: () => request('/learning/dsa-sandbox/problems'),

  submitDsaSandbox: (playerId, problemId, code, language = 'python') =>
    request('/learning/dsa-sandbox/submit', {
      method: 'POST',
      body: { player_id: playerId, problem_id: problemId, code, language },
    }),
};
