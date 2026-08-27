'use client';

import { useQuery } from '@tanstack/react-query';
import { Trophy } from 'lucide-react';
import clsx from 'clsx';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { game } from '@/lib/api/client';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelButton from '@/components/ui/PixelButton';
import PixelSprite from '@/components/PixelSprite';
import { heroOrDefault } from '@/lib/sprites/heroSprites';

const RANK_TONE = ['gold', 'arcane', 'ember'];

export default function LeaderboardPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: () => game.getLeaderboard(),
    enabled: ready,
    refetchInterval: 10000, // was 5000 -- halved background query volume, still feels live
  });

  if (!ready) return null;

  const board = data?.leaderboard || [];

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <h1 className="font-display text-sm text-parchment text-center flex items-center justify-center gap-2">
        <Trophy size={18} className="text-gold" /> WEEKLY RANKS
      </h1>

      <PixelPanel>
        {isLoading ? (
          <p className="font-body text-parchment-dim">Tallying the realm&apos;s XP…</p>
        ) : isError ? (
          <div className="flex flex-col items-center gap-3">
            <p className="font-body text-blood">Could not load the leaderboard.</p>
            <PixelButton variant="ghost" onClick={() => refetch()}>RETRY</PixelButton>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {board.map((row, i) => {
              const hero = heroOrDefault(row.hero_id);
              return (
              <div
                key={row.player_id}
                className={clsx(
                  'flex items-center justify-between border-2 border-black px-3 py-2',
                  row.player_id === player?.player_id ? 'bg-arcane/20 border-arcane' : 'bg-stone-dark'
                )}
              >
                <div className="flex items-center gap-3">
                  <span className="font-display text-xs w-6 text-parchment-dim">#{i + 1}</span>
                  <PixelSprite src={hero.image} grid={hero.grid} palette={hero.palette} size={32} title={hero.name} className="border-2 border-black shrink-0" />
                  <div className="flex flex-col">
                    <span className="font-body text-lg text-parchment leading-tight">{row.username}</span>
                    <span className="font-body text-sm text-parchment-dim leading-tight">{hero.name}</span>
                  </div>
                  {i < 3 && <PixelBadge tone={RANK_TONE[i]}>TOP {i + 1}</PixelBadge>}
                </div>
                <div className="flex items-center gap-3">
                  <PixelBadge tone="gold">🔥 {row.streak_days}d</PixelBadge>
                  <span className="font-body text-lg text-gold">{row.total_xp} XP</span>
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
