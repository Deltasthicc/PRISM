'use client';

import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import ReactFlow, { Background, Handle, Position, useViewport } from 'reactflow';
import 'reactflow/dist/style.css';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import { ai } from '@/lib/api/client';
import { layoutGraph } from '@/lib/graphLayout';
import { TOPIC_LABELS } from '@/lib/statMap';
import PixelPanel from './ui/PixelPanel';
import PixelBadge from './ui/PixelBadge';
import PixelSprite from './PixelSprite';
import ChainLink from './ChainLink';
import { monsterForTopic } from '@/lib/sprites/monsterSprites';

const NODE_WIDTH = 140;
const NODE_HEIGHT = 90;

// ReactFlow 11's edge renderer only draws an edge once it considers both
// endpoint nodes "measured" (their Handle DOM bounds recorded internally).
// That measurement pass never completes for this project's React 19 +
// ReactFlow 11 combination -- reproducible even with a stock, uncustomized
// 2-node/1-edge example -- so edges silently never render, regardless of
// edge type. Rather than depend on that broken subsystem, this draws the
// chain-link connectors as an independent overlay driven by ReactFlow's
// (separately, and correctly) tracked pan/zoom viewport.
function GraphChainOverlay({ positions, edges }) {
  const { x: vpX, y: vpY, zoom } = useViewport();

  function toScreen(p) {
    return {
      x: (p.x + NODE_WIDTH / 2) * zoom + vpX,
      y: (p.y + NODE_HEIGHT / 2) * zoom + vpY,
    };
  }

  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 0 }}>
      {edges.map((e, i) => {
        const from = positions[e.source];
        const to = positions[e.target];
        if (!from || !to) return null;
        const a = toScreen(from);
        const b = toScreen(to);
        return <ChainLink key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y} thickness={Math.max(8, 16 * zoom)} />;
      })}
    </svg>
  );
}

const STATUS_COLOR = {
  locked: '#443d34',
  unlocked: '#6ee7d0',
  weak: '#c43d3d',
  mastered: '#e8b339',
};

const DIFFICULTY_VALUE = { easy: 1, medium: 2, hard: 3 };
const VERDICT_TONE = { correct: 'arcane', partial: 'gold', incorrect: 'blood' };

function StoneNode({ data }) {
  const monster = monsterForTopic(data.id);
  return (
    <div
      className="font-display text-[8px] text-center px-2 py-2 border-4 border-black bg-stone flex flex-col items-center gap-1"
      style={{ width: 140, boxShadow: `0 0 0 2px ${STATUS_COLOR[data.status]}` }}
    >
      <Handle type="target" position={Position.Top} style={{ background: '#000' }} />
      <PixelSprite src={monster.image} grid={monster.grid} palette={monster.palette} size={28} title={monster.name} />
      <div className="text-parchment leading-tight">{data.label}</div>
      <div className="font-body text-sm mt-1" style={{ color: STATUS_COLOR[data.status] }}>
        {Math.round(data.accuracy * 100)}%
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: '#000' }} />
    </div>
  );
}

const nodeTypes = { stone: StoneNode };

