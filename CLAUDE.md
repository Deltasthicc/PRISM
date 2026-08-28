# CLAUDE.md

Guidance for Claude Code working in this repository. Read this before the first tool call.

---

## What this project is

A working name only — **"SIH Learning Tool"** — not a final brand. Don't invent or assume a
product name beyond that; ask before introducing one anywhere user-facing.

Built for **SIH26101** (Smart India Hackathon, MoSPI problem statement): an explainable,
cross-domain skill-intelligence platform. It builds a role-aware competency profile, runs a gap
analysis against a target proficiency level, orders a prerequisite-aware learning pathway,
recommends learning catalogs, turns uploaded material into source-grounded quizzes, and closes the
loop with adaptive practice evidence — across four domains: DSA, Official Statistics & Data
Governance, Public Policy & Programme Evaluation, and Digital & AI Literacy.

The product has two faces over one shared data model, not two separate products:

- **Professional mode** — the Academy (`/academy`), the admin overview (`/admin`), profile/gap/
  pathway/quiz flows. This is the SIH26101-facing product.
- **Quest mode** — the dungeon-crawler RPG (combat, bosses, heroes, guilds, leaderboard). This is
  an adaptive-practice engagement layer, kept deliberately, that both delivers practice questions
  and generates one source of evidence (`accuracy_history`) the gap engine reads.

Gamification is the delivery layer for practice; the skill record underneath must stay explicit
and interpretable. Don't let RPG flavor (hero powerups, boss names, XP) leak into how a competency
score or gap is computed — that logic lives in `backend/services/learning_engine.py` and must stay
deterministic and explainable.

## Provenance — read this before assuming anything is "the old project"

This repo's dungeon-RPG engine and UI kernel were forked from an earlier, differently-branded
single-domain (DSA-only) learning game. That project has been **fully de-branded**: its former
name must never appear in code, comments, docs, or UI copy anywhere in this repository. If you
find a stray mention of it, remove it and reword the surrounding text — don't just delete the
sentence and leave a gap. `docs/archive/` holds two audit documents written before the rename;
they're historical record and are deliberately **not** edited to strip that name (see
`docs/archive/README.md` for why) — don't use them as a template for current-facing copy.

The cross-domain skill-intelligence layer (`services/curricula.py`, `learning_engine.py`,
`quiz_generator.py`, `routes/learning.py`, `components/AcademyHub.jsx`, and everything that
depends on them) was designed in a separate AI-assisted session, then completed and integrated
into this actual repository, then verified here — see the root `README.md`'s "what's real right
now" section for exactly what was independently confirmed (a real `pytest` run, a live server
boot, live HTTP calls through the full loop) versus what's still aspirational.

## Repository layout

```
SIH Learning Tool/
├── README.md                 What's real vs. aspirational — read this, not memory, before claiming status
├── CLAUDE.md                 This file
├── docs/
│   ├── archive/               Pre-rename planning docs (historical, not current-facing)
│   ├── chatgpt_art_prompt*.md  Sprite art generation prompts (Quest mode assets)
│   └── gemini_music_prompt.md  Background music generation prompt (Quest mode assets)
├── backend/                  FastAPI + SQLAlchemy + SQLite
│   ├── main.py                App entry, CORS, router registration, DB init + seeding
│   ├── db/                    Engine/session setup, seeding (DSA legacy path + cross-domain)
│   ├── models/                SQLAlchemy tables (game/ + learning.py)
│   ├── schemas/                Pydantic request/response shapes (mirrors models/)
│   ├── routes/                 HTTP handlers only — game.py, ai_real.py, learning.py
│   ├── services/                Pure logic, no DB/HTTP — game rules, curricula, gap engine,
│   │                            quiz generation, content ingestion, catalog/integration boundary
│   └── tests/                   42 tests: original game engine + cross-domain/learning platform
├── frontend/                 Next.js 15 (App Router) + Zustand + TanStack Query
│   ├── app/                   One folder per route (academy/, admin/, dungeon/, combat/, ...)
│   ├── components/            Game + Academy UI, plus components/ui/ Pixel design-system primitives
│   ├── lib/api/client.js       The ONLY file that calls fetch — add new API calls here
│   └── store/                  Zustand: useAuthStore, useGameStore, ...
└── services/                 Optional standalone AI engine (real sentence-embedding grading),
                               off by default — see services/README.md
```

## Coding conventions (inherited, keep following them)

### Python

- Python 3.11+. Type hints on public functions.
- **Pydantic v2 only.** `model_validate`, `model_dump`, `field_validator` — never v1's `.dict()`
  or `@validator`.
- `routes/` = HTTP handlers only, no business logic. `services/` = pure logic, no DB, no HTTP.
  `models/` = SQLAlchemy tables. `schemas/` = Pydantic shapes, one file per feature area, named to
  mirror `models/`.
- Comments explain *why*, not what — a hidden constraint, an invariant, a workaround for a
  specific bug. Don't restate what the code already says.
