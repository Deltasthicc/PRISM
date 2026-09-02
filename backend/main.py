"""
Backend entry point — FastAPI app for PRISM (Personalized Readiness Intelligence & Skill Mapping).
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from db.database import (
    Base,
    engine,
    ensure_columns,
    is_sqlite_database,
    require_database_at_migration_head,
    should_seed_demo_data,
)

# Import all models so tables are registered with Base.metadata
from models.player import Player
from models.accuracy_history import AccuracyHistory
from models.question import Question
from models.submission import AnswerSubmission
from models.guild import Guild
from models.dungeon import Dungeon, Room
from models.session import GameSession
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz
from models.governance import RoleTarget, EvidenceRecord, SourceVersion, AuditEvent
from models.identity import IdentityBinding


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Prepare the configured schema and seed synthetic demo data."""
    if is_sqlite_database():
        Base.metadata.create_all(bind=engine)
        print("SQLite database tables created or verified.")
    else:
        # PostgreSQL is migration-managed: silently creating model tables here
        # would hide a missed deploy step and leave alembic_version lying about
        # the real schema. Fail with an actionable message instead.
        require_database_at_migration_head()
        print("Database migration revision verified.")

    # SQLite compatibility columns added after an existing demo DB was first
    # created -- create_all() never alters existing tables. This helper is a
    # deliberate no-op on migration-managed PostgreSQL.
    ensure_columns("players", [
        ("hero_id", "TEXT"),
        ("pending_xp_multiplier", "REAL DEFAULT 1.0"),
        ("pending_verdict_boost", "BOOLEAN DEFAULT 0"),
        ("pending_force_correct", "BOOLEAN DEFAULT 0"),
        ("powerup_window_start", "TEXT"),
        ("powerup_uses_this_window", "INTEGER DEFAULT 0"),
    ])
    ensure_columns("accuracy_history", [
        ("mastered", "BOOLEAN DEFAULT 0"),
        ("damage_dealt", "INTEGER DEFAULT 0"),
    ])
    ensure_columns("submissions", [
        ("damage_dealt", "INTEGER DEFAULT 0"),
    ])
    ensure_columns("questions", [
        ("max_damage", "INTEGER DEFAULT 80"),
    ])

    # Auto-seed the demo DSA dungeon, then materialize every other curriculum
    # in services/curricula.py as its own dungeon (see db/seed.py's
    # seed_curricula_dungeons for why DSA keeps its own legacy seeding path).
    # Gated by SEED_DEMO_DATA (see db/database.py::should_seed_demo_data) --
    # on by default for the SQLite demo, off by default for PostgreSQL, so a
    # migration-managed database doesn't silently receive a synthetic player
    # and curriculum content unless that's explicitly asked for.
    if should_seed_demo_data():
        from db.seed import seed_database, seed_curricula_dungeons
        seed_database()
        seed_curricula_dungeons()
        print("Seeded synthetic demo data (SEED_DEMO_DATA resolved to true).")
    else:
        print(
            "Skipped synthetic demo data seeding (SEED_DEMO_DATA resolved to false) -- "
            "see docs/contracts/data-authorization.md."
        )

    yield


app = FastAPI(
    title="PRISM API",
    description=(
        "Skill-intelligence backend for SIH26101: role-aware competency profiles, "
        "explainable gap analysis, adaptive practice quests, and source-grounded quiz "
        "generation across DSA, Official Statistics, Public Policy, and Digital Literacy."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        # :3001 included too -- `next dev` silently falls back to it whenever
        # another process (often a stale dev server from a previous session)
        # is still squatting :3000, and a CORS-rejected preflight ("Could not
        # reach the backend") is a much more confusing failure than just
        # trusting both ports up front.
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
    ).split(",")
    if origin.strip()
]

# Credentialed browser requests require explicit origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging middleware
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - start_time) * 1000
        print(f"[{request.method}] {request.url.path} -> {response.status_code} ({duration_ms:.1f}ms)")
        return response


app.add_middleware(RequestLoggingMiddleware)

# Import and include routers
from routes.game import router as game_router
from routes.ai_real import router as ai_router
from routes.learning import router as learning_router

app.include_router(game_router)
app.include_router(ai_router)
app.include_router(learning_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {
        "app": "PRISM",
        "version": "0.1.0",
        "docs": "/docs",
        "status": "prototype -- see README.md and docs/ for what's real vs. aspirational",
    }
