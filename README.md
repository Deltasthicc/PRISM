# SIH Learning Tool — SkillQuest Skill Intelligence

An explainable, cross-domain skill-intelligence platform built for **SIH26101** (MoSPI): it
builds a role-aware competency profile, runs an explainable gap analysis against a target level,
orders a prerequisite-aware learning pathway, recommends verified learning catalogs, turns
uploaded material into source-grounded quizzes, and closes the loop with adaptive practice
evidence. It is built on top of **SkillQuest**, an adaptive DSA-learning RPG — that game is still
here, fully playable, and now one of four domains ("Quest mode") rather than the whole product.

> **This is a prototype, honestly labeled as one.** iGOT Karmayogi and NSSTA/TPAC are
> `catalog-fallback` integrations today, not live enrolment/progress syncs — there is no public
> partner API for either, and this repo never fabricates one. Identity is username-only with no
> password or server-side authorization check on any route. Neither is safe for real officials or
> real personnel data. See [`docs/SIH26101_FEASIBILITY_AND_ROADMAP.md`](docs/SIH26101_FEASIBILITY_AND_ROADMAP.md)
> and [`docs/SIH26101_ORCHESTRATION_PLAN.md`](docs/SIH26101_ORCHESTRATION_PLAN.md) for exactly what
> that means and the ordered plan to close it.

## What's real right now (verified in this repo, not just claimed)

Everything below was actually run — a live `pytest` pass, a live `uvicorn` boot, and live HTTP
calls through the full profile → assessment → quiz → admin loop — not re-quoted from another
session.

- **4 domains, 1 engine.** `backend/services/curricula.py` holds DSA Fundamentals, Official
  Statistics & Data Governance, Public Policy & Programme Evaluation, and Digital & AI Literacy —
  34 competencies total, each with a stable ID, prerequisites, and a 1–5 target level, validated
  for cycles and dangling references at import time. Every domain is a real, enterable dungeon:
  `db/seed.py`'s `seed_curricula_dungeons()` materializes rooms + a namespaced boss
  (`boss::official-statistics`, not a shared `"boss"` string) for the three new domains alongside
  DSA's existing seeding.
- **A working competency-gap engine.** `backend/services/learning_engine.py` blends demonstrated
  quest evidence (65%) with self-assessment (35%) when both exist, explains its evidence source in
  plain text, caps the pathway target by experience level, and orders the resulting gaps
  prerequisite-first — all deterministic, no black box.
- **Grounded quiz generation that can't silently hallucinate.** `backend/services/quiz_generator.py`
  validates every Gemini-drafted question against the source text (exactly four unique options, a
  valid answer index, and a `source_excerpt` that must be an exact substring of the uploaded
  material); anything that fails validation, or any request with no API key configured, falls back
  to a deterministic extractive generator instead of failing or fabricating.
- **Bounded file ingestion.** `backend/services/content_ingestion.py` extracts text from TXT, MD,
  PDF, and DOCX uploads with a 5&nbsp;MB cap, a 100-page PDF cap, and a DOCX zip-expansion guard —
  and only ever persists a hash, character count, and short excerpt, never the original file or
  full extracted text.
- **An honest integration boundary.** `backend/services/learning_catalog.py` never returns a
  fabricated course ID or enrolment record. Every recommendation is either a link to this app's own
  adaptive practice quest (real, clickable) or a link to iGOT/NSSTA's public catalog pages, tagged
  `catalog-fallback` — flip to `configured` only once a real partner adapter exists behind
  `IGOT_API_BASE_URL` / `NSSTA_API_BASE_URL`.
- **A cross-domain room-unlock fix.** The original DSA-only unlock check
  (`routes/game.py::_is_room_unlocked_for_player`) only understood the hardcoded DSA topic graph;
  any non-DSA room would have been permanently locked. It now falls back to
  `services/curricula.py` for any topic outside that graph, so the new domains are actually
  playable, not just seeded.
- **The Academy UI.** `frontend/app/academy` (backing component: `components/AcademyHub.jsx`) is a
  full profile form, a per-domain diagnostic, an explainable pathway view, and the quiz
  upload/preview flow, built on the existing Pixel design-system primitives.
- **An honest admin view.** `frontend/app/admin` shows aggregate-only organizational gap data (no
  individual learner record, ever) with an explicit banner stating there is no RBAC boundary yet.
- **42/42 backend tests pass**, including 18 new tests for the cross-domain engine, the quiz
  fallback, bounded ingestion, and the room-unlock fix — run with
  `backend/.venv/Scripts/python.exe -m pytest`, not assumed.
- **`npm audit --omit=dev` reports 0 vulnerabilities** after bumping the `next`/postcss dependency
  override that was pinning an old vulnerable version.

