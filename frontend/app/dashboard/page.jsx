'use client';

import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import MLDashboard from '@/components/MLDashboard';

export default function DashboardPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const { t } = useLanguage();

  if (!ready || !player) return null;

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="font-display text-sm text-parchment">{t('dashboard.heading')}</h1>
        <p className="font-body text-parchment-dim">
          {t('dashboard.subtitleBefore')} {player.username} {t('dashboard.subtitleAfter')}
        </p>
      </div>
      <MLDashboard playerId={player.player_id} />
    </div>
  );
}
