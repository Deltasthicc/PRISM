'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Lock, CheckCircle2, AlertTriangle, Circle } from 'lucide-react';
import clsx from 'clsx';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useGameStore } from '@/store/useGameStore';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning, game } from '@/lib/api/client';
import { layoutGraph } from '@/lib/graphLayout';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// This map renders exactly what the backend computes for this learner: real
// per-room unlock/accuracy status from GET /game/dungeon/{id}
// (backend/routes/game.py::_annotate_rooms_for_player) merged with the real,
// prerequisite-ordered competency gap analysis from GET /learning/pathway
// (backend/services/learning_engine.py::analyse_competencies) -- the same
// engine /stats already uses. This page is on the always-visible
// professional path (NavBar never gates it behind the opt-in Quest Mode
// toggle -- see components/NavBar.jsx), so unlike /boss and /combat it uses
// the same plain professional-shell components (Panel/Badge/Button) as
// /stats and /academy, not the Pixel*/dungeon-skin kit that's reserved for
// Quest Mode's own opt-in routes.
const STATUS_ICON = { locked: Lock, unlocked: Circle, weak: AlertTriangle, mastered: CheckCircle2 };
const STATUS_TONE = { locked: 'default', unlocked: 'accent', weak: 'danger', mastered: 'success' };
const STATUS_BORDER = {
  locked: 'border-[#c5c5d3]/50 opacity-60',
  unlocked: 'border-[#00236f]/40',
  weak: 'border-[#b3261e]/50',
  mastered: 'border-[#1a7f4b]/50',
};
const PRIORITY_TONE = { critical: 'danger', high: 'warning', medium: 'warning', maintain: 'success', unassessed: 'default' };

