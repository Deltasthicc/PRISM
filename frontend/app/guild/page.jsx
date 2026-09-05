'use client';

import { useState } from 'react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { game } from '@/lib/api/client';
import { TOPIC_LABELS } from '@/lib/statMap';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelButton from '@/components/ui/PixelButton';
import PixelBadge from '@/components/ui/PixelBadge';
import HealthBar from '@/components/HealthBar';

export default function GuildPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const [guild, setGuild] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleJoin() {
    setLoading(true);
    setError(null);
    try {
      const g = await game.joinGuildRaid(player.guild_id);
      setGuild(g);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  if (!ready || !player) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <h1 className="font-display text-sm text-parchment text-center">GUILD HALL</h1>

      {!guild ? (
        <PixelPanel variant="arcane" className="text-center">
          <p className="font-body text-lg text-parchment-dim mb-4">
            You haven&apos;t joined a raid party yet. Team up and split the boss&apos;s sub-puzzles between you.
          </p>
          {error && <p className="font-body text-blood mb-3">{error}</p>}
          <PixelButton variant="arcane" onClick={handleJoin} disabled={loading}>
            {loading ? 'GATHERING ALLIES…' : 'JOIN A RAID PARTY'}
          </PixelButton>
        </PixelPanel>
      ) : (
        <>
          <PixelPanel>
            <h2 className="font-display text-xs text-gold mb-2">{guild.name}</h2>
            <div className="flex flex-col gap-2">
              {guild.members.map((m) => (
                <div
                  key={m.player_id}
                  className="flex justify-between items-center border-2 border-black bg-stone-dark px-3 py-2"
                >
                  <span className="font-body text-lg text-parchment">
                    {m.username}
                    {m.player_id === player.player_id && (
                      <PixelBadge tone="arcane" className="ml-2">YOU</PixelBadge>
                    )}
                  </span>
                  <PixelBadge tone="gold">{TOPIC_LABELS[m.topic] || m.topic}</PixelBadge>
                </div>
              ))}
            </div>
          </PixelPanel>

          <PixelPanel className="border-ember">
            <h2 className="font-display text-xs text-ember mb-3">RAID BOSS PROGRESS</h2>
            <HealthBar
              current={guild.raid_boss_hp}
              max={guild.raid_boss_hp_max}
              label="BOSS HEALTH REMAINING"
              kind="enemy"
            />
          </PixelPanel>
        </>
      )}
    </div>
  );
}
