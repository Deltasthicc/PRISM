# deploy

Owner: Lane 6 (Quality, Security, Release & Evidence) -- `SIH26101_TEAM_ORCHESTRATION.md`
section 2.

Status: **a real, live, shared free-tier team environment** (database + backend + local-standards
OIDC provider), so the six lanes stop looking at six different local databases. **Not** a
government-approved production deployment -- see `SIH26101_TEAM_ORCHESTRATION.md` section 11,
"Production authorization remains external", and `SIH26101_MASTER_CHECKLIST.md` section 5.1. Free
hosting tiers, no SLA, no on-call, no DR -- good enough for a hackathon team to see each other's
data, not for real learner data or a real government pilot.

## What this is for

Before this, every teammate's `DATABASE_URL` defaulted to a SQLite file on their own laptop (or, at
best, their own local `docker compose -f backend/docker-compose.dev.yml up` -- still local to that
one machine). Nobody could see anyone else's profiles, rankings, or leaderboard, because there was
never a shared database to look at. This gives the team exactly three shared pieces, hosted once
instead of six times:

1. **A shared PostgreSQL database** (Neon) -- one real place everyone's data lives.
2. **A shared FastAPI backend** (Render) -- one real API everyone's frontend talks to, instead of
   `localhost:8000` meaning something different on every laptop.
3. **A shared local-standards OIDC provider** (the same Keycloak realm from
   `backend/keycloak/`, now always-on instead of six people each running their own copy) -- because
   the moment routes are genuinely protected (as of Lane 5's `game.py`/`learning_*` auth work),
   a shared backend needs one real, shared way to get a token, not six local ones that only work on
   their own machine.

Everyone's frontend still runs locally (`npm run dev` on your own laptop) -- it just points at the
shared backend URL instead of `localhost:8000`.

## One-time setup (whoever stands this up)

### 1. Database -- Neon

1. Create a free account at neon.tech, create one project (any region).
2. Create a database named `prism` inside it (Neon's default `neondb` also works fine -- just be
   consistent with whatever you put in step 2 below).
3. Copy the connection string it gives you -- it already includes `?sslmode=require`, which this
   project's `psycopg[binary]` driver understands natively (`backend/db/database.py`'s
   `normalize_database_url()` handles both `postgres://` and `postgresql://` schemes it might hand
   you). You'll paste this into Render as `DATABASE_URL` in step 3 below -- Render can't create a
   Neon project for you, this step has to happen in Neon's own dashboard.

### 2. Backend + OIDC provider -- Render

`render.yaml` at the repo root defines both services as a single Render "Blueprint":

1. In Render, choose **New > Blueprint**, connect this GitHub repo, and point it at `main`
   (or whichever branch you're deploying from).
2. Render reads `render.yaml` and creates two services: `prism-backend` and `prism-keycloak`. It
   will prompt you for every env var marked `sync: false` in that file during creation -- fill in:
   - `prism-keycloak`'s `KC_BOOTSTRAP_ADMIN_USERNAME` / `KC_BOOTSTRAP_ADMIN_PASSWORD` -- pick
     anything, this is just the Keycloak admin console login, nobody else needs it.
   - `prism-keycloak`'s `KC_HOSTNAME` -- **you don't know this until Render assigns the service its
     real `.onrender.com` domain, so deploy this service once first, note the hostname Render gives
     it, then come back and set this env var to exactly that hostname** (no `https://`, no
     trailing slash -- a plain hostname, verified locally against a real running container; see
     the note in `backend/keycloak/Dockerfile`). Redeploy after setting it.
   - `prism-backend`'s `DATABASE_URL` -- the Neon connection string from step 1.
   - `prism-backend`'s `OIDC_ISSUER` -- `https://<prism-keycloak's real hostname>/realms/prism`.
   - `prism-backend`'s `KEYCLOAK_DEV_TOKEN_URL` --
     `https://<prism-keycloak's real hostname>/realms/prism/protocol/openid-connect/token`.
   - `prism-backend`'s `KEYCLOAK_DEV_CLIENT_SECRET` / `KEYCLOAK_DEV_PASSWORD` -- copy these straight
     out of `backend/keycloak/README.md` (they're the same fixed dev-only values that ship in
     `prism-realm-export.json`, not a new secret to invent).
   - `prism-backend`'s `GEMINI_API_KEY` -- same key format as local dev (`.env.example`).
3. Render's build for `prism-backend` runs `pip install -r requirements.txt`, then its start
   command runs `python -m alembic upgrade head` before starting `uvicorn` -- the shared database
   gets migrated to head automatically on every deploy, the same guarantee
   `db/database.py::require_database_at_migration_head` already enforces for local PostgreSQL.

**A note on `prism-keycloak`'s memory:** Keycloak is a real JVM app, and Render's free tier caps
the container at 512Mi. `backend/keycloak/Dockerfile` tunes the JVM to fit -- verified directly
against the exact same 512Mi limit locally -- but it still sits around 90% of that limit at rest.
That's normal, not a sign something's wrong. If it ever shows up flaky under real concurrent
teammate logins (visible as the service restarting on its own in Render's dashboard), the fix is
upgrading `prism-keycloak`'s plan to Render's smallest paid tier for more RAM, not more JVM flags --
see the Dockerfile's own comment for the full story of what was tried.

### 3. Point your own frontend at the shared backend

In your own `frontend/.env.local` (per-laptop, not committed):

```
NEXT_PUBLIC_API_URL=https://<prism-backend's real Render hostname>
```

That's the only frontend change needed -- `frontend/lib/config.js`'s `API_BASE_URL` already reads
this env var. If `prism-backend`'s `FRONTEND_ORIGINS` env var doesn't already include your local
`http://localhost:3000`, add it there (comma-separated) or your browser's CORS preflight will fail.

## What this does NOT give you yet

- **Still not the real browser OIDC/PKCE login** -- `ENABLE_DEV_LOGIN` bridges the existing
  username-only demo login to a real shared Keycloak token automatically (see
  `backend/routes/dev_auth.py`'s docstring); it is not a substitute for the Authorization Code +
  PKCE flow `SIH26101_MASTER_CHECKLIST.md` 5.1 and `README.md` still track as open Lane 1/5 work.
- **No production TLS/secrets/KMS custody, no scheduled encrypted offsite backup, no DR runbook,
  no uptime guarantee** -- both services are on free tiers, which sleep/cold-start and carry no
  SLA. Fine for a team demo; not a claim of anything more.
- **No real learner/personal data belongs here.** Same rule as the local Compose stack this
  replaces (`docs/contracts/production-database-hardening.md` section 0): synthetic/demo data only.
