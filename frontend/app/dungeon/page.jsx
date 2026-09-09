'use client';

import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Lock } from 'lucide-react';
import clsx from 'clsx';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useGameStore } from '@/store/useGameStore';
import { useAuthStore } from '@/store/useAuthStore';
import { learning, game } from '@/lib/api/client';
import { layoutGraph } from '@/lib/graphLayout';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelButton from '@/components/ui/PixelButton';
import XPBar from '@/components/XPBar';
import ChainLink from '@/components/ChainLink';
import PixelSprite from '@/components/PixelSprite';
import { monsterForTopic } from '@/lib/sprites/monsterSprites';

// This map renders exactly what the backend computes for this learner:
// real per-room unlock/accuracy status from GET /game/dungeon/{id}
// (backend/routes/game.py::_annotate_rooms_for_player) merged with the real,
// prerequisite-ordered competency gap analysis from GET /learning/pathway
// (backend/services/learning_engine.py::analyse_competencies) -- the same
// engine /stats already uses. An earlier version of this page (see git
// history, commit "meow") replaced a working, backend-driven map with a
// hand-written fictional course list; this restores the real version and
// generalizes it from the single hardcoded DSA dungeon to every curriculum
// the learner has selected.
const STATUS_STYLE = {
  locked: 'bg-stone-light border-black opacity-50',
  unlocked: 'bg-stone border-arcane',
  weak: 'bg-stone border-blood',
  mastered: 'bg-stone border-gold',
};

const PRIORITY_TONE = {
  critical: 'blood',
  high: 'ember',
  medium: 'gold',
  maintain: 'arcane',
  unassessed: 'stone',
};

