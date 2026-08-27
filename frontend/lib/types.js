// JSDoc-only "types" — no TypeScript build step needed, but editors get
// autocomplete + the whole team has one place that documents every shape
// crossing the frontend/backend boundary. Keep this in sync with the actual
// FastAPI response shapes in backend/schemas/ whenever a contract changes.

/**
 * @typedef {Object} Player
 * @property {string} player_id
 * @property {string} username
 * @property {number} level
 * @property {number} total_xp
 * @property {number} streak_days
 * @property {string} last_active
 * @property {string|null} guild_id
 * @property {number} hint_tokens
 */

/**
 * @typedef {Object} AccuracyHistory
 * @property {string} topic
 * @property {number} attempts
 * @property {number} correct
 * @property {number} recent_accuracy
 * @property {boolean[]} last_5_results
 */

/**
 * @typedef {Object} Room
 * @property {string} topic
 * @property {string} label
 * @property {'locked'|'unlocked'|'weak'|'mastered'} status
 * @property {number} recent_accuracy
 * @property {string[]} prerequisites
 */

/**
 * @typedef {Object} Dungeon
 * @property {string} dungeon_id
 * @property {string} domain
 * @property {Room[]} rooms
 * @property {string|null} next_topic - suggested by knowledge graph
 */

/**
 * @typedef {Object} Question
 * @property {string} question_id
 * @property {string} topic
 * @property {'easy'|'medium'|'hard'} difficulty
 * @property {string} question
 * @property {string} hint
 * @property {number} enemy_hp
 * @property {string} enemy_name
 * (expected_answer is intentionally absent — backend must never send it)
 */

/**
 * @typedef {Object} AnswerSubmitPayload
 * @property {string} question_id
 * @property {string} player_answer
 * @property {number} response_time_ms
 */

/**
 * @typedef {Object} AnswerResult
 * @property {'correct'|'partial'|'incorrect'} verdict
 * @property {number} score
 * @property {number} damage_multiplier
 * @property {string} feedback
 * @property {number} xp_gained
 * @property {number} damage_dealt
 * @property {number} player_hp_after
 * @property {number} enemy_hp_after
 */

/**
 * @typedef {Object} GraphNode
 * @property {string} id
 * @property {string} label
 * @property {number} accuracy
 * @property {'locked'|'unlocked'|'weak'|'mastered'} status
 */

/**
 * @typedef {Object} GraphEdge
 * @property {string} source
 * @property {string} target
 */

/**
 * @typedef {Object} DashboardData
 * @property {{nodes: GraphNode[], edges: GraphEdge[]}} graph
 * @property {{topic: string, difficulty: string, timestamp: string}[]} difficulty_history
 * @property {{score: number, verdict: string, timestamp: string}[]} score_history
 * @property {Object.<string, number>} topic_accuracies
 */

export {};