## What's aim, not yet reality

- **No live iGOT or NSSTA integration.** There is no public partner API for either today (verified
  directly against both portals and against APISetu). Production activation needs an approved
  sandbox, credentials, and a real adapter behind the interface already sketched in
  `learning_catalog.py`.
- **No real identity.** Username-only, no password, no server-derived session, no RBAC on any
  route. A pilot cannot run on this — it needs government-approved OIDC/SAML, server-side subject
  derivation, and role checks on every protected endpoint.
- **No official competency ownership.** The four curricula are a reviewed, internally-consistent
  *demonstration* taxonomy, not an MoSPI/NSSTA/CBC-approved role-to-competency map. A real pilot
  needs a named domain owner to sign off on targets and descriptors.
- **SQLite, not PostgreSQL; no migrations.** `ensure_columns()` (see `db/database.py`) is the only
  schema-evolution mechanism and is a no-op on anything but SQLite. Fine for a prototype, not for
  scale.
- **No content-review workflow.** Generated quiz questions are demo-ready, not publish-ready — there
  is no draft/review/approve/retire state yet, so nothing stops an unreviewed item from being
  served.
- **No real multilingual pipeline, malware scanning, queues, or observability.** All flagged
  explicitly, none faked.

The full, itemized version of this list — with acceptance gates, a prioritized backlog, an
orchestration model, and a judge Q&A stress test — is in
[`docs/SIH26101_ORCHESTRATION_PLAN.md`](docs/SIH26101_ORCHESTRATION_PLAN.md).

## How it plays

