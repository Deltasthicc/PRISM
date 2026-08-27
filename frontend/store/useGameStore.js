'use client';

import { create } from 'zustand';
import { game } from '@/lib/api/client';

export const useGameStore = create((set, get) => ({
  dungeon: null,
  loadingDungeon: false,
  dungeonError: null,

  // active fight
  currentQuestion: null, // Question shape from lib/types.js
  combat: null, // { playerHp, playerHpMax, enemyHp, enemyHpMax, enemyName }
  enteringRoom: false,
  questionStartedAt: null,

  // last answer outcome, shown before returning to the map
  lastResult: null,
  submitting: false,
  submitError: null,

  hintRevealed: false,
  powerupResult: null,
  powerupError: null,

  async loadDungeon(dungeonId) {
    set({ loadingDungeon: true, dungeonError: null });
    try {
      const dungeon = await game.getDungeon(dungeonId);
      set({ dungeon, loadingDungeon: false });
    } catch (e) {
      set({ dungeonError: e.message, loadingDungeon: false });
    }
  },

  async enterRoom(topic) {
    set({ enteringRoom: true, lastResult: null, hintRevealed: false, submitError: null });
    try {
      const q = await game.enterRoom(topic);
      set({
        currentQuestion: q,
        combat: {
          playerHp: get().combat?.playerHp ?? 100,
          playerHpMax: 100,
          enemyHp: q.enemy_hp,
          enemyHpMax: q.enemy_hp_max ?? q.enemy_hp,
          enemyName: q.enemy_name,
        },
        enteringRoom: false,
        questionStartedAt: Date.now(),
      });
    } catch (e) {
      // submitError, not dungeonError -- the combat/boss pages that call
      // enterRoom() only render dungeonError on the separate /dungeon map
      // page. Setting the wrong field here left a locked/unreachable room
      // (e.g. the boss before every topic is cleared) rendering a blank
      // page with zero feedback instead of the actual error message.
      set({ enteringRoom: false, submitError: e.message });
    }
  },

  async submitAnswer(answerText) {
    const { currentQuestion, questionStartedAt } = get();
    if (!currentQuestion) return null;
    set({ submitting: true, submitError: null });
    try {
      const response_time_ms = Date.now() - (questionStartedAt ?? Date.now());
      const result = await game.submitAnswer({
        question_id: currentQuestion.question_id,
        player_answer: answerText,
        response_time_ms,
      });
      set((s) => ({
        submitting: false,
        lastResult: result,
        combat: {
          ...s.combat,
          playerHp: result.player_hp_after,
          enemyHp: result.enemy_hp_after,
        },
      }));
      return result;
    } catch (e) {
      set({ submitting: false, submitError: e.message });
      return null;
    }
  },

  async revealHint(playerId, decrementFn) {
    const questionId = get().currentQuestion?.question_id;
    if (!questionId) return;
    try {
      await game.useHint(playerId, questionId);
      set({ hintRevealed: true, submitError: null });
      decrementFn?.();
    } catch (e) {
      set({ submitError: e.message });
    }
  },

  // `onPlayerEffect` lets the caller react to server-authoritative changes
  // this powerup made (bonus XP, refilled hint tokens) without this store
  // needing to know about useAuthStore.
  async usePowerup(playerId, onPlayerEffect) {
    const questionId = get().currentQuestion?.question_id;
    set({ powerupError: null });
    try {
      const result = await game.usePowerup(playerId, questionId);
      set((s) => ({
        // force_correct/force_correct_heal don't touch enemy HP immediately --
        // they queue a guaranteed-correct verdict the backend applies on the
        // next submit, which reports the real hits_required/hits_landed then.
        // heal_to_full is the one effect with no server-side HP pool to
        // report back, so it's applied here directly.
        combat: s.combat
          ? { ...s.combat, playerHp: result.heal_to_full ? s.combat.playerHpMax : s.combat.playerHp }
          : s.combat,
        hintRevealed: result.hint_text ? true : s.hintRevealed,
        powerupResult: result,
      }));
      onPlayerEffect?.(result);
      return result;
    } catch (e) {
      set({ powerupError: e.message });
      return null;
    }
  },

  resetCombat() {
    set({ currentQuestion: null, combat: null, lastResult: null, hintRevealed: false, powerupResult: null });
  },

  async retreat() {
    await game.respawn().catch(() => {});
    get().resetCombat();
  },
}));