- No bare `except Exception: pass`. Catch the specific type, or let it propagate.
- Lazy-import optional/heavy SDKs inside the function that needs them (see
  `backend/services/ai_client.py`, `services/services/llm_engine.py`) so the package stays
  importable without every optional dependency installed.

### Frontend

- `frontend/lib/api/client.js` is the single browser-to-backend boundary. No component, page, or
  store calls `fetch` directly — add new endpoints there, following the existing `auth` / `game` /
  `ai` / `learning` export pattern.
- Reuse `components/ui/` (PixelPanel, PixelButton, PixelInput, PixelBadge) rather than inventing
  new primitives — they're the de-facto design system for both Professional and Quest mode.

### Tests

- Pytest, fixtures not setUp/tearDown. Run with `backend/.venv/Scripts/python.exe -m pytest` (or
  activate the venv first) — 42 tests, no server or API key required; every AI-dependent path under
  test either mocks the network call or exercises its deterministic fallback directly.
- Every bug fix gets a test — see `test_learning_platform.py::test_room_unlock_falls_back_to_curricula_for_non_dsa_topics`
  for the pattern (a real bug found during integration, fixed, and regression-tested).

## Key architectural rules — don't casually break these

1. **The 65/35 evidence-weighting policy in `learning_engine.py` is a stated, transparent
   prototype policy, not a validated formula.** If you change the weights or add a new evidence
   type, say so explicitly in the code comment and in any user-facing explanation — never present
   a heuristic as if it were psychometrically validated.
2. **`learning_catalog.py` must never fabricate a live integration.** There is no public iGOT
   Karmayogi or NSSTA/TPAC partner API today. Every recommendation is either a link to this app's
   own practice quest or a `catalog-fallback`-labeled link to a public catalog page. Don't invent a
   course ID, enrolment record, or "configured" status without a real adapter behind it.
3. **`quiz_generator.py`'s source-grounding validation is load-bearing, not decoration.** Every
   accepted question must have a `source_excerpt` that is an exact substring of the uploaded
   material. Don't loosen this to "approximately matches" — that's exactly the hallucination risk
   the validator exists to catch.
4. **The cross-domain competency model lives in `services/curricula.py`, not scattered dicts.**
   The DSA domain still has its own legacy graph in `knowledge_graph.py` (see README §"Competency
   graph & data model" for why they're not yet unified) — don't add a *third* place a topic list
   lives. If you add a competency, prerequisite, or domain, it goes in `curricula.py` and
   `validate_curricula()` must still pass.
5. **`routes/game.py::_is_room_unlocked_for_player` must stay cross-domain-aware.** It checks
   `TOPIC_GRAPH` (DSA) first and falls back to `curricula.py` for everything else — don't
   "simplify" this back to DSA-only, that's the exact bug that was found and fixed here.
6. **Never commit a real API key or `.env` file.** `services/.env` and `backend/.env` are
   gitignored for a reason — a local dev copy has historically held a live Gemini key. Always
   `git status`/`git diff --cached` before committing anything touching env files.

## What's done vs. what's left

Don't answer "is X done" from memory or from `docs/archive/` — those are dated. The root
`README.md`'s "What's real right now" / "What's aim, not yet reality" sections are the current,
maintained source of truth and must be kept in sync with reality:

- If you add a feature, add it to "what's real" **only after verifying it** (run the tests, hit
  the endpoint, don't just describe what you intended).
- If you notice README claims something that no longer holds, fix the README in the same change.

Known real gaps as of the last verification pass: no live iGOT/NSSTA integration (no public
partner API exists), no real identity/RBAC (username-only, no password, no server-derived
session), no official (MoSPI/NSSTA/CBC-approved) competency ownership of the four curricula,
SQLite with no real migration tool, no content-review workflow for generated quiz questions, no
multilingual pipeline, malware scanning, background job queue, or observability.

## When Claude Code should ask vs. act

- **Act without asking:** bug fixes with an obvious cause, adding tests, extending
  `curricula.py`/`learning_catalog.py` following existing patterns, README updates that keep it in
  sync with verified reality.
- **Ask first:** naming the product (there isn't one yet — don't pick one), any change that would
  make `learning_catalog.py` claim a live integration without a real adapter behind it, removing or
  significantly changing Quest mode (the RPG layer was kept deliberately, not by default), and any
  large-scope refactor (>100 lines across >3 files).

## Verification before calling something done

- `cd backend && .venv/Scripts/python.exe -m pytest` — expect 42 passed. If that number changes,
  explain why in the commit message.
- `cd frontend && npm run lint && npm run build` — both must succeed; the build must list every
  route including `/academy` and `/admin`.
- `npm audit --omit=dev` — expect 0 vulnerabilities.
- For anything touching `/learning/*`, prefer an actual live HTTP round-trip (boot `uvicorn`, hit
  the endpoint) over trusting a unit test alone — the multipart quiz-upload path in particular has
  broken silently before on tooling quirks unrelated to the code itself.

## Meta

- Maintained by the repository owner and Claude Code together.
- If you notice this file has gone stale (a claim here no longer matches the code), propose a
  correction rather than silently acting on outdated information.
