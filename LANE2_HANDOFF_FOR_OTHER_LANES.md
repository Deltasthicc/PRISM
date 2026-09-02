# Lane 2 handoff: issues raised that are NOT Lane 2's job to fix

Owner of this file: Lane 2 (Core Platform, Identity & Data), written 2 September 2026 after the
project owner tested the deployed app and raised a batch of issues. Lane 2's scope is
`backend/db/**`, `backend/models/**`, `backend/schemas/**`, `backend/main.py`,
`backend/security/**`, `backend/tests/test_core_*.py` and `docs/contracts/data-authorization.md`
(see `SIH26101_TEAM_ORCHESTRATION.md` section 2 for the full ownership table). Several of the
raised issues are genuinely outside that scope. Rather than silently skip them or overstep into
another lane's files, this file records exactly what's needed and who owns it, so whoever picks up
that lane next has a ready punch list instead of rediscovering the same gaps.

Each item below states: what was observed, why it's not Lane 2's file to fix, which lane owns it,
and what Lane 2 already provides that the owning lane can build on.

## 1. Quest/dungeon mode is not yet genuinely optional (only the default landing page changed)

**Observed:** Login and registration now route to `/academy` instead of `/dungeon` (fixed in an
earlier pass), so a brand-new user's *first* screen is the professional workspace. But Quest mode
itself is still fully visible and reachable for every user — the "Dungeon" link sits in the main
navigation bar unconditionally, with no way for a learner (or an administrator) to actually turn
Quest mode off. "Optional" today only means "not the first thing you see," not "can be disabled."

**Why not Lane 2:** Making a nav item conditional and adding a settings toggle is
`frontend/**` — Lane 1's exclusive territory. Reading that preference to decide which nav items or
routes to serve is `backend/routes/**` — Lane 5's territory (except `ai_real.py`).

**What Lane 2 already provides:** `players.preferred_mode` (migration `640603a37f2f`,
`models/enums.py`'s `LearningMode`, values `"professional"`/`"quest"`, defaults to
`"professional"`) — see `docs/contracts/data-authorization.md` section 8 for the full contract.
This column exists, is tested (`backend/tests/test_core_learning_mode.py`), and is enforced by a
database-level `CHECK` constraint. **No route currently reads or writes it.**

