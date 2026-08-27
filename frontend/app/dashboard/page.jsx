'use client';

import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import MLDashboard from '@/components/MLDashboard';

export default function DashboardPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);

  if (!ready || !player) return null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-sm text-parchment">AI CORE</h1>
        <p className="font-body text-parchment-dim">
          What the dungeon currently knows about {player.username} — live from the LLM, RL tuner, and NLP judge.
        </p>
      </div>
      <MLDashboard playerId={player.player_id} />
    </div>
  );
}
