'use client';

import { useState } from 'react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { game } from '@/lib/api/client';
import { TOPIC_LABELS } from '@/lib/statMap';
import Panel from '@/components/ui/Panel';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

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

  const bossRemaining = guild ? Math.max(0, guild.raid_boss_hp) : 0;
  const bossPct = guild && guild.raid_boss_hp_max > 0
    ? Math.max(0, Math.min(100, (bossRemaining / guild.raid_boss_hp_max) * 100))
    : 0;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-5">
      <div>
        <h1 className="font-sans text-lg font-bold text-[#00236f] text-center">Group practice raid</h1>
        <p className="font-sans text-sm text-[#757682] text-center mt-1">
          Team up with other learners and split a shared boss&apos;s questions between you.
        </p>
      </div>

      {!guild ? (
        <Panel variant="accent" className="text-center">
          <p className="font-sans text-sm text-[#444651] mb-4">
            You haven&apos;t joined a raid party yet. Team up and split the boss&apos;s questions between you.
          </p>
          {error && (
            <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2 mb-3">
              {error}
            </p>
          )}
          <Button onClick={handleJoin} disabled={loading}>
            {loading ? 'Gathering allies…' : 'Join a raid party'}
          </Button>
        </Panel>
      ) : (
        <>
          <Panel>
            <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">{guild.name}</h2>
            <div className="flex flex-col gap-2">
              {guild.members.map((m) => (
                <div
                  key={m.player_id}
                  className="flex justify-between items-center border border-[#c5c5d3]/40 rounded-lg px-3 py-2"
                >
                  <span className="font-sans text-sm text-[#131b2e]">
                    {m.username}
                    {m.player_id === player.player_id && (
                      <Badge tone="accent" className="ml-2">You</Badge>
                    )}
                  </span>
                  <Badge tone="default">{TOPIC_LABELS[m.topic] || m.topic}</Badge>
                </div>
              ))}
            </div>
          </Panel>

          <Panel variant="accent">
            <div className="flex justify-between items-baseline mb-1.5">
              <h2 className="font-sans text-sm font-bold text-[#131b2e]">Raid boss progress</h2>
              <span className="font-mono text-xs text-[#757682]">
                {bossRemaining}/{guild.raid_boss_hp_max} HP remaining
              </span>
            </div>
            <div className="h-2.5 w-full bg-[#eaedff] rounded-full overflow-hidden">
              <div
                className="h-full bg-[#00236f] rounded-full transition-all duration-300"
                style={{ width: `${bossPct}%` }}
              />
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
