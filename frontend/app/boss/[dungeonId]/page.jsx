'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useGameStore } from '@/store/useGameStore';
import { useAuthStore } from '@/store/useAuthStore';
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
import { heroOrDefault, queuedPowerupText } from '@/lib/sprites/heroSprites';

const VERDICT_TONE = { correct: 'arcane', partial: 'gold', incorrect: 'blood' };
const BOSS_TOPIC = 'boss';

export default function BossFightPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();

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
    if (ready) enterRoom(BOSS_TOPIC);
    return () => resetCombat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  useEffect(() => {
    if (!lastResult) return;
    fetchMe();
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

  if (submitError && !currentQuestion) {
    return (
      <div className="max-w-xl mx-auto text-center mt-10">
        <p className="font-body text-blood text-lg">{submitError}</p>
        <PixelButton className="mt-4" onClick={() => router.push('/dungeon')}>
          BACK TO THE DUNGEON
        </PixelButton>
      </div>
    );
  }

  if (enteringRoom && !currentQuestion) {
    return (
      <p className="font-body text-ember text-center mt-10 animate-flicker">
        The dungeon shakes. The Big-O Devourer awakens…
      </p>
    );
  }

  if (!currentQuestion || !combat) return null;

  // See the equivalent note in app/combat/[roomId]/page.jsx: the client-side
  // HP pool and the backend's actual clear condition are independent and can
  // disagree, so trust whichever says the fight is over first.
  const bossDefeated = combat.enemyHp <= 0 || Boolean(lastResult?.dungeon_completed);
  const playerDefeated = combat.playerHp <= 0;
  const fightOver = bossDefeated || playerDefeated;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!answer.trim() || submitting) return;
    await submitAnswer(answer);
    setAnswer('');
  }

  async function handleContinue() {
    setAnswer('');
    await enterRoom(BOSS_TOPIC);
  }

  function handleVictory() {
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
      <div className="text-center">
        <h1 className="font-display text-sm text-ember">BOSS ENCOUNTER</h1>
        <p className="font-body text-parchment-dim">Every question pulls from a different topic. Stay sharp.</p>
      </div>

      <PixelPanel className="border-ember">
        <div className="flex justify-between items-center mb-2">
          <span className="font-display text-[10px] text-ember">THE BIG-O DEVOURER</span>
          <div className="flex items-center gap-2">
            <PixelBadge tone="ember">{currentQuestion.difficulty}</PixelBadge>
            <PixelBadge tone="gold">up to {currentQuestion.max_damage} DMG</PixelBadge>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <VillainSprite topic="boss" hitKey={lastResult?.submission_id} defeated={bossDefeated} size={88} />
          <div className="flex-1 relative">
            <DamageNumber items={floats} />
            <HealthBar current={combat.enemyHp} max={combat.enemyHpMax} label="BOSS" kind="enemy" />
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
        {hintRevealed && <p className="font-body text-arcane mt-3 text-base">💡 {currentQuestion.hint}</p>}
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
            id="boss-answer"
            label="YOUR ANSWER"
            textarea
            rows={4}
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            disabled={submitting}
          />
          <PixelButton type="submit" variant="primary" disabled={submitting || !answer.trim()}>
            {submitting ? 'THE JUDGE CONSIDERS…' : 'STRIKE'}
          </PixelButton>
        </form>
      )}

      {lastResult && !fightOver && (
        <PixelPanel>
          <PixelBadge tone={VERDICT_TONE[lastResult.verdict]}>{lastResult.verdict.toUpperCase()}</PixelBadge>
          <p className="font-body text-lg mt-2">{lastResult.feedback}</p>
          <PixelButton variant="ghost" className="mt-4" onClick={handleContinue}>
            CONTINUE
          </PixelButton>
        </PixelPanel>
      )}

      {bossDefeated && (
        <PixelPanel variant="arcane">
          <h2 className="font-display text-sm text-gold mb-2">THE DUNGEON FALLS SILENT</h2>
          <p className="font-body text-lg">You&apos;ve cleared the dungeon. The Devourer dissolves into data.</p>
          <PixelButton variant="gold" className="mt-4" onClick={handleVictory}>
            CLAIM VICTORY
          </PixelButton>
        </PixelPanel>
      )}

      {playerDefeated && (
        <PixelPanel>
          <h2 className="font-display text-sm text-blood mb-2">THE DEVOURER PREVAILS — FOR NOW</h2>
          <p className="font-body text-lg">Retreat, sharpen your weak topics, and return stronger.</p>
          <PixelButton variant="danger" className="mt-4" onClick={handleRetreat}>
            RETREAT
          </PixelButton>
        </PixelPanel>
      )}
    </div>
  );
}