export default function DungeonMapPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
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
    queryKey: ['curricula', 'en'],
    queryFn: () => learning.getCurricula('en'),
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
    queryKey: ['pathway', player?.player_id, activeSlug],
    queryFn: () => learning.getPathway(player.player_id, activeSlug),
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

  // rowHeight must be >= the room tile's rendered height (tile - 20 = 130px)
  // plus a visible gap, or adjacent depth rows overlap on the map.
  const tile = 150;
  const rowHeight = 170;

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

  const bossRoom = dungeon?.rooms?.find((r) => r.is_boss) || null;

  const graph = useMemo(
    () => Object.fromEntries(rooms.map((r) => [r.topic, r.prerequisites])),
    [rooms]
  );
  const positions = useMemo(() => layoutGraph({ graph, colWidth: 170, rowHeight }), [graph]);

  if (!ready || (!curriculaData && !dungeonError)) {
    return <p className="font-body text-parchment-dim text-center mt-10">Descending into the dungeon…</p>;
  }

  if (dungeonError) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10">
        <p className="font-body text-blood text-center">{dungeonError}</p>
        <PixelButton variant="ghost" onClick={() => matchedDungeon && loadDungeon(matchedDungeon.dungeon_id)}>
          RETRY
        </PixelButton>
      </div>
    );
  }

  if (!activeSlug) {
    return (
      <p className="font-body text-parchment-dim text-center mt-10">
        Pick at least one specialty in your profile to see a pathway here.
      </p>
    );
  }

  if (loadingDungeon || !dungeon || pathwayLoading) {
    return <p className="font-body text-parchment-dim text-center mt-10">Descending into the dungeon…</p>;
  }

  const xs = rooms.map((r) => positions[r.topic]?.x ?? 0);
  const ys = rooms.map((r) => positions[r.topic]?.y ?? 0);
  const minX = rooms.length ? Math.min(...xs) : 0;
  const maxY = rooms.length ? Math.max(...ys) : 0;
  const offsetX = -minX + 80;
  const bossTop = maxY + rowHeight;
  const bossHeight = tile - 10;

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

  function handleBossClick() {
    if (!dungeon.boss_unlocked || !matchedDungeon) return;
    router.push(`/boss/${matchedDungeon.dungeon_id}`);
  }

  return (
    <div>
      <div className="mb-6 flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
        <div>
          <h1 className="font-display text-sm text-parchment">{activeCurriculum?.name || dungeon.domain}</h1>
          {dungeon.next_topic && (
            <p className="font-body text-arcane mt-1">
              The dungeon senses weakness in{' '}
              <strong>{rooms.find((r) => r.topic === dungeon.next_topic)?.label || dungeon.next_topic}</strong>.
            </p>
          )}
        </div>
        <div className="flex items-center gap-3">
          {curricula.length > 1 && (
            <select
              value={activeSlug || ''}
              onChange={(e) => setSelectedSlug(e.target.value)}
              className="bg-stone border-2 border-black font-display text-[9px] text-parchment px-2 py-2 outline-none cursor-pointer"
            >
              {curricula.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
          <div className="w-full md:w-64">
            <XPBar level={player.level} totalXp={player.total_xp} />
          </div>
        </div>
      </div>

      <PixelPanel className="overflow-x-auto">
        <div
          className="relative mx-auto"
          style={{ width: offsetX * 2 + tile, height: bossTop + bossHeight + 30, minWidth: 600 }}
        >
          <svg className="absolute inset-0 w-full h-full pointer-events-none">
            {edges.map((e, i) => {
              const from = positions[e.from];
              const to = positions[e.to];
              if (!from || !to) return null;
              return (
                <ChainLink
                  key={i}
                  x1={from.x + offsetX + tile / 2}
                  y1={from.y + tile / 2}
                  x2={to.x + offsetX + tile / 2}
                  y2={to.y + tile / 2}
                  thickness={20}
                />
              );
            })}
          </svg>

          {rooms.map((room) => {
            const pos = positions[room.topic];
            if (!pos) return null;
            const locked = room.status === 'locked';
            const monster = monsterForTopic(room.topic);
            return (
              <button
                key={room.topic}
                onClick={() => handleRoomClick(room)}
                style={{ left: pos.x + offsetX, top: pos.y, width: tile, height: tile - 20 }}
                className={clsx(
                  'absolute flex flex-col items-center justify-center gap-1 border-4 p-2 transition-transform',
                  'hover:-translate-y-1',
                  selectedTopic === room.topic && 'ring-2 ring-parchment',
                  STATUS_STYLE[room.status] || STATUS_STYLE.locked
                )}
              >
                {locked ? (
                  <Lock size={28} />
                ) : (
                  <PixelSprite src={monster.image} grid={monster.grid} palette={monster.palette} size={40} title={monster.name} />
                )}
                <span className="font-display text-[8px] text-parchment text-center leading-tight">
                  {room.label}
                </span>
                {!locked && (
                  <span className="font-body text-sm text-parchment-dim">
                    {Math.round(room.completion * 100)}%
                  </span>
                )}
              </button>
            );
          })}

          {/* boss room, one row below the deepest topic */}
          {bossRoom && (
            <button
              disabled={!dungeon.boss_unlocked}
              onClick={handleBossClick}
              style={{ left: offsetX + tile / 4, top: bossTop, width: tile * 1.5, height: bossHeight }}
              className={clsx(
                'absolute flex flex-col items-center justify-center gap-1 border-4 p-2',
                dungeon.boss_unlocked ? 'bg-stone border-ember' : 'bg-stone-light border-black opacity-50'
              )}
            >
              {dungeon.boss_unlocked ? (
                <PixelSprite
                  src={monsterForTopic('boss').image}
                  grid={monsterForTopic('boss').grid}
                  palette={monsterForTopic('boss').palette}
                  size={48}
                  title={monsterForTopic('boss').name}
                />
              ) : (
                <Lock size={28} />
              )}
              <span className="font-display text-[8px] text-parchment text-center">
                {dungeon.boss_unlocked ? 'THE DOMAIN BOSS' : 'CLEAR ALL ROOMS FIRST'}
              </span>
            </button>
          )}
        </div>
      </PixelPanel>

      <div className="flex gap-3 mt-4 flex-wrap">
        <PixelBadge tone="arcane">unlocked</PixelBadge>
        <PixelBadge tone="blood">weak — needs practice</PixelBadge>
        <PixelBadge tone="gold">mastered</PixelBadge>
        <PixelBadge tone="stone">locked</PixelBadge>
      </div>

      {selected && (
        <PixelPanel className="mt-4">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <h2 className="font-display text-xs text-parchment">{selected.label}</h2>
              <p className="font-body text-parchment-dim mt-1 max-w-lg">
                {competencyByTopic.get(selected.topic)?.description}
              </p>
            </div>
            {selected.priority && (
              <PixelBadge tone={PRIORITY_TONE[selected.priority] || 'stone'}>
                {selected.priority === 'unassessed' ? 'not yet assessed' : `${selected.priority} gap`}
              </PixelBadge>
            )}
          </div>
          <div className="flex flex-wrap gap-4 mt-3 font-body text-sm text-parchment-dim">
            {selected.observedLevel != null && <span>Observed level: {selected.observedLevel.toFixed(1)} / 5</span>}
            {selected.gap != null && <span>Gap to target: {selected.gap.toFixed(1)}</span>}
            <span>Room accuracy: {Math.round((selected.recent_accuracy || 0) * 100)}%</span>
          </div>
          {selected.recommendedAction && (
            <p className="font-body text-arcane mt-2 text-sm">{selected.recommendedAction}</p>
          )}
          <PixelButton
            variant={selected.status === 'locked' ? 'ghost' : 'primary'}
            className="mt-3"
            disabled={selected.status === 'locked'}
            onClick={() => handleRoomClick(selected)}
          >
            {selected.status === 'locked' ? 'LOCKED — CLEAR PREREQUISITES FIRST' : 'START QUEST'}
          </PixelButton>
        </PixelPanel>
      )}

      {pathwayOrder.length > 0 && (
        <PixelPanel className="mt-4">
          <h2 className="font-display text-xs text-parchment mb-3">RECOMMENDED ORDER</h2>
          <p className="font-body text-parchment-dim text-sm mb-3">
            Computed from your real gaps and this domain&apos;s prerequisites — largest, most foundational gaps first.
          </p>
          <ol className="flex flex-col gap-2">
            {pathwayOrder.map((item) => (
              <li key={item.competency_id}>
                <button
                  onClick={() => setSelectedTopic(item.competency_id)}
                  className={clsx(
                    'w-full text-left flex items-center gap-3 px-3 py-2 border-2 border-black font-body text-sm',
                    selectedTopic === item.competency_id ? 'bg-arcane text-void' : 'bg-stone text-parchment'
                  )}
                >
                  <span className="font-display text-[9px] shrink-0">#{item.step}</span>
                  <span className="flex-1">{item.label}</span>
                  <PixelBadge tone={PRIORITY_TONE[item.priority] || 'stone'}>{item.priority}</PixelBadge>
                </button>
              </li>
            ))}
          </ol>
        </PixelPanel>
      )}
    </div>
  );
}
