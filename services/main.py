"""
FastAPI app entry point for the standalone AI/ML services layer.

The main backend calls into this from its own server-side flows (see
backend/services/ai_client.py); this process can also be run standalone for
local development:

    uvicorn main:app --reload --port 8001
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

import config  # noqa: F401  -- load environment configuration before routes
from routes.ai import router as ai_router
from services.nlp_judge import warm_up


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pay the SentenceTransformer model-load cost once at startup instead of
    # on the first player's answer submission.
    await warm_up()
    yield


app = FastAPI(title="PRISM AI Services", version="1.0.0", lifespan=lifespan)

# This service is only ever called server-to-server (by backend/services/ai_client.py
# over httpx), never from a browser, so there is no session/cookie to carry --
# allow_credentials=True served no purpose here and, combined with a wildcard
# origin, is a combination browsers reject outright anyway.
# TODO INTEGRATION: Lock down allowed_origins to the main backend's server
# URL when deploying. Currently open for local development.
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)


@app.get("/")
async def root() -> dict:
    return {"message": "PRISM AI layer is running"}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "services": ["question", "judge", "tuner", "graph"]}