export default function DungeonMapPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const { language } = useLanguage();
  const player = useAuthStore((s) => s.player);
  const dungeon = useGameStore((s) => s.dungeon);
  const loadingDungeon = useGameStore((s) => s.loadingDungeon);
  const dungeonError = useGameStore((s) => s.dungeonError);
  const loadDungeon = useGameStore((s) => s.loadDungeon);

  const [selectedSlug, setSelectedSlug] = useState(null);
  const [selectedTopic, setSelectedTopic] = useState(null);

  const { data: profileData } = useQuery({
    queryKey: ['learning-profile', player?.player_id],
    queryFn: () => learning.getProfile(player.player_id),
    enabled: ready && !!player,
  });
  const { data: curriculaData } = useQuery({
    queryKey: ['curricula', language],
    queryFn: () => learning.getCurricula(language),
    enabled: ready && !!player,
  });
  const { data: dungeonsData } = useQuery({
    queryKey: ['dungeons-list'],
    queryFn: () => game.listDungeons(),
    enabled: ready && !!player,
  });

  const profile = profileData?.profile;
  const curricula = curriculaData?.curricula || [];
  // A learner's own chosen goals (register/profile setup) drive which
  // pathways they see, same as /stats -- falls back to every curriculum only
  // when nothing has been picked yet.
  const targetSlugs = profile?.target_domains?.length ? profile.target_domains : curricula.map((c) => c.slug);
  const activeSlug = selectedSlug || targetSlugs[0] || curricula[0]?.slug;
  const activeCurriculum = curricula.find((c) => c.slug === activeSlug);
  const matchedDungeon = (dungeonsData || []).find((d) => d.slug === activeSlug);

  const { data: pathwayData, isLoading: pathwayLoading } = useQuery({
    queryKey: ['pathway', player?.player_id, activeSlug, language],
    queryFn: () => learning.getPathway(player.player_id, activeSlug, language),
    enabled: ready && !!player && !!activeSlug,
  });

  useEffect(() => {
    if (ready && matchedDungeon) loadDungeon(matchedDungeon.dungeon_id);
  }, [ready, matchedDungeon, loadDungeon]);

  useEffect(() => {
    setSelectedTopic(null);
  }, [activeSlug]);

  const competencyByTopic = useMemo(() => {
    const map = new Map();
    (pathwayData?.competencies || []).forEach((c) => map.set(c.competency_id, c));
    return map;
  }, [pathwayData]);

  const pathwayOrder = useMemo(() => pathwayData?.pathway || [], [pathwayData]);

  // rowHeight must be >= the node's rendered height (tile - 20 = 90px) plus
  // a visible gap, or adjacent depth rows overlap.
  const tile = 160;
  const rowHeight = 130;

  const rooms = useMemo(() => {
    if (!dungeon) return [];
    return (dungeon.rooms || [])
      .filter((r) => !r.is_boss)
      .map((room) => {
        const competency = competencyByTopic.get(room.topic);
        return {
          ...room,
          label: competency?.label || room.topic,
          prerequisites: competency?.prerequisites || [],
          gap: competency?.gap ?? null,
          priority: competency?.priority ?? null,
          observedLevel: competency?.observed_level ?? null,
          recommendedAction: pathwayOrder.find((p) => p.competency_id === room.topic)?.recommended_action || null,
        };
      });
  }, [dungeon, competencyByTopic, pathwayOrder]);

  const capstoneRoom = dungeon?.rooms?.find((r) => r.is_boss) || null;

  const graph = useMemo(
    () => Object.fromEntries(rooms.map((r) => [r.topic, r.prerequisites])),
    [rooms]
  );
  const positions = useMemo(() => layoutGraph({ graph, colWidth: 180, rowHeight }), [graph]);

  if (!ready || (!curriculaData && !dungeonError)) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading your pathway…</p>;
  }

  if (dungeonError) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10">
        <p className="font-sans text-sm text-[#b3261e] text-center">{dungeonError}</p>
        <Button variant="ghost" onClick={() => matchedDungeon && loadDungeon(matchedDungeon.dungeon_id)}>
          Retry
        </Button>
      </div>
    );
  }

  if (!activeSlug) {
    return (
      <p className="font-sans text-sm text-[#757682] text-center mt-10">
        Pick at least one specialty in your profile to see a pathway here.
      </p>
    );
  }

  if (loadingDungeon || !dungeon || pathwayLoading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading your pathway…</p>;
  }

  const xs = rooms.map((r) => positions[r.topic]?.x ?? 0);
  const ys = rooms.map((r) => positions[r.topic]?.y ?? 0);
  const minX = rooms.length ? Math.min(...xs) : 0;
  const maxY = rooms.length ? Math.max(...ys) : 0;
  const offsetX = -minX + 90;
  const capstoneTop = maxY + rowHeight;
  const capstoneHeight = tile - 60;

  const edges = [];
  rooms.forEach((r) => {
    r.prerequisites.forEach((pre) => {
      if (positions[pre]) edges.push({ from: pre, to: r.topic });
    });
  });

  const selected = rooms.find((r) => r.topic === selectedTopic) || null;

  function handleRoomClick(room) {
    setSelectedTopic(room.topic);
    if (room.status === 'locked') return;
    router.push(
      `/combat/${encodeURIComponent(room.topic)}?dungeon=${matchedDungeon.dungeon_id}&label=${encodeURIComponent(room.label)}`
    );
  }

  function handleCapstoneClick() {
    if (!dungeon.boss_unlocked || !matchedDungeon) return;
    router.push(`/boss/${matchedDungeon.dungeon_id}`);
  }

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-5">
      <div className="flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
        <div>
          <h1 className="font-sans text-lg font-bold text-[#00236f]">{activeCurriculum?.name || dungeon.domain}</h1>
          {dungeon.next_topic && (
            <p className="font-sans text-sm text-[#757682] mt-1">
              Your biggest current gap is in{' '}
              <strong className="text-[#131b2e]">
                {rooms.find((r) => r.topic === dungeon.next_topic)?.label || dungeon.next_topic}
              </strong>
              .
            </p>
          )}
        </div>
        {curricula.length > 1 && (
          <select
            value={activeSlug || ''}
            onChange={(e) => setSelectedSlug(e.target.value)}
            className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f] cursor-pointer"
          >
            {curricula.map((c) => (
              <option key={c.slug} value={c.slug}>
                {c.name}
              </option>
            ))}
          </select>
        )}
      </div>

      <Panel className="overflow-x-auto">
        <div
          className="relative mx-auto"
          style={{ width: offsetX * 2 + tile, height: capstoneTop + capstoneHeight + 30, minWidth: 600 }}
        >
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ overflow: 'visible' }}>
            {edges.map((e, i) => {
              const from = positions[e.from];
              const to = positions[e.to];
              if (!from || !to) return null;
              return (
                <line
                  key={i}
                  x1={from.x + offsetX + tile / 2}
                  y1={from.y + tile / 2 - 30}
                  x2={to.x + offsetX + tile / 2}
                  y2={to.y + tile / 2 - 30}
                  stroke="#c5c5d3"
                  strokeWidth={2}
                />
              );
            })}
          </svg>

          {rooms.map((room) => {
            const pos = positions[room.topic];
            if (!pos) return null;
            const locked = room.status === 'locked';
            const Icon = STATUS_ICON[room.status] || Lock;
            return (
              <button
                key={room.topic}
                onClick={() => handleRoomClick(room)}
                style={{ left: pos.x + offsetX, top: pos.y, width: tile, height: tile - 60 }}
                className={clsx(
                  'absolute flex flex-col items-center justify-center gap-1.5 rounded-xl border-2 bg-white p-3 shadow-sm transition-transform',
                  'hover:-translate-y-0.5 hover:shadow-md',
                  selectedTopic === room.topic && 'ring-2 ring-[#00236f]',
                  STATUS_BORDER[room.status] || STATUS_BORDER.locked
                )}
              >
                <Icon
                  size={20}
                  className={clsx(
                    room.status === 'mastered' && 'text-[#1a7f4b]',
                    room.status === 'weak' && 'text-[#b3261e]',
                    room.status === 'unlocked' && 'text-[#00236f]',
                    room.status === 'locked' && 'text-[#757682]'
                  )}
                />
                <span className="font-sans text-xs font-semibold text-[#131b2e] text-center leading-tight">
                  {room.label}
                </span>
                {!locked && (
                  <span className="font-mono text-[10px] text-[#757682]">{Math.round(room.completion * 100)}%</span>
                )}
              </button>
            );
          })}

          {/* capstone assessment, one row below the deepest topic */}
          {capstoneRoom && (
            <button
              disabled={!dungeon.boss_unlocked}
              onClick={handleCapstoneClick}
              style={{ left: offsetX + tile / 4, top: capstoneTop, width: tile * 1.5, height: capstoneHeight }}
              className={clsx(
                'absolute flex flex-col items-center justify-center gap-1.5 rounded-xl border-2 p-3 shadow-sm',
                dungeon.boss_unlocked
                  ? 'bg-white border-[#fe932c]/60 hover:-translate-y-0.5 hover:shadow-md transition-transform'
                  : 'bg-[#f7f7fb] border-[#c5c5d3]/50 opacity-60'
              )}
            >
              {dungeon.boss_unlocked ? (
                <CheckCircle2 size={20} className="text-[#fe932c]" />
              ) : (
                <Lock size={20} className="text-[#757682]" />
              )}
              <span className="font-sans text-xs font-semibold text-[#131b2e] text-center">
                {dungeon.boss_unlocked ? 'Capstone assessment' : 'Clear every competency first'}
              </span>
            </button>
          )}
        </div>
      </Panel>

      <div className="flex gap-3 flex-wrap">
        <Badge tone="accent">unlocked</Badge>
        <Badge tone="danger">weak — needs practice</Badge>
        <Badge tone="success">mastered</Badge>
        <Badge tone="default">locked</Badge>
      </div>

      {selected && (
        <Panel>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="font-sans text-base font-bold text-[#131b2e]">{selected.label}</h2>
              <p className="font-sans text-sm text-[#757682] mt-1 max-w-lg">
                {competencyByTopic.get(selected.topic)?.description}
              </p>
            </div>
            {selected.priority && (
              <Badge tone={PRIORITY_TONE[selected.priority] || 'default'}>
                {selected.priority === 'unassessed' ? 'not yet assessed' : `${selected.priority} gap`}
              </Badge>
            )}
          </div>
          <div className="flex flex-wrap gap-4 mt-3 font-sans text-sm text-[#757682]">
            {selected.observedLevel != null && <span>Observed level: {selected.observedLevel.toFixed(1)} / 5</span>}
            {selected.gap != null && <span>Gap to target: {selected.gap.toFixed(1)}</span>}
            <span>Practice accuracy: {Math.round((selected.recent_accuracy || 0) * 100)}%</span>
          </div>
          {selected.recommendedAction && (
            <p className="font-sans text-sm text-[#00236f] mt-2">{selected.recommendedAction}</p>
          )}
          <Button
            variant={selected.status === 'locked' ? 'ghost' : 'primary'}
            className="mt-3"
            disabled={selected.status === 'locked'}
            onClick={() => handleRoomClick(selected)}
          >
            {selected.status === 'locked' ? 'Locked — clear prerequisites first' : 'Practice this competency'}
          </Button>
        </Panel>
      )}

      {pathwayOrder.length > 0 && (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-1">Recommended order</h2>
          <p className="font-sans text-sm text-[#757682] mb-3">
            Computed from your real gaps and this domain&apos;s prerequisites — largest, most foundational gaps first.
          </p>
          <ol className="flex flex-col gap-2">
            {pathwayOrder.map((item) => (
              <li key={item.competency_id}>
                <button
                  onClick={() => setSelectedTopic(item.competency_id)}
                  className={clsx(
                    'w-full text-left flex items-center gap-3 px-3 py-2.5 rounded-lg border font-sans text-sm transition-colors',
                    selectedTopic === item.competency_id
                      ? 'bg-[#f2f3ff] border-[#00236f]/40'
                      : 'bg-white border-[#c5c5d3]/30 hover:border-[#00236f]/30'
                  )}
                >
                  <span className="font-mono text-xs text-[#757682] shrink-0">#{item.step}</span>
                  <span className="flex-1 text-[#131b2e] font-medium">{item.label}</span>
                  <Badge tone={PRIORITY_TONE[item.priority] || 'default'}>{item.priority}</Badge>
                </button>
              </li>
            ))}
          </ol>
        </Panel>
      )}
    </div>
  );
}
