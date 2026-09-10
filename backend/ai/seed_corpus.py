"""Seeds ai/retrieval.py's in-memory `default_chunk_store` so the Learner
Assistant (routes/ai_real.py's /ai/assistant/query, ai/assistant.py) has real
evidence to retrieve from the moment the backend starts, instead of being an
empty, always-abstaining store until someone manually POSTs to
/ai/retrieval/index.

Seeds from data/hand_authored_questions.json's `source_excerpt` field --
already-committed, human-reviewed, real quoted passages from real government
documents (each with a real doc_id and locator) -- rather than the raw PDF
corpus in data/document_corpus.json. That corpus is fetched over the network
into a gitignored backend/data/.doc_cache/ directory; a fresh clone (a
judge's machine, CI, a teammate who never ran the content-authoring scripts)
starts with that cache empty, which would leave the assistant silently inert.
The hand-authored excerpts are already real, already verified, and already
version-controlled, so indexing them needs no network access and reproduces
identically on any checkout.

One chunk per question item -- source_excerpt is already a short, self-
contained quoted passage, so no further chunk-splitting is needed (unlike a
raw multi-page PDF, which ai/ingestion.py's `_split_into_chunks` exists for).
"""
from __future__ import annotations

import json
import os

from ai.provenance import Chunk, SourceLocator
from ai.retrieval import InMemoryChunkStore, default_chunk_store
from security.rbac import DEPLOYMENT_TENANT_SCOPE

_QUESTIONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "data", "hand_authored_questions.json"
)


def build_seed_chunks() -> list[Chunk]:
    with open(_QUESTIONS_PATH, encoding="utf-8") as handle:
        data = json.load(handle)

    chunks: list[Chunk] = []
    for item in data.get("questions", []):
        excerpt = (item.get("source_excerpt") or "").strip()
        if not excerpt:
            continue
        chunks.append(
            Chunk(
                chunk_id=item["item_id"],
                source_id=item["doc_id"],
                source_version=1,
                text=excerpt,
                locators=[
                    SourceLocator(
                        locator_type="section",
                        index=0,
                        label=item.get("locator", item["doc_id"]),
                    )
                ],
                # Chunk.tenant_id defaults to the generic placeholder
                # "default" in ai/provenance.py, but every real BoundPrincipal
                # this app issues (routes/authorization.py's demo principal
                # included) carries tenant_scope=DEPLOYMENT_TENANT_SCOPE
                # ("deployment-database", security/rbac.py -- this is a
                # single-tenant deployment, not a literal "default" tenant).
                # AccessContext.can_access() is an exact tenant_id match, so
                # seeding with the wrong constant here would make every real
                # query 403 into "insufficient evidence" despite the store
                # being fully populated -- caught by
                # tests/test_ai_seed_corpus.py's end-to-end app test, not by
                # the unit-level tests that build their own AccessContext.
                tenant_id=DEPLOYMENT_TENANT_SCOPE,
                allowed_roles=["learner", "trainer", "admin"],
                token_count=len(excerpt.split()),
                metadata={
                    "filename": item["doc_id"],
                    "competency_id": item.get("competency_id"),
                    "item_status": "DRAFT",
                },
            )
        )
    return chunks


def seed_default_chunk_store(chunk_store: InMemoryChunkStore | None = None) -> int:
    """Idempotent: does nothing if the store already has chunks (e.g. a
    second call under --reload, or a caller that indexed something first)."""
    store = chunk_store or default_chunk_store
    if store.chunk_count:
        return 0
    chunks = build_seed_chunks()
    return store.add_chunks(chunks)
