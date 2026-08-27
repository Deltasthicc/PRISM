# SkillQuest — Frontend

Next.js 15 (App Router) frontend for **SkillQuest: The AI Dungeon**.

## Run it

```powershell
npm install
if (-not (Test-Path .env.local)) { Copy-Item .env.local.example .env.local }
npm run dev
```

Open http://localhost:3000. The backend (`../backend`, default `http://localhost:8000`) must be
running — set `NEXT_PUBLIC_API_URL` in `.env.local` if it's hosted elsewhere.

Every API call in the app goes through `lib/api/client.js`. No component, page, or store talks to
`fetch` directly.

## What's built

- **Player identity** — create/enter/logout pages, locally restored player session, and guarded routes
  via `lib/useRequireAuth.js`. This hackathon build does not implement password authentication.
- **DungeonMap** (`/dungeon`) — the 11-topic knowledge graph rendered as a literal level-select map:
  stone tiles connected by glowing prerequisite lines. Locked/unlocked/weak/mastered styling driven
  by live accuracy data. Boss room gates open once every topic exceeds 65% recent accuracy.
- **Combat** (`/combat/[roomId]`) — free-text answer box, segmented pixel HP bars for player + enemy,
  floating damage/XP numbers, hint tokens, multi-question fights against one enemy until it's defeated.
- **BossFight** (`/boss/[dungeonId]`) — same combat loop, bigger HP pool, questions rotate across all
  topics.
- **StatSheet** (`/stats`) — per-topic accuracy mapped to RPG stats (see `lib/statMap.js`).
- **Guild** (`/guild`) — join a raid party, see member topic-lanes and shared boss HP.
- **Leaderboard** (`/leaderboard`) — polls every 5s, highlights your row.
- **AI Core dashboard** (`/dashboard`) — the judge-facing panel: live knowledge graph (React Flow,
  same layout function as the dungeon map on purpose), RL difficulty history and NLP score history
  charts (Recharts). Polls every 6s.

## Folder structure

```
app/                  routes (App Router) — one folder per page
components/           game UI (HealthBar, XPBar, HintToken, MLDashboard, NavBar, DamageNumber)
components/ui/        pixel design system primitives (Panel, Button, Input, Badge)
lib/api/client.js      ← the ONLY file that calls fetch
lib/config.js          env-driven config (API URL)
lib/statMap.js          topic ↔ RPG stat names, mirrors backend TOPIC_GRAPH
lib/graphLayout.js      shared layout math for DungeonMap + MLDashboard's graph
store/                  Zustand: useAuthStore, useGameStore
```

## Known gaps

- Player identity is username-only for this build; there is no password authentication.
- See the root [README.md](../README.md) for the full API contract this frontend is built against.
