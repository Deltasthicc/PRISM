'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useGameStore } from '@/store/useGameStore';
import { useAuthStore } from '@/store/useAuthStore';
import { TOPIC_LABELS } from '@/lib/statMap';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelButton from '@/components/ui/PixelButton';
import PixelInput from '@/components/ui/PixelInput';
import PixelBadge from '@/components/ui/PixelBadge';
import HealthBar from '@/components/HealthBar';
import HintToken from '@/components/HintToken';
import DamageNumber from '@/components/DamageNumber';
import VillainSprite from '@/components/VillainSprite';
import PowerupButton from '@/components/PowerupButton';
import PixelSprite from '@/components/PixelSprite';
import { monsterForTopic } from '@/lib/sprites/monsterSprites';
import { heroOrDefault, queuedPowerupText } from '@/lib/sprites/heroSprites';

const VERDICT_TONE = { correct: 'arcane', partial: 'gold', incorrect: 'blood' };

export default function CombatPage() {
  const { ready } = useRequireAuth();
  const params = useParams();
  const router = useRouter();
  const topic = params.roomId;

  const player = useAuthStore((s) => s.player);
  const spendHintToken = useAuthStore((s) => s.spendHintToken);
  const fetchMe = useAuthStore((s) => s.fetchMe);

  const currentQuestion = useGameStore((s) => s.currentQuestion);
  const combat = useGameStore((s) => s.combat);
  const enteringRoom = useGameStore((s) => s.enteringRoom);
  const lastResult = useGameStore((s) => s.lastResult);
  const submitting = useGameStore((s) => s.submitting);
  const submitError = useGameStore((s) => s.submitError);
  const hintRevealed = useGameStore((s) => s.hintRevealed);
  const enterRoom = useGameStore((s) => s.enterRoom);
  const submitAnswer = useGameStore((s) => s.submitAnswer);
  const revealHint = useGameStore((s) => s.revealHint);
  const resetCombat = useGameStore((s) => s.resetCombat);
  const retreat = useGameStore((s) => s.retreat);
  const triggerPowerup = useGameStore((s) => s.usePowerup);
  const powerupResult = useGameStore((s) => s.powerupResult);
  const powerupError = useGameStore((s) => s.powerupError);

  const [answer, setAnswer] = useState('');
  const [floats, setFloats] = useState([]);
  const floatTimeoutsRef = useRef([]);

  useEffect(() => {
    if (ready && topic) enterRoom(topic);
    return () => resetCombat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, topic]);

  useEffect(() => {
    if (!lastResult) return;
    fetchMe(); // resync level/xp/hint_tokens after the backend updates them
    const id = Date.now();
    const text =
      lastResult.verdict === 'correct'
        ? `-${lastResult.damage_dealt} HP  +${lastResult.xp_gained} XP`
        : lastResult.verdict === 'partial'
        ? `-${lastResult.damage_dealt} HP`
        : 'MISS';
    setFloats((f) => [...f, { id, text, tone: lastResult.verdict === 'correct' ? 'xp' : 'damage' }]);
    // Timeout is tracked in a ref and only cleared on unmount, not on the next
    // `lastResult` change — otherwise re-entering combat before 1s elapses
    // cancels this removal and leaves a permanent "ghost" float on screen.
    const t = setTimeout(() => setFloats((f) => f.filter((x) => x.id !== id)), 1000);
    floatTimeoutsRef.current.push(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastResult]);

  useEffect(() => {
    const timeouts = floatTimeoutsRef.current;
    return () => timeouts.forEach(clearTimeout);
  }, []);

  if (!ready) return null;

  if (enteringRoom && !currentQuestion) {
    return (
      <p className="font-body text-arcane text-center mt-10 animate-flicker">
        {monsterForTopic(topic).name} of {TOPIC_LABELS[topic] || topic} stirs… generating a challenge.
      </p>
    );
  }

  if (!currentQuestion || !combat) {
    return <p className="font-body text-blood text-center mt-10">{submitError || 'No active fight.'}</p>;
  }

  // The enemy's HP pool (client-side, scaled by player level/damage) and the
  // backend's actual room-clear condition (N correct answers) are computed
  // independently and can disagree — trust whichever says the fight is over
  // first, so the victory screen isn't stuck behind a HP bar that never
  // reaches zero for a high-level player against a large enemy pool.
  const enemyDefeated = combat.enemyHp <= 0 || Boolean(lastResult?.room_cleared);
  const playerDefeated = combat.playerHp <= 0;
  const fightOver = enemyDefeated || playerDefeated;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!answer.trim() || submitting) return;
    await submitAnswer(answer);
    setAnswer('');
  }

  async function handleContinue() {
    setAnswer('');
    await enterRoom(topic);
  }

  async function handleClaimVictory() {
    resetCombat();
    router.push('/dungeon');
  }

  async function handleRetreat() {
    await retreat();
    router.push('/dungeon');
  }

  async function handleUsePowerup() {
    await triggerPowerup(player.player_id, () => fetchMe());
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <PixelPanel variant="arcane">
        <div className="flex justify-between items-center mb-2">
          <span className="font-display text-[10px] text-ember">{combat.enemyName}</span>
          <div className="flex items-center gap-2">
            <PixelBadge tone={combat.enemyName.includes('Devourer') ? 'ember' : 'arcane'}>
              {currentQuestion.difficulty}
            </PixelBadge>
            <PixelBadge tone="gold">up to {currentQuestion.max_damage} DMG</PixelBadge>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <VillainSprite topic={topic} hitKey={lastResult?.submission_id} defeated={enemyDefeated} />
          <div className="flex-1 relative">
            <DamageNumber items={floats} />
            <HealthBar current={combat.enemyHp} max={combat.enemyHpMax} label="ENEMY" kind="enemy" />
          </div>
        </div>
      </PixelPanel>

      <PixelPanel>
        <div className="flex items-center gap-4">
          <PixelSprite
            src={heroOrDefault(player.hero_id).image}
            grid={heroOrDefault(player.hero_id).grid}
            palette={heroOrDefault(player.hero_id).palette}
            size={56}
            title={heroOrDefault(player.hero_id).name}
          />
          <div className="flex-1">
            <HealthBar current={combat.playerHp} max={combat.playerHpMax} label={player.username.toUpperCase()} kind="player" />
          </div>
        </div>
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <PowerupButton
            heroId={player.hero_id}
            usesRemaining={player.powerup_uses_remaining}
            resetsAt={player.powerup_resets_at}
            onUse={handleUsePowerup}
            disabled={fightOver}
          />
          {powerupError && <span className="font-body text-blood text-sm">{powerupError}</span>}
          {powerupResult && !powerupError && (
            <span className="font-body text-gold text-sm">
              {powerupResult.powerup_name} used!
              {powerupResult.queued ? ` ${queuedPowerupText(player.hero_id)}` : ''}
              {powerupResult.xp_awarded ? ` +${powerupResult.xp_awarded} XP` : ''}
            </span>
          )}
        </div>
      </PixelPanel>

      <PixelPanel>
        <p className="font-body text-xl text-parchment leading-relaxed">{currentQuestion.question}</p>
        {hintRevealed && (
          <p className="font-body text-arcane mt-3 text-base">💡 {currentQuestion.hint}</p>
        )}
        <div className="mt-3">
          <HintToken
            tokensRemaining={player.hint_tokens}
            maxTokens={3}
            used={hintRevealed}
            onUse={() => revealHint(player.player_id, spendHintToken)}
          />
        </div>
      </PixelPanel>

      {!fightOver && !lastResult && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <PixelInput
            id="answer"
            label="YOUR ANSWER"
            textarea
            rows={4}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="Explain your answer — paraphrasing is fine, the judge reads for meaning."
            disabled={submitting}
          />
          <PixelButton type="submit" disabled={submitting || !answer.trim()}>
            {submitting ? 'THE JUDGE CONSIDERS…' : 'ATTACK'}
          </PixelButton>
        </form>
      )}

      {lastResult && !fightOver && (
        <PixelPanel>
          <PixelBadge tone={VERDICT_TONE[lastResult.verdict]}>{lastResult.verdict.toUpperCase()}</PixelBadge>
          <p className="font-body text-lg mt-2">{lastResult.feedback}</p>
          <PixelButton variant="ghost" className="mt-4" onClick={handleContinue}>
            CONTINUE FIGHT
          </PixelButton>
        </PixelPanel>
      )}

      {enemyDefeated && (
        <PixelPanel variant="arcane">
          <h2 className="font-display text-sm text-gold mb-2">VICTORY</h2>
          <p className="font-body text-lg">{lastResult?.feedback}</p>
          <PixelButton variant="gold" className="mt-4" onClick={handleClaimVictory}>
            RETURN TO THE DUNGEON
          </PixelButton>
        </PixelPanel>
      )}

      {playerDefeated && (
        <PixelPanel>
          <h2 className="font-display text-sm text-blood mb-2">YOU HAVE FALLEN</h2>
          <p className="font-body text-lg">The wraith overwhelms you. Retreat and heal before trying again.</p>
          <PixelButton variant="danger" className="mt-4" onClick={handleRetreat}>
            RETREAT
          </PixelButton>
        </PixelPanel>
      )}
    </div>
  );
}