1. **Create a character** — username only in this prototype (see [Player identity](#player-identity)).
2. **Open the Academy** (`/academy`) — build a profile from designation, department, assignment,
   qualifications, experience, prior training, preferred language, and career goal.
3. **Diagnose gaps** — rate yourself 0–5 per competency; the engine blends that with real quest
   evidence where it exists and explains exactly how.
4. **Follow the pathway** — a prerequisite-ordered list of what to close first, each step showing
   its observed level, target, gap, and priority.
5. **Practice** — enter the matching dungeon room; a fresh AI question is generated at a difficulty
   chosen from your recent accuracy on that competency.
6. **Answer in free text** — an AI grader judges meaning, not exact wording: correct / partial /
   incorrect.
7. **Generate a grounded quiz** — upload TXT, Markdown, PDF, or DOCX; every accepted question cites
   an exact excerpt from your own material.
8. **Check the org view** (`/admin`) — aggregate, PII-free gap demand across every learner.

## Architecture

```text
SIH Learning Tool/
|-- frontend/   Next.js website — no direct AI or DB access
|-- backend/    FastAPI server — API, SQLite, game + skill-intelligence rules, default AI implementation
`-- services/   Optional standalone AI engine (real sentence-embedding grading, not used by default)
```

The frontend only ever calls the backend's REST API (`frontend/lib/api/client.js` is the one file
that calls `fetch`, including the `learning` export added for this project). The backend is the
single source of truth for game and skill-intelligence state and the only thing that touches the
database or an LLM.

## Run it locally

**Backend** (start first):

```powershell
cd backend
if (-not (Test-Path .venv\Scripts\python.exe)) { py -3.12 -m venv .venv }
& .\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m uvicorn main:app --reload --port 8000
```

Set `GEMINI_API_KEY` in `backend/.env` (get one at [Google AI Studio](https://aistudio.google.com/apikey))
to enable live question/quiz generation and semantic grading — every AI-dependent path has a
deterministic fallback if you skip this. Runs at `http://localhost:8000`, auto-seeds all four
dungeons plus a demo DSA player on first launch. Docs at `http://localhost:8000/docs`.

**Frontend:**

```powershell
cd frontend
npm install
if (-not (Test-Path .env.local)) { Copy-Item .env.local.example .env.local }
npm run dev
```

Runs at `http://localhost:3000`. Without the backend running, every action fails with
"Could not reach the backend."

### Player identity

Username only, no password — a deliberate simplification for this build, not a real auth system.
Don't reuse a real password as your username. This must be replaced with real identity before any
non-synthetic learner or organizational data touches this app.

## Competency graph & data model

`backend/services/curricula.py` is the data-driven catalog for the three new domains; every
competency has a globally unique ID, label, description, prerequisites, and target level.
`backend/services/knowledge_graph.py`'s `TOPIC_GRAPH` remains the DSA domain's own graph — kept
separate deliberately rather than folded into `curricula.py` too, since DSA's seeding, tests, and
frontend sprite/label mappings all still key off it directly (see
`docs/SIH26101_FEASIBILITY_AND_ROADMAP.md` §2.3 for why unifying the two is a follow-up, not done
here).

| Competency (Official Statistics & Data Governance) | Prerequisites |
|---|---|
| `os_statistical_foundations` | — |
| `os_data_collection` | `os_statistical_foundations` |
| `os_visualization` | `os_statistical_foundations` |
| `os_data_quality` | `os_data_collection` |
| `os_sampling_design` | `os_statistical_foundations`, `os_data_collection` |
| `os_gis` | `os_data_quality`, `os_visualization` |
| `os_big_data` | `os_data_quality` |
| `os_official_statistics` | `os_sampling_design`, `os_data_quality` |
| `os_ml` | `os_official_statistics`, `os_big_data` |

(this is a DAG, not a tree — several competencies have more than one prerequisite; `curricula.py`
is the authoritative source, and Public Policy / Digital Literacy follow the same shape)

A competency unlocks once every prerequisite is demonstrated or its room is cleared (checked
live, cross-domain, in `routes/game.py::_is_room_unlocked_for_player`); each domain's mastery
challenge unlocks once every one of its competencies is proven.

State lives in SQLite: `players`, `learner_profiles`, `competency_assessments`,
`learning_materials`, `generated_quizzes`, `accuracy_history` (rolling last-5 accuracy per player
per topic), `dungeons` (now `curriculum_slug`-tagged) / `rooms`, `questions`, `answer_submissions`,
`guilds`, `game_sessions`. SQLite is suitable for this local prototype only — see the roadmap for
the PostgreSQL/Alembic migration this needs before any pilot.

## AI logic

| System | How it works |
|---|---|
| Question generation | Gemini prompt → question + expected answer + hint, per topic/difficulty. Always fresh, never a static bank. |
| Answer grading | Gemini judges semantic correctness of free text against the expected answer → `correct`/`partial`/`incorrect`. |
| Difficulty tuning | Epsilon-greedy bandit: 90% picks by recent accuracy (>80%→hard, >50%→medium, else easy), 10% random exploration. Boss fights are always hard. |
| Topic routing | Recommends the weakest currently-unlocked topic. |
| Competency-gap analysis | Deterministic 0–5 blend (65% demonstrated / 35% self-assessed when both exist), explicit evidence text, experience-capped target, priority tiers. |
| Learning pathway | Topological (prerequisites-first) ordering of gaps by severity, with a recommended next action per step. |
| Quiz generation | Gemini draft constrained to the uploaded document, validated against a strict source-grounding schema; deterministic extractive fallback if unavailable or invalid. |

**Fallbacks** (no AI-dependent step can hard-fail): question generation retries Gemini 3× with
backoff, then falls back to a templated question. Grading falls back to word-overlap scoring. Quiz
generation falls back to a deterministic extractive generator. Difficulty and topic routing never
call an LLM at all.

## API reference

Full request/response schemas are served live at `http://localhost:8000/docs`.

| Endpoint | Purpose |
|---|---|
| `POST /game/player/create` | Create a player |
| `GET /game/player/{id}` / `by-username/{username}` | Fetch stats + accuracy history |
| `GET /game/dungeons` / `dungeon/{id}` | List / fetch a dungeon and its rooms (list now includes `slug`) |
| `POST /game/session/start` | Start a run, bump login streak, open first room |
| `POST /game/room/enter` | Enter a room — picks difficulty, generates the question |
| `POST /game/answer/submit` | **Core loop**: grade, apply XP/damage, update accuracy, check room/dungeon completion |
| `POST /game/hint/use` | Spend a hint token |
| `GET /game/dungeon/{id}/next-topic` | Recommend next room |
| `POST /game/guild/create` / `join` · raid endpoints | Guild + raid lifecycle |
| `GET /game/leaderboard` / `leaderboard/guild` | XP rankings |
| `POST /ai/question/generate` · `/ai/answer/judge` · `/ai/difficulty/next` · `/ai/graph/next-topic` | Direct access to each AI subsystem |
| `GET /ai/dashboard/{player_id}` | Full AI Core dashboard payload |
| `GET /learning/curricula` | All 4 domains and their competencies |
| `GET/PUT /learning/profile/{player_id}` | Read or upsert a learner's competency profile |
| `POST /learning/assessment/{player_id}` | Run an explainable gap analysis + pathway |
| `GET /learning/pathway/{player_id}?curriculum_slug=...` | Recompute the latest pathway |
| `POST /learning/quiz/generate` (multipart) | Upload a document, generate a grounded quiz |
| `GET /learning/quiz/{player_id}` | List a learner's generated quizzes |
| `GET /learning/integrations/status` | Honest iGOT/NSSTA configured-vs-fallback status |
| `GET /learning/admin/overview` | Aggregate-only organizational gap view |
| `GET /health`, `GET /`, `GET /docs` | Liveness, app info, Swagger UI |

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, React 19, Tailwind, Zustand, TanStack Query, React Flow, Recharts |
| Backend | FastAPI, SQLAlchemy, SQLite |
| AI | Google Gemini; optional `services/` upgrade adds `sentence-transformers` |
| Document ingestion | `pypdf`, `python-docx` (bounded — see `services/content_ingestion.py`) |

## For developers

<details>
<summary><strong>Full directory structure</strong> (click to expand)</summary>

```text
SIH Learning Tool/
├── README.md
├── docs/
│   ├── SIH26101_FEASIBILITY_AND_ROADMAP.md   Full PS analysis + engineering audit
│   ├── SIH26101_ORCHESTRATION_PLAN.md        Weighted ledger, lanes, backlog, gates, timeline
│   └── CLAUDE_SESSION_DOSSIERS.md            Pointer to the two Claude-authored dossiers
├── backend/
│   ├── .env.example
│   ├── main.py                    App entry point, CORS, router registration, DB init + seeding
│   ├── requirements.txt / requirements-dev.txt
│   ├── db/
│   │   ├── database.py            Engine/session setup
│   │   └── seed.py                Demo DSA dungeon + seed_curricula_dungeons() for the other 3
│   ├── models/                    SQLAlchemy tables
│   │   ├── player.py, accuracy_history.py, dungeon.py, question.py, submission.py, guild.py, session.py
│   │   └── learning.py            LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz
│   ├── schemas/
│   │   └── learning.py            Pydantic request/response shapes for /learning/*
│   ├── routes/
│   │   ├── game.py                All /game/* endpoints (now with cross-domain unlock fallback)
│   │   ├── ai_real.py             All /ai/* endpoints (calls Gemini directly)
│   │   └── learning.py            All /learning/* endpoints
│   ├── services/                  Pure logic — no DB, no HTTP (except learning_catalog's env read)
│   │   ├── game_logic.py, knowledge_graph.py, ai_client.py, heroes.py, monsters.py
│   │   ├── curricula.py           The 4-domain, 34-competency data-driven catalog
│   │   ├── learning_engine.py     Explainable gap/pathway calculation
│   │   ├── learning_catalog.py    Honest iGOT/NSSTA recommendation + status boundary
│   │   ├── content_ingestion.py   Bounded TXT/MD/PDF/DOCX extraction
│   │   └── quiz_generator.py      Grounded generation + deterministic fallback
│   └── tests/
│       ├── test_progression.py, test_combat_model.py     Original 24 tests
│       └── test_learning_platform.py                     18 new cross-domain/learning tests
├── frontend/
│   ├── app/
│   │   ├── academy/                Wraps AcademyHub — profile, diagnostic, pathway, quiz upload
│   │   ├── admin/                  Aggregate organizational overview
│   │   ├── login/, register/, dungeon/, combat/[roomId]/, boss/[dungeonId]/, guild/, leaderboard/, stats/, dashboard/
│   ├── components/
│   │   ├── AcademyHub.jsx          The Academy's full UI
│   │   └── ...existing game/dashboard components + ui/ Pixel primitives
│   ├── lib/api/client.js           The ONLY file that calls fetch, now with a `learning` export
│   └── ...
└── services/                       Optional standalone AI engine (off by default) — unchanged from SkillQuest
```

</details>

- **Backend layout**: `routes/` = HTTP handlers only; `services/` = pure game/AI logic (no DB, no
  HTTP); `models/` = SQLAlchemy tables; `schemas/` = Pydantic request/response shapes.
- **Tests**:
  ```powershell
  cd backend
  & .\.venv\Scripts\Activate.ps1
  python -m pytest
  ```
  42 tests, no server or API key needed — every AI-dependent path under test either mocks the
  network call or exercises the deterministic fallback directly.
- **CORS**: the backend only allows credentialed requests from `FRONTEND_ORIGINS` — update it
  (comma-separated) if you deploy the frontend somewhere other than `localhost:3000`.
- **Provenance**: this repository's game engine and UI kernel come from
  [`SkillQuest-AI-Dungeon`](https://github.com/Abhiraj-Agarwal/SkillQuest-AI-Dungeon); the
  cross-domain skill-intelligence layer (`services/curricula.py`, `learning_engine.py`,
  `quiz_generator.py`, `routes/learning.py`, `components/AcademyHub.jsx`) originated in a separate
  AI-assisted design session and was integrated, completed, and verified here — see
  `docs/CLAUDE_SESSION_DOSSIERS.md` for the full provenance trail.