export default function MLDashboard({ playerId }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['dashboard', playerId],
    queryFn: () => ai.getDashboard(playerId),
    enabled: !!playerId,
    // 15s instead of 6s: this panel runs ReactFlow + two recharts and a full
    // DB read on every refetch; nothing meaningful changes for the player
    // between answers, so tighter polling was pure background churn.
    refetchInterval: 15000,
  });

  const { nodes, edges, positions } = useMemo(() => {
    if (!data?.graph) return { nodes: [], edges: [], positions: {} };
    const positions = layoutGraph();
    const nodes = data.graph.nodes.map((n) => ({
      id: n.id,
      type: 'stone',
      position: positions[n.id] || { x: 0, y: 0 },
      data: n,
    }));
    return { nodes, edges: data.graph.edges, positions };
  }, [data]);

  const scoreChartData = useMemo(
    () => (data?.score_history || []).slice().reverse().map((s, i) => ({ idx: i + 1, score: s.score })),
    [data]
  );

  const difficultyChartData = useMemo(
    () =>
      (data?.difficulty_history || [])
        .slice()
        .reverse()
        .map((d, i) => ({ idx: i + 1, value: DIFFICULTY_VALUE[d.difficulty] || 1, topic: d.topic })),
    [data]
  );

  if (error) {
    return (
      <PixelPanel variant="arcane">
        <p className="font-body text-blood">Could not load the AI dashboard: {error.message}</p>
      </PixelPanel>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <PixelPanel variant="arcane" className="lg:col-span-2 lg:h-[430px] relative">
        <div className="flex items-center justify-between mb-2">
          <h3 className="font-display text-xs text-arcane">KNOWLEDGE GRAPH</h3>
          <PixelBadge tone="arcane" className="animate-pulse">LIVE</PixelBadge>
        </div>
        {isLoading ? (
          <p className="font-body text-parchment-dim">Reading the dungeon&apos;s mind…</p>
        ) : (
          <div className="h-[300px]">
            <ReactFlow
              nodes={nodes}
              edges={[]}
              nodeTypes={nodeTypes}
              fitView
              proOptions={{ hideAttribution: true }}
              nodesDraggable={false}
              nodesConnectable={false}
              elementsSelectable={false}
            >
              <Background color="#18140f" gap={16} />
              <GraphChainOverlay positions={positions} edges={edges} />
            </ReactFlow>
          </div>
        )}
        <Legend />
      </PixelPanel>

      <div className="flex flex-col gap-4">
        <PixelPanel>
          <h3 className="font-display text-xs text-gold mb-2">RL DIFFICULTY TUNER</h3>
          <ResponsiveContainer width="100%" height={130}>
            <LineChart data={difficultyChartData}>
              <CartesianGrid stroke="#18140f" />
              <XAxis dataKey="idx" stroke="#a89f8c" fontSize={10} />
              <YAxis
                domain={[0, 3]}
                ticks={[1, 2, 3]}
                tickFormatter={(v) => ['', 'easy', 'med', 'hard'][v]}
                stroke="#a89f8c"
                fontSize={10}
              />
              <Tooltip
                contentStyle={{ background: '#18140f', border: '2px solid #000', fontFamily: 'var(--font-vt323)' }}
                formatter={(v) => ['', 'easy', 'medium', 'hard'][v]}
              />
              <Line type="stepAfter" dataKey="value" stroke="#e8b339" strokeWidth={3} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </PixelPanel>

        <PixelPanel>
          <h3 className="font-display text-xs text-ember mb-2">NLP JUDGE SCORES</h3>
          <ResponsiveContainer width="100%" height={130}>
            <BarChart data={scoreChartData}>
              <CartesianGrid stroke="#18140f" />
              <XAxis dataKey="idx" stroke="#a89f8c" fontSize={10} />
              <YAxis domain={[0, 1]} stroke="#a89f8c" fontSize={10} />
              <Tooltip contentStyle={{ background: '#18140f', border: '2px solid #000', fontFamily: 'var(--font-vt323)' }} />
              <Bar dataKey="score" fill="#ff6b3d" />
            </BarChart>
          </ResponsiveContainer>
        </PixelPanel>
      </div>

      <PixelPanel className="lg:col-span-3">
        <h3 className="font-display text-xs text-gold mb-2">RECENT FIGHTS</h3>
        {isLoading ? (
          <p className="font-body text-parchment-dim">Loading recent fights…</p>
        ) : (data?.score_history || []).length === 0 ? (
          <p className="font-body text-parchment-dim">No fights recorded yet.</p>
        ) : (
          <div className="flex flex-col gap-2 max-h-80 overflow-y-auto">
            {data.score_history.map((s, i) => (
              <div key={i} className="border-2 border-black bg-stone-dark px-3 py-2">
                <div className="flex items-center justify-between flex-wrap gap-2">
                  <span className="font-body text-parchment">{TOPIC_LABELS[s.topic] || s.topic}</span>
                  <div className="flex items-center gap-2">
                    <PixelBadge tone="stone">{s.difficulty}</PixelBadge>
                    <PixelBadge tone={VERDICT_TONE[s.verdict]}>{s.verdict}</PixelBadge>
                    <span className="font-body text-sm text-parchment-dim">{Math.round(s.score * 100)}%</span>
                  </div>
                </div>
                <p className="font-body text-sm text-parchment-dim mt-1">Q: {s.question}</p>
                <p className="font-body text-sm text-parchment-dim">You: {s.player_answer}</p>
              </div>
            ))}
          </div>
        )}
      </PixelPanel>
    </div>
  );
}

function Legend() {
  return (
    <div className="flex gap-3 mt-2 flex-wrap">
      {Object.entries(STATUS_COLOR).map(([status, color]) => (
        <div key={status} className="flex items-center gap-1 font-body text-xs text-parchment-dim">
          <span className="w-3 h-3 border-2 border-black inline-block" style={{ backgroundColor: color }} />
          {status}
        </div>
      ))}
    </div>
  );
}
