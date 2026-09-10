"""Coverage for ai/seed_corpus.py -- the Learner Assistant's retrieval store
must have real evidence to search from the moment the app starts, on any
fresh checkout, with no network access or gitignored document cache
required. See main.py's lifespan for where this actually gets called."""
import json

from fastapi.testclient import TestClient

from ai.provenance import AccessContext
from ai.retrieval import InMemoryChunkStore
from ai.seed_corpus import build_seed_chunks, seed_default_chunk_store
from main import app
from routes.authorization import require_principal
from security.rbac import DEPLOYMENT_TENANT_SCOPE, BoundPrincipal

client = TestClient(app)


class _StubSubject:
    subject_id = "test-learner"
    issuer = "test"
    roles = frozenset({"learner"})


def _learner_principal() -> BoundPrincipal:
    return BoundPrincipal(
        subject=_StubSubject(), binding_id="test-learner", player_id=None, roles=frozenset({"learner"})
    )


def test_build_seed_chunks_covers_every_source_excerpt_in_the_question_bank():
    with open("data/hand_authored_questions.json", encoding="utf-8") as handle:
        data = json.load(handle)
    expected = {
        item["item_id"] for item in data["questions"] if (item.get("source_excerpt") or "").strip()
    }

    chunks = build_seed_chunks()

    assert {c.chunk_id for c in chunks} == expected
    for chunk in chunks:
        assert chunk.text.strip()
        assert chunk.source_id
        assert chunk.locators and chunk.locators[0].label
        assert chunk.allowed_roles == ["learner", "trainer", "admin"]
        # Must match every real BoundPrincipal's tenant_scope
        # (DEPLOYMENT_TENANT_SCOPE), not the generic "default" placeholder
        # Chunk/AccessContext happen to default to -- see seed_corpus.py's
        # own comment on this exact point.
        assert chunk.tenant_id == DEPLOYMENT_TENANT_SCOPE


def test_seed_default_chunk_store_is_idempotent():
    store = InMemoryChunkStore()
    first = seed_default_chunk_store(store)
    second = seed_default_chunk_store(store)  # already populated -- must be a no-op
    assert first == store.chunk_count
    assert first > 0
    assert second == 0


def test_seeded_chunks_are_actually_retrievable_by_a_real_deployment_principal():
    store = InMemoryChunkStore()
    seed_default_chunk_store(store)
    ctx = AccessContext(tenant_id=DEPLOYMENT_TENANT_SCOPE, roles=("learner",))
    results, is_insufficient = store.search(query="hazard rate exponential distribution", access_context=ctx)
    assert not is_insufficient
    assert results


def test_seeded_chunks_are_not_visible_under_the_wrong_tenant():
    """Guards the exact bug this module used to have: chunks seeded under
    the generic "default" placeholder tenant were invisible to every real
    principal, silently making the assistant abstain on every query."""
    store = InMemoryChunkStore()
    seed_default_chunk_store(store)
    ctx = AccessContext(tenant_id="default", roles=("learner",))
    results, is_insufficient = store.search(query="hazard rate exponential distribution", access_context=ctx)
    assert is_insufficient
    assert not results


def test_assistant_query_route_finds_the_real_seeded_default_store():
    """End-to-end through the real /ai/assistant/query route and the real
    `default_chunk_store` singleton it reads -- not just the module-level
    seed_corpus functions in isolation -- so a route-level regression (e.g.
    the tenant-scope mismatch this module used to have) would show up here
    even if the unit-level tests above didn't happen to catch it.

    Deliberately does NOT go through `with TestClient(app) as ...` (which
    would run main.py's full lifespan, including its Alembic schema-version
    check against whatever database CI's plain `client = TestClient(app)`
    fixture already connects to unmigrated) -- main.py's lifespan wiring
    itself was already verified by hand against a real running dev server
    (see this PR's description), so this test only needs to seed the same
    real singleton the route reads and confirm the route's own logic (auth,
    access filtering, response shape) works against it."""
    from ai.retrieval import default_chunk_store
    from ai.seed_corpus import seed_default_chunk_store

    seed_default_chunk_store(default_chunk_store)
    assert default_chunk_store.chunk_count > 0

    app.dependency_overrides[require_principal] = _learner_principal
    try:
        response = client.post(
            "/ai/assistant/query",
            json={"query": "What is the hazard rate of an exponentially distributed lifetime?"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "supported"
        assert body["citations"]
    finally:
        app.dependency_overrides.pop(require_principal, None)
