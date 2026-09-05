"""Lane 4 Tests — Access-Filtered Retrieval, Cross-Tenant Isolation & Citations."""
import pytest

from ai.ingestion import ingest_document
from ai.provenance import AccessContext
from ai.retrieval import InMemoryChunkStore, create_citations_from_retrieved_chunks


@pytest.fixture
def populated_store():
    store = InMemoryChunkStore()

    # Ingest document for Tenant A (Official Statistics)
    doc_a = (
        "# Agricultural Statistics and Crop Estimation\n"
        "General Crop Estimation Surveys (GCES) employ stratified multi-stage random sampling.\n"
        "The primary sampling units are revenue villages, and the ultimate units are crop-cutting experimental plots.\n"
        "Yield estimates are calculated by applying the average yield rate to the total cropped area reported in land records.\n"
    )
    _, chunks_a, _ = ingest_document(
        filename="agri_stats.md",
        content=doc_a.encode("utf-8"),
        source_id="src-tenant-a",
        tenant_id="tenant-alpha",
        allowed_roles=["learner", "trainer"],
    )

    # Ingest document for Tenant B (Finance & Budget Division)
    doc_b = (
        "# Union Budget Formulation and Fiscal Deficit Rules\n"
        "The Fiscal Responsibility and Budget Management (FRBM) Act sets statutory limits on the fiscal deficit.\n"
        "Capital expenditure allocations are prioritized for infrastructure and high-multiplier asset creation.\n"
        "Revenue deficit targets ensure borrowings are not used to finance recurring operational expenditures.\n"
    )
    _, chunks_b, _ = ingest_document(
        filename="budget_rules.md",
        content=doc_b.encode("utf-8"),
        source_id="src-tenant-b",
        tenant_id="tenant-beta",
        allowed_roles=["admin"],
    )

    store.add_chunks(chunks_a + chunks_b)
    return store


def test_cross_tenant_isolation_prevents_data_leakage(populated_store):
    """Assert Tenant Alpha cannot search or retrieve Tenant Beta chunks under any circumstance."""
    alpha_ctx = AccessContext(tenant_id="tenant-alpha", roles=("learner",))

    # Query matching Tenant Beta content exactly
    results, is_weak = populated_store.search(
        query="Fiscal Responsibility and Budget Management FRBM deficit rules",
        access_context=alpha_ctx,
        top_k=5,
    )

    # Tenant Alpha should get zero results or abstain
    assert all(rc.chunk.tenant_id == "tenant-alpha" for rc in results)
    assert not any("FRBM" in rc.chunk.text for rc in results)


def test_role_based_filtering_blocks_unauthorized_roles(populated_store):
    """Assert a learner cannot retrieve chunks restricted to admin-only."""
    learner_beta_ctx = AccessContext(tenant_id="tenant-beta", roles=("learner",))

    results, is_weak = populated_store.search(
        query="Fiscal deficit targets and capital expenditure",
        access_context=learner_beta_ctx,
        top_k=3,
    )

    assert len(results) == 0
    assert is_weak is True


def test_authorized_retrieval_and_relevance_ranking(populated_store):
    """Assert authorized queries retrieve correct chunks with ranked scores."""
    alpha_ctx = AccessContext(tenant_id="tenant-alpha", roles=("learner",))

    results, is_weak = populated_store.search(
        query="What are the primary sampling units in General Crop Estimation Surveys?",
        access_context=alpha_ctx,
        top_k=3,
        threshold=0.15,
    )

    assert is_weak is False
    assert len(results) >= 1
    top_chunk = results[0].chunk
    assert "revenue villages" in top_chunk.text
    assert top_chunk.source_id == "src-tenant-a"
    assert results[0].relevance_score > 0.30


def test_weak_evidence_triggers_abstention_flag(populated_store):
    """Assert out-of-scope queries produce weak evidence flag without hallucination."""
    alpha_ctx = AccessContext(tenant_id="tenant-alpha", roles=("learner",))

    results, is_weak = populated_store.search(
        query="Quantum entanglement protocols in superconductive circuits",
        access_context=alpha_ctx,
        top_k=3,
        threshold=0.20,
    )

    assert is_weak is True


def test_verifiable_citation_resolution(populated_store):
    """Assert citation objects resolve to source version, filename, and locators."""
    alpha_ctx = AccessContext(tenant_id="tenant-alpha", roles=("learner",))

    results, _ = populated_store.search(
        query="crop-cutting experimental plots yield estimates",
        access_context=alpha_ctx,
        top_k=1,
    )

    citations = create_citations_from_retrieved_chunks(results)
    assert len(citations) == 1
    cit = citations[0]
    assert cit.source_id == "src-tenant-a"
    assert cit.source_version == 1
    assert "Section" in cit.locator_label
    assert len(cit.quote) > 10
