'use client';

import { useQuery } from '@tanstack/react-query';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { game } from '@/lib/api/client';
import { STAT_MAP, TOPIC_LABELS } from '@/lib/statMap';
import { heroOrDefault } from '@/lib/sprites/heroSprites';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelButton from '@/components/ui/PixelButton';
import PixelSprite from '@/components/PixelSprite';
import XPBar from '@/components/XPBar';

export default function StatSheetPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['player', player?.player_id],
    queryFn: () => game.getPlayer(player.player_id),
    enabled: ready && !!player,
  });

  if (!ready || !player) return null;

  const accuracies = data?.topic_accuracies || {};
  const history = data?.accuracy_history || [];
  // Totals aren't tracked as their own backend field -- they're just a sum
  // over the same per-topic attempts/correct rows the topic breakdown below
  // already renders, so no separate endpoint or schema change was needed.
  const totalAttempts = history.reduce((sum, h) => sum + (h.attempts || 0), 0);
  const totalCorrect = history.reduce((sum, h) => sum + (h.correct || 0), 0);
  const hero = heroOrDefault(player.hero_id);

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-5">
      <PixelPanel variant="arcane">
        <div className="flex flex-col md:flex-row md:items-center gap-4">
          <PixelSprite src={hero.image} grid={hero.grid} palette={hero.palette} size={88} title={hero.name} />
          <div className="flex-1">
            <h1 className="font-display text-sm text-parchment">{player.username}</h1>
            <p className="font-body text-arcane text-base mt-0.5">
              {hero.name} <span className="text-parchment-dim">— {hero.powerupName}</span>
            </p>
            <p className="font-body text-parchment-dim text-sm mt-1">{hero.powerupDescription}</p>
            <div className="flex gap-2 mt-2 flex-wrap">
              <PixelBadge tone="gold">🔥 {player.streak_days} day streak</PixelBadge>
              <PixelBadge tone="arcane">{player.hint_tokens} hints left</PixelBadge>
              <PixelBadge tone={hero.gender === 'male' ? 'arcane' : 'gold'}>{hero.gender}</PixelBadge>
            </div>
          </div>
          <div className="w-full md:w-60">
            <XPBar level={player.level} totalXp={player.total_xp} />
          </div>
        </div>
      </PixelPanel>

      <PixelPanel>
        <h2 className="font-display text-xs text-gold mb-4">PROGRESS</h2>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="border-2 border-black p-3 bg-stone-dark">
            <div className="font-display text-lg text-arcane">{totalCorrect}</div>
            <div className="font-body text-sm text-parchment-dim mt-1">questions solved</div>
          </div>
          <div className="border-2 border-black p-3 bg-stone-dark">
            <div className="font-display text-lg text-parchment">{totalAttempts}</div>
            <div className="font-body text-sm text-parchment-dim mt-1">questions attempted</div>
          </div>
          <div className="border-2 border-black p-3 bg-stone-dark">
            <div className="font-display text-lg text-gold">{player.streak_days}</div>
            <div className="font-body text-sm text-parchment-dim mt-1">day streak</div>
          </div>
        </div>
      </PixelPanel>

      <PixelPanel>
        <h2 className="font-display text-xs text-gold mb-4">CHARACTER STATS</h2>
        {isLoading ? (
          <p className="font-body text-parchment-dim">Reading your accuracy history…</p>
        ) : isError ? (
          <div className="flex flex-col items-center gap-3">
            <p className="font-body text-blood">Could not load your stats.</p>
            <PixelButton variant="ghost" onClick={() => refetch()}>RETRY</PixelButton>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(STAT_MAP).map(([topic, { stat, flavor }]) => {
              const acc = accuracies[topic] ?? 0;
              return (
                <div key={topic} className="border-2 border-black p-3 bg-stone-dark">
                  <div className="flex justify-between items-baseline">
                    <span className="font-display text-[10px] text-parchment">{stat.toUpperCase()}</span>
                    <span className="font-body text-lg text-gold">{Math.round(acc * 100)}</span>
                  </div>
                  <p className="font-body text-sm text-parchment-dim mt-1">
                    {TOPIC_LABELS[topic]} — {flavor}
                  </p>
                  <div className="h-2 w-full bg-black border-2 border-black mt-2">
                    <div className="h-full bg-gold" style={{ width: `${Math.round(acc * 100)}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </PixelPanel>
    </div>
  );
}