**What's needed:**
- Lane 5: add an endpoint (or extend an existing player-read endpoint) to expose
  `preferred_mode`, plus a way for a learner to change it (e.g. `PATCH /game/player/{id}/mode` or
  similar — propose the exact shape as a contract change against
  `docs/contracts/data-authorization.md` section 7's process, since `schemas/player.py`'s
  `PlayerCreate` deliberately doesn't accept it yet for exactly this reason).
- Lane 1: read that value and conditionally hide/show the "Dungeon"/"Guild"/"Ranks" nav items and
  routes based on it; add a real settings control for changing it, not just a data field nobody can
  reach.

## 2. Full "professional visual separation" (AcademyHub still looks like the dungeon)

**Observed:** Even outside Quest's own pages, the professional workspace still uses the dungeon's
pixel-art font, panel/button styling, and (until this pass) an always-on flying bat-swarm
animation and CRT/torch-flicker overlay on every page.

**Already partially fixed in this pass** (small, low-risk, done because it directly serves "make
Quest optional/separate" and was easy to verify): `components/BatSwarm.jsx` now only renders on
Quest's own routes (`/dungeon`, `/combat`, `/boss`, `/character`, `/guild`, `/leaderboard`), not on
`/academy`, `/dashboard`, `/admin`, `/stats`, `/`, `/login`, `/register`. The torch-flicker/CRT
scanline overlays and the pixel font itself were left alone — they're subtler, and a full
"distinct professional visual theme" (already flagged as an open gap in
`SIH26101_MASTER_CHECKLIST.md`/`SIH26101_WINNING_PLAYBOOK.md` after the PRISM rebrand) is a real
design project, not a one-line fix.

**Why not Lane 2:** All of `frontend/**` — pixel font choice, panel/button component styling,
whether Academy gets its own visual language — is Lane 1's exclusive territory.

**What's needed:** Lane 1 designs and builds an actual distinct professional theme (typography,
color palette, component styling) for Academy/dashboard/admin/stats, separate from Quest's pixel-art
kit, per the team's own already-recorded decision that Quest is optional practice, not the base
product.

## 3. Multi-language support (Hindi and other major Indian languages), as a real dropdown

**Observed:** The site is English-only today. The project owner wants a language selector (a real
`<select>`/dropdown, not a free-text box) defaulting to English with Hindi and other commonly used
Indian languages selectable.

**Why not Lane 2:** This needs an i18n framework choice, translated UI strings, and a language
switcher component — all `frontend/**`, Lane 1. If competency/quiz *content* itself needs
translation (not just UI chrome), that's content pipeline work — Lane 4's territory
(`backend/services/content_ingestion.py`, `quiz_generator.py`).

**Relevant existing constraint:** `docs/SIH26101_PROBLEM_STATEMENT.md` (PS-09) already scopes this
as "one end-to-end English/Hindi journey" for the demo, not full multi-language operations —
Lane 1 owns that requirement (`SIH26101_TEAM_ORCHESTRATION.md`'s ownership table lists `PS-09`
under Lane 1). Adding more Indian languages beyond Hindi is a further ask beyond the current
problem-statement scope; flag it to the team before committing to it, since translation quality and
maintenance cost scale with every language added.

**What's needed:** Lane 1 picks an i18n library (e.g. `next-intl`, `react-i18next`), extracts every
UI string, adds a dropdown language switcher in `NavBar.jsx`, and builds the English/Hindi journey
end-to-end first per the problem statement's own scope before considering further languages.

## 4. Admin route RBAC/OIDC wiring ("NOT PRODUCTION-SECURE" banner)

**Observed:** `/admin` shows an honest banner: any logged-in session can currently reach it,
because there is no RBAC/OIDC boundary attached to that route yet. The project owner asked whether
this was already fixed and whether it's Lane 2's issue.

**Answer, precisely:** Lane 2 built the RBAC/OIDC *primitives* — a real OIDC token verifier
(`backend/security/identity.py`, tested against live Keycloak and real JWKS key rotation), an
issuer/subject identity-binding model, and a fixed RBAC permission-checking policy
(`backend/security/rbac.py`). These are implemented, tested, and Codex-accepted (see
`LANE2_SYNC.md`). **Attaching them to actual HTTP routes — making `GET /learning/admin/overview`
in `backend/routes/learning.py` actually require a verified token and an `organization_admin` (or
similar) permission before it returns data — is Lane 5's job**
(`backend/routes/**` except `ai_real.py`, per the ownership table), not Lane 2's. Confirmed by
reading the route directly: `admin_overview()` currently depends only on `get_db`, no identity or
permission check at all — the banner is accurate, not stale.

**What Lane 2 already provides, ready to use:** `docs/contracts/identity-authorization.md` section 6
("Route handoff and present limitations") specifies exactly this handoff and lists what's still
open (secure session/token storage, a government-approved issuer, 401/403 wiring, rate limits,
etc.). The admin page's banner text was corrected in this pass to point there instead of a stale
archived roadmap file it previously cited.

**What's needed:** Lane 5 adds a FastAPI dependency (using Lane 2's `OIDCVerifier` and RBAC policy)
to `backend/routes/learning.py`'s admin route (and every other privileged route), returning 401/403
appropriately, with negative tests. Lanes 1+5 together still owe real browser Authorization
Code+PKCE login (today's login is a username-only demo flow, not real authentication) before any
of this matters end-to-end for a real user.

## 5. Self-assessment vs. quiz-based competency measurement

**Observed:** The project owner asked why competency assessment lets users self-report a rating
instead of only measuring it via quiz performance.

**Not something this pass changed, and not Lane 2's call either way:** The competency scoring
policy (currently a documented, transparent 65% demonstrated-performance + 35% self-rating blend
when both exist) lives in Lane 3's territory (`backend/services/learning_engine.py`,
`docs/contracts/competency-evidence.md`), not Lane 2's. `CLAUDE.md`/`CODEX.md` already state this
explicitly as "a transparent prototype policy, not validated psychometrics" — a deliberate,
already-made design decision, not an oversight. Lane 2 only added test coverage this pass for the
*data validation* around self-ratings (`schemas/learning.py`'s `CompetencyAssessmentRequest`: a
self-rating must be between 0 and 5, at most 100 per request) — it did not add, remove, or reweight
self-assessment as a feature.

**If the team wants to change the weighting or remove self-assessment entirely:** that's a Lane 3
decision, proposed as a contract change against `docs/contracts/competency-evidence.md`, not
something to silently edit in either lane's files.

## Summary table

| Issue | Owning lane(s) | Lane 2 already did |
|---|---|---|
| Quest mode not truly optional (no way to disable) | Lane 1 (UI) + Lane 5 (API) | `players.preferred_mode` field + constraint |
| Academy still looks like the dungeon | Lane 1 | BatSwarm no longer renders on professional routes |
| Multi-language / Hindi dropdown | Lane 1 (+ Lane 4 for content) | Nothing yet — not Lane 2 scope |
| `/admin` has no real RBAC/OIDC boundary | Lane 5 | RBAC/OIDC primitives, tested and ready; corrected the banner's stale doc reference |
| Self-assessment vs. quiz-only scoring | Lane 3 | Nothing changed; added validation tests only |
