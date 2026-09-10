# PRISM — Personalized Readiness Intelligence & Skill Mapping

<div align="center">

**An 11-language, explainable competency-gap engine for government skill development — built for Smart India Hackathon 2026 (PS: 26101).**

[![CI](https://github.com/Deltasthicc/PRISM/actions/workflows/ci.yml/badge.svg)](https://github.com/Deltasthicc/PRISM/actions/workflows/ci.yml)
[![Keepalive](https://github.com/Deltasthicc/PRISM/actions/workflows/keepalive.yml/badge.svg)](https://github.com/Deltasthicc/PRISM/actions/workflows/keepalive.yml)
![Backend](https://img.shields.io/badge/backend-FastAPI%200.141-009688?logo=fastapi&logoColor=white)
![Frontend](https://img.shields.io/badge/frontend-Next.js%2015%20%2F%20React%2019-000000?logo=nextdotjs&logoColor=white)
![Database](https://img.shields.io/badge/database-PostgreSQL%20(Neon)-4169E1?logo=postgresql&logoColor=white)
![Languages](https://img.shields.io/badge/UI-11%20languages-orange)
![Tests](https://img.shields.io/badge/backend%20tests-967-brightgreen)

[Live demo](#-live-demo) · [What it does](#-what-prism-actually-does) · [Architecture](#-architecture) · [Quizzes](#-quizzes) · [DSA Sandbox](#-dsa-sandbox) · [Learner Assistant (RAG)](#-learner-assistant-rag) · [Voice AI](#-voice-ai-pipeline) · [What's real vs. mockup](#-whats-real-and-whats-a-mockup) · [Local setup](#-running-it-locally) · [API](#-api-reference) · [Known limitations](#-known-limitations)

</div>

---

## 📖 What PRISM actually does

Government officers (MoSPI-style: statistical officers, analysts, policy staff) need a way to know exactly *which* skills they're missing, *why*, and *what to do about it* — without a vague "take this course" recommendation. PRISM is a **deterministic, explainable competency-gap engine**: it blends a learner's self-assessment with demonstrated performance (quiz results, exercises, real code submissions) at a fixed **65% demonstrated / 35% self-assessed** weighting, maps the result against a curated, government-source-cited competency catalog, and generates a personalized learning pathway (the "Prerequisite Pathways" map) with a plain-language rationale for every gap it identifies.

**Four curricula, 55 competencies**, each traceable to an actual government or standards document (see [`backend/services/competency_docs.py`](backend/services/competency_docs.py) and [`curricula.py`](backend/services/curricula.py)):
- DSA Fundamentals
- Official Statistics & Data Governance
- Public Policy
- Digital Literacy

The whole UI and the deterministic gap-analysis prose is available in **11 languages** — English, Hindi, and the next 9 most-spoken languages from the 2011 Census (Bengali, Marathi, Telugu, Tamil, Gujarati, Urdu, Kannada, Odia, Malayalam) — switchable live from the navbar, no page reload required. See [Internationalization](#-internationalization) for what's machine-translated vs. what still needs a native-speaker review pass.

## 🖥️ Live demo

The backend is deployed on Render, backed by a Neon Postgres database:

- API: `https://prism-backend-2voe.onrender.com`
- Auth provider (Keycloak, largely vestigial in demo mode — see [Auth model](#-auth-model-read-this-before-you-judge-the-security)): `https://prism-keycloak.onrender.com`

There is no hosted frontend — everyone on the team runs `npm run dev` locally against the shared backend. A [`keepalive` workflow](.github/workflows/keepalive.yml) pings both services every 10 minutes so Render's free tier doesn't cold-start them mid-demo (a cold Keycloak boot is 3–4+ minutes).

> Free-tier constraints apply: cold starts on first request after idle, and Keycloak sits at roughly 90% of its 512MB memory cap. This is a hackathon demo environment, **not** a government-approved production deployment.

## 🔐 Auth model — read this before you judge the security

The real thing exists and is untouched: OIDC token verification and role-based access control live in [`backend/security/identity.py`](backend/security/identity.py) and [`backend/security/rbac.py`](backend/security/rbac.py).

In front of it sits **one deliberate, clearly-labeled demo bypass** ([`backend/routes/authorization.py`](backend/routes/authorization.py)):

```python
_DEMO_AUTH_DISABLED = os.environ.get("DISABLE_AUTH", "").strip().lower() in {"1", "true", "yes", "on"}
```

When `DISABLE_AUTH=true` (the deployed demo's setting), every request is granted a synthetic principal with **every** role and skips per-player ownership checks — there's no real identity distinguishing one caller from another while this is set. This exists because the shared Keycloak instance's cold-start latency was making the full OIDC flow unreliable during live demos; a username alone is enough to act as that player. Unset it (the default) and full OIDC/RBAC verification is restored with **zero code changes** — nothing about the real auth path was weakened or removed, it's just bypassed for the demo.

A companion piece, [`routes/dev_auth.py`](backend/routes/dev_auth.py), bridges that demo username login to a *real* Keycloak-issued bearer token so `/learning/*` routes (which expect a genuine `BoundPrincipal`) work end-to-end while browsing locally. Its own docstring is explicit that this is **not** a login backdoor and **not** the real browser OIDC/PKCE flow — that flow is still open work.

**Never set `DISABLE_AUTH=true` for a deployment handling real user data.**

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Client["Browser (per teammate, npm run dev)"]
        FE["Next.js 15 / React 19\nEN / HI via LanguageContext"]
    end

    subgraph Render["Render (shared, free tier)"]
        BE["FastAPI backend\n(DISABLE_AUTH=true in demo)"]
        KC["Keycloak\n(real OIDC provider)"]
    end

    NEON[("Neon Postgres")]
    GEMINI["Gemini API\n(quiz generation, AI routes)"]

    FE -- "NEXT_PUBLIC_API_URL" --> BE
    BE -- "SQLAlchemy + Alembic" --> NEON
    BE -. "dev_auth.py bridge" .-> KC
    BE -- "ai_client.py" --> GEMINI

    style Client fill:#eef2ff,stroke:#4f46e5
    style Render fill:#ecfdf5,stroke:#059669
```

There's also a **separate, standalone second FastAPI app** at repo root (`services/`, distinct from `backend/services/`) — an optional AI microservice reachable via `AI_SERVICE_URL`. By default the backend runs self-contained and never needs it.

## 🧩 Quizzes

There are two genuinely separate, working quiz mechanisms — not one quiz reused everywhere:

1. **Competency quiz bank** ([`backend/routes/competency_quiz.py`](backend/routes/competency_quiz.py)) — **174 hand-authored questions** (both multiple-choice and fill-in-the-blank) across **22 topics** spanning all four curricula, servable either as a whole topic (onboarding baseline, `/baseline-assessment`) or scoped to exactly one competency (`/practice`, reached from a Prerequisite Pathways room — see [`frontend/lib/competencyTopics.js`](frontend/lib/competencyTopics.js) for the full topic list). Every question traces back to a real, hash-verified government document registered in [`document_corpus.json`](backend/data/document_corpus.json) — **49 source documents** in total, including official GATE CS/IT question papers (DSA), MoSPI/NSSO/Census/DST publications (Official Statistics), UPSC prelims papers, DARPG/NITI Aayog/DoPT documents (Public Policy), and MeitY/I4C/NIELIT material (Digital Literacy) — loaded via [`hand_authored_questions.py`](backend/services/hand_authored_questions.py). Only one DSA competency (`binary_search`) has no verified questions yet.
2. **Grounded quiz generation** ([`learning_content.py`](backend/routes/learning_content.py), via [`quiz_generator.py`](backend/services/quiz_generator.py)) — upload your own `.txt`/`.md`/`.pdf`/`.docx` material from the Academy page and get back a fresh MCQ set with an exact source citation for every answer, with a local fallback generator when no Gemini key is configured.

Both the competency quiz and the DSA Sandbox write to the same `AccuracyHistory` table that drives Prerequisite Pathways room unlocking — finishing either kind of real practice moves the map forward, for every course and topic.

```mermaid
sequenceDiagram
    participant U as Officer
    participant FE as Frontend
    participant BE as Backend

    U->>FE: Sign in (any email/password, demo mode)
    FE->>BE: POST /game/login or /game/register
    BE-->>FE: Real player record
    U->>FE: Complete profile (CreateProfilePage)
    FE->>BE: POST /learning/profile
    U->>FE: Take baseline quiz (CompetencyQuizPage)
    FE->>BE: GET /learning/competency-quiz/questions?topic_id=...
    BE-->>FE: Source-cited MCQs
    U->>FE: Submit answers
    FE->>BE: POST /learning/competency-quiz/submit
    BE-->>FE: Score + redirect to /stats
    FE->>BE: GET /learning/pathway/{player_id}
    BE-->>FE: Real gap analysis, no hardcoded data
```

## 🧮 DSA Sandbox

A real coding workspace for the DSA Fundamentals curriculum ([`frontend/app/dsa-sandbox/`](frontend/app/dsa-sandbox/), [`backend/routes/dsa_sandbox.py`](backend/routes/dsa_sandbox.py)):

- **A real CodeMirror 6 editor** — syntax highlighting, line numbers, bracket matching, autocomplete, folding, four-space indentation, `Ctrl`/`Cmd`+`Enter` to run.
- **22 original problems** across every DSA topic (arrays, linked lists, trees, graphs, DP, sliding window, hashing, two pointers, backtracking, intervals, matrices, prefix sums, and more), each with two worked examples, constraints, and a collapsible solution outline.
- **Five real languages** — Python, JavaScript, Java, C++, C# — generated once per problem from shared type metadata ([`services/dsa_lang_gen.py`](backend/services/dsa_lang_gen.py)), not hand-duplicated five times.
- **A real judge, not a simulated pass/fail** — every submission runs against the public [Judge0](https://ce.judge0.com) API. Hidden test cases stay server-side.
- Solving a problem writes real practice evidence into the same `AccuracyHistory` row Prerequisite Pathways reads — a DSA Sandbox submission unlocks the map exactly like a competency quiz does.

## 🤖 Learner Assistant (RAG)

A real, access-filtered, cited retrieval engine ([`backend/ai/retrieval.py`](backend/ai/retrieval.py), [`ai/assistant.py`](backend/ai/assistant.py), exposed at `/assistant` in the frontend) — not a general-purpose chatbot, and it says so:

- **Real BM25 retrieval** over a real corpus: at backend startup, [`ai/seed_corpus.py`](backend/ai/seed_corpus.py) indexes all 174 hand-authored questions' `source_excerpt` fields — already-committed, human-reviewed quotes from real government documents — into an in-memory chunk store. No network fetch needed, so this works identically on a fresh clone.
- **Pre-retrieval access filtering** by tenant and role, before ranking — a chunk a caller isn't allowed to see is never scored, not just hidden after the fact.
- **Honest abstention** — if nothing retrieved clears the relevance threshold, the assistant says so explicitly (`insufficient_evidence`) instead of inventing an answer.
- **Every answer carries citations** — source document id, a real locator (page/section), and the exact quoted passage the answer is grounded in.
- **Graceful LLM degradation** — with a working `GEMINI_API_KEY`, the top evidence is handed to Gemini for a synthesized, still-grounded answer; without one (or on an API error), it falls back to a deterministic extractive answer quoting the top-matching evidence directly, rather than failing.
- Prompt-injection detection runs on every query before retrieval even starts.

## ✅ What's real, and what's a mockup

Being honest about this line is the point of this section — the frontend has a real split between pages backed by the actual engine and pages that are still visual placeholders for the demo narrative.

| Route | Status |
|---|---|
| `/login` → `/register` → `/baseline-assessment` | **Real.** Resolves an actual backend player via `useAuthStore`, then a real profile form, then a source-cited baseline quiz served by `routes/competency_quiz.py`. |
| `/stats` | **Real.** Every number comes from `GET /learning/pathway` — no hardcoded competency data. |
| `/dungeon` ("Prerequisite Pathways") | **Real, for all four curricula.** Driven by `GET /learning/pathway/{player_id}` (the same engine `/stats` uses) merged with real per-player room unlock status from `GET /game/dungeon/{id}`. "Practice this competency" opens `/practice`, a plain quiz scoped to that one competency; finishing it updates `AccuracyHistory`, which is what flips a room to unlocked/weak/mastered and advances the "biggest gap" pointer — verified live across every curriculum, not just DSA. |
| `/dsa-sandbox` | **Real.** See [DSA Sandbox](#-dsa-sandbox) below — real code, a real Judge0 judge, no simulated pass/fail. |
| `/assistant` | **Real.** See [Learner Assistant (RAG)](#-learner-assistant-rag) below — a real, cited retrieval engine, not a general chatbot. |
| `/quiz` (Source Quiz Generator) | **Real.** Upload your own material, get back a real generated quiz — see [Quizzes](#-quizzes) above. |
| `/academy`, `/register`, `/dashboard`, `/admin` | **Real.** Backed by live API calls (`learning.*` / `game.*`). |
| `/character`, `/combat/[roomId]`, `/boss/[dungeonId]`, `/leaderboard` | **Real, but gated behind Quest Mode.** Off by default — visiting directly shows `QuestModeGate` (a "turn on Quest Mode?" prompt) until the learner opts in from the NavBar toggle. Once on, these render genuine player/game state (hint tokens, damage, hero selection, XP-ranked leaderboard) on top of the same real competency-quiz question bank. Leaderboard's heading reads "ALL-TIME RANKS" — the backend ranks by lifetime `total_xp`, no weekly window exists. |
| `/guild` | **Gated behind Quest Mode, and still a self-contained mockup underneath.** The real backend endpoints it should call (`/game/guild/raid/join`, `/raid/status`) exist and work — `joinGuildRaid()` in `frontend/lib/api/client.js` is correctly wired — but nothing in the UI calls it yet; it's disconnected working infrastructure for a legitimately future feature, not fake code. |
| `/integration-registry` | **Still a mockup**, but its copy was fixed for honesty — it used to assert specific, never-checked compliance claims ("VERIFIED COMPLIANT", a fabricated audit hash, a specific RTI Act citation); now framed explicitly as "design-intent, not measured." |

## 🌐 Internationalization

**11 languages**: English, Hindi, Bengali, Marathi, Telugu, Tamil, Gujarati, Urdu, Kannada, Odia, Malayalam — the 2011 Census's top 10 most-spoken mother tongues, plus English.

- [`frontend/lib/i18n/translations.js`](frontend/lib/i18n/translations.js) — one dictionary per language, ~280 keys each (nav, login, academy, stats, radar, admin, dashboard, leaderboard, character, DSA Sandbox, Learner Assistant, footer, and more). Adding a language needed **zero code changes** — [`LanguageContext.jsx`](frontend/lib/i18n/LanguageContext.jsx) and [`LanguageSwitcher.jsx`](frontend/components/LanguageSwitcher.jsx) were already fully generic over whatever languages this file lists.
- [`frontend/lib/i18n/LanguageContext.jsx`](frontend/lib/i18n/LanguageContext.jsx) — a `useLanguage()` hook, persisted to `localStorage`, with a `hasOwnProperty`-guarded lookup (deliberately hardened against prototype pollution) and fallback to English for any missing key or language.
- The backend also honors `?lang=` (all 11 codes) on `/learning/curricula`, `/learning/pathway/{id}`, `/learning/assessment/{id}`, `/learning/integrations/status`, and `/learning/admin/overview`, translating both the curated curriculum catalog (`curricula_<lang>.json` per language) and the deterministic gap-analysis prose generated by `learning_engine.py`.
- Scope is intentionally UI chrome + deterministic system text, **not** AI-generated content — quiz questions and Gemini-generated text come back in whatever language they were generated in.
- **Translation provenance matters here**: Hindi's content was hand-translated. Every other language (Bengali through Malayalam) was machine-translated via [`backend/i18n_pipeline/`](backend/i18n_pipeline/) — Google Translate's public endpoint, with MyMemory as a fallback when rate-limited — never by an LLM or by hand. That pipeline is documented and re-runnable, but its output is a first pass: **a fluent native-speaker review is still an open item** for those 9 languages, same standard already applied before trusting Hindi.

The same competency-radar page, switched live from the navbar with no reload (English/Hindi shown as a two-language sample of the full 11-language set):

| English | हिंदी |
|---|---|
| `Skill Vector Divergence`, `11 tracked competencies`, `not yet assessed` | `स्किल वेक्टर विचलन`, `11 ट्रैक की गई दक्षताएं`, `अभी तक मूल्यांकन नहीं` |
| Curriculum picker: `DSA Fundamentals` | पाठ्यक्रम चयनकर्ता: `DSA मूल बातें` |
| Footer: `© 2024 Ministry of Statistics and Programme Implementation (MoSPI)` | फुटर: `© 2024 सांख्यिकी और कार्यक्रम कार्यान्वयन मंत्रालय (MoSPI)` |

## 🎙️ Voice AI pipeline

A fully local, authenticated voice interface to the learning assistant — no audio ever leaves the machine, and nothing is written to disk ([`backend/ai/voice/`](backend/ai/voice/), [`routes/ai_voice.py`](backend/routes/ai_voice.py)):

```mermaid
flowchart LR
    MIC["Microphone\nPCM16 @ 16kHz"] -- "WebSocket /ai/voice/stream\n(authenticated)" --> VAD["Silero VAD\n(bundled ONNX, via faster-whisper)"]
    VAD -- "speech segment" --> STT["faster-whisper tiny.en\n(local STT)"]
    STT -- "transcript" --> RAG["LearnerAssistant\n(existing RAG: retrieval, citations,\naccess filtering, abstention)"]
    RAG -- "grounded response" --> TTS["Piper TTS\n(local, sentence-streamed)"]
    TTS -- "synthesized audio" --> SPK["Speaker"]

    style MIC fill:#fff4e5,stroke:#904d00
    style SPK fill:#fff4e5,stroke:#904d00
```

- Server-derived identity only — `tenant_id`, `user_id`, `player_id`, and `roles` sent by the client are rejected outright; the same tenant/role-scoped RAG filtering and prompt-injection detection used by the text-based assistant applies here too.
- Cooperative cancellation and barge-in: a learner can interrupt mid-response.
- **Local-only for now** — the Piper voice model isn't committed to the repo (`.gitignore`'d, configured via `PIPER_MODEL_PATH`/`PIPER_CONFIG_PATH`), so this isn't part of the hosted Render demo; it runs when you bring your own model file locally.
- **Backend-only today — no frontend entry point yet.** The WebSocket pipeline above is real and has 61 test functions covering it (`tests/test_content_ai_voice.py`), but there is no microphone button or audio UI anywhere in `frontend/`. A learner can reach the text version of the same assistant at [`/assistant`](#-learner-assistant-rag); a voice UI wired to `/ai/voice/stream` is tracked as an open item, not claimed as shipped.

## 🚀 Running it locally

**Backend** (Python 3.11 — pinned in `render.yaml` and `backend/.python-version`; newer versions fail to build `pydantic-core` from source):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate      # or: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env      # fill in DATABASE_URL at minimum; DISABLE_AUTH=true for a quick local demo
python -m alembic upgrade head
uvicorn main:app --reload --port 8000
```

**Frontend** (Node ≥ 22.13):

```bash
cd frontend
npm install
echo NEXT_PUBLIC_API_URL=http://localhost:8000 > .env.local
npm run dev
```

Then open `http://localhost:3000`.

## 📡 API reference

| Router | Prefix | Purpose |
|---|---|---|
| `game.py` | `/game` | Player creation/login, hero selection, sessions, leaderboard, hint tokens |
| `learning_profile.py` | `/learning` | Learner profile CRUD |
| `learning_competency.py` | `/learning` | Competency assessment, pathway, curricula listing |
| `learning_content.py` | `/learning` | Quiz/content generation and listing |
| `learning_integration.py` | `/learning` | External catalog (iGOT/NSSTA) integration status |
| `learning_analytics.py` | `/learning` | Admin overview & analytics |
| `competency_quiz.py` | `/learning/competency-quiz` | Source-cited competency quiz bank — by topic (baseline) or by a single `competency_id` (`/practice`) |
| `dsa_sandbox.py` | `/learning/dsa-sandbox` | Real Judge0 code execution — see [DSA Sandbox](#-dsa-sandbox) |
| `dev_auth.py` | `/auth` | Local-dev bridge: demo login → real Keycloak token (not a backdoor, not the real OIDC flow) |
| `ai_real.py` | `/ai` | Learner Assistant (`/ai/assistant/query`), retrieval (`/ai/retrieval/search`, `/ai/retrieval/index`) — see [Learner Assistant (RAG)](#-learner-assistant-rag) |
| `ai_voice.py` | `/ai/voice` | Authenticated WebSocket voice pipeline (`/ai/voice/stream`) — see [Voice AI pipeline](#-voice-ai-pipeline) |

`learning.py` aggregates the `learning_*` routers into one `APIRouter` for a single import point. Full OpenAPI contract: [`docs/contracts/openapi.json`](docs/contracts/openapi.json).

## 🧱 Tech stack

| Layer | Choice |
|---|---|
| Backend | FastAPI 0.141, Starlette 1.6, SQLAlchemy 2.0, Alembic, Uvicorn |
| Database | PostgreSQL (Neon, serverless) |
| Auth | Keycloak (OIDC), demo-bypassable per above |
| AI | Gemini (`gemini-flash-lite-latest`) |
| Voice | faster-whisper 1.2.1 (STT), piper-tts 1.8.0 (TTS), Silero VAD (bundled ONNX) — all local |
| Frontend | Next.js 15, React 19, Zustand, TanStack Query, Recharts, React Flow, Framer Motion, Tailwind CSS |
| Deployment | Render (Blueprint: backend + Keycloak), Neon (DB) |
| CI | GitHub Actions — see below |

## 🧪 Tests & CI

- **992 backend tests** (967 passed, 25 skipped locally; pytest), run against a real `postgres:16` service container in CI.
- **No frontend test suite** exists yet — `frontend/package.json` only defines `dev`/`build`/`start`/`lint`.
- [`ci.yml`](.github/workflows/ci.yml) runs on every push/PR to `main`:
  - `backend-tests` — `pip-audit` + full pytest suite against Postgres
  - `frontend-checks` — lint + production build
  - `contract-checks` — validates `docs/contracts/openapi.json`
  - `security-checks` — `gitleaks` secret scan
  - `sast` — Semgrep, with one rule exception documented inline for two reviewed call sites in `backend/db/database.py`
- [`keepalive.yml`](.github/workflows/keepalive.yml) — cron every 10 minutes, keeps the free-tier Render services warm.

Not yet covered: end-to-end/Playwright smoke tests, SBOM, DAST.

## ☁️ Deployment

[`render.yaml`](render.yaml) is a Render Blueprint defining two services — `prism-backend` (FastAPI, Python 3.11.9 pinned) and `prism-keycloak` (Docker). The frontend and the Neon database are **not** part of this blueprint: the frontend runs per-laptop via `npm run dev` pointed at the deployed backend, and Neon is provisioned separately. See [`deploy/README.md`](deploy/README.md) for the full setup walkthrough.

## ⚠️ Known limitations

- `DISABLE_AUTH=true` in the deployed demo means there is no real identity check on any request — see [Auth model](#-auth-model-read-this-before-you-judge-the-security).
- `/integration-registry` is a visual mockup with no backend behind it; `/guild` has a real backend endpoint waiting but no UI wired to it yet.
- The optional gamified practice layer (Quest Mode: `/character`, `/combat`, `/boss/[dungeonId]`, `/guild`, `/leaderboard`) is off by default and intentionally not part of the front-page pitch for now — see the [real-vs-mockup table](#-whats-real-and-whats-a-mockup) if you need the detail.
- The Learner Assistant's answer quality without a working `GEMINI_API_KEY` is extractive (it quotes the top-matching evidence directly rather than synthesizing prose) — real and honestly labeled, but a configured key gives noticeably better answers. The 174-excerpt seed corpus is UPSC-exam-style passages, so some phrasing reads more like an exam question than a textbook explanation.
- The voice pipeline is local-only and has no frontend UI yet — see [Voice AI pipeline](#-voice-ai-pipeline).
- 9 of the 11 UI languages are a first machine-translation pass awaiting native-speaker review — see [Internationalization](#-internationalization).
- One DSA competency (`binary_search`) has no verified quiz questions yet.
- The real browser OIDC/PKCE login flow (as opposed to the demo bypass and the dev-login bridge) is not yet implemented.
- No frontend automated test suite.
- Render's free tier means cold starts and tight memory headroom on Keycloak — not a production-scale deployment.

## 📁 Project structure

```
backend/
  routes/            FastAPI routers (game, learning/*, auth, ai, ai_voice, dsa_sandbox)
  services/          Domain logic — curricula, gap engine, quiz generation, catalogues
  ai/                Retrieval, ingestion, the Learner Assistant, corpus seeding, voice/ (local VAD/STT/TTS)
  i18n_pipeline/     Documented, re-runnable scripts that machine-translated 9 UI languages
  models/            SQLAlchemy models (players, learning, governance, dungeon, guild, ...)
  security/          Real OIDC identity + RBAC (untouched by the demo bypass)
  migrations/        Alembic migrations
  tests/             992 pytest tests

frontend/
  app/           Next.js App Router pages (see the real-vs-mockup table above)
  components/    Shared UI (AcademyHub, MLDashboard, NavBar, ...)
  lib/           API client, i18n (translations.js, LanguageContext.jsx, 11 languages)
  store/         Zustand stores (auth, game)

services/        Standalone optional AI microservice (separate FastAPI app)
docs/            Contracts (OpenAPI), evidence log, problem statement
docs/internal/   Lane coordination/strategy docs (team orchestration, handoffs, sync logs)
deploy/          Render/Neon deployment walkthrough
```

Root now holds only what someone evaluating the product needs first: `README.md`, `SIH26101_MASTER_CHECKLIST.md`, `EVIDENCE.md`, and the agent-instruction files (`CLAUDE.md`, `CODEX.md`, `AGENTS.md`). Internal lane-coordination docs live under `docs/internal/`.

## 🙌 Team

Built for Smart India Hackathon 2026, Problem Statement 26101, across six coordinated lanes (identity & core data, AI/content, frontend, integrations, release engineering, and orchestration). See [`docs/internal/SIH26101_TEAM_ORCHESTRATION.md`](docs/internal/SIH26101_TEAM_ORCHESTRATION.md) for the full lane breakdown and [`EVIDENCE.md`](EVIDENCE.md) for the running evidence log.
