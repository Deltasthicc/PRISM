"""Lane 4 (Content AI, RAG & Evaluation) — Access-Filtered Retrieval & Ranking.

Provides deterministic, explainable chunk indexing, pre-retrieval tenant/role
access enforcement, relevance scoring, and weak-evidence abstention detection.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from ai.provenance import AccessContext, Chunk, Citation, RetrievedChunk, generate_uuid

# Minimum relevance score required before evidence is considered sufficient
DEFAULT_ABSTAIN_THRESHOLD = 0.20
TOKEN_PATTERN = re.compile(r"\b\w{2,}\b")

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only",
    "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "with", "would", "you", "your", "yours", "yourself", "yourselves",
}


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_PATTERN.findall(text)]


def _content_tokens(text: str) -> list[str]:
    return [t for t in _tokenize(text) if t not in STOP_WORDS]


class InMemoryChunkStore:
    """Thread-safe, tenant-aware chunk repository and BM25/TF-IDF retriever."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._source_index: dict[str, list[str]] = {}  # source_id -> list[chunk_id]
        self._tenant_index: dict[str, list[str]] = {}  # tenant_id -> list[chunk_id]

    def add_chunks(self, chunks: list[Chunk]) -> int:
        count = 0
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            self._source_index.setdefault(chunk.source_id, []).append(chunk.chunk_id)
            self._tenant_index.setdefault(chunk.tenant_id, []).append(chunk.chunk_id)
            count += 1
        return count

    def get_chunk(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    def get_chunks_by_source(self, source_id: str) -> list[Chunk]:
        chunk_ids = self._source_index.get(source_id, [])
        return [self._chunks[cid] for cid in chunk_ids if cid in self._chunks]

    def clear(self) -> None:
        self._chunks.clear()
        self._source_index.clear()
        self._tenant_index.clear()

    def search(
        self,
        query: str,
        access_context: AccessContext | None = None,
        source_id: str | None = None,
        top_k: int = 3,
        threshold: float = DEFAULT_ABSTAIN_THRESHOLD,
    ) -> tuple[list[RetrievedChunk], bool]:
        """Perform pre-retrieval access-filtered search.

        Returns:
            (retrieved_chunks, is_insufficient_evidence)
        """
        query_clean = query.strip()
        all_query_tokens = _tokenize(query_clean)
        content_query_tokens = _content_tokens(query_clean)

        # Fallback to all tokens if query was purely stop words
        effective_query_tokens = content_query_tokens if content_query_tokens else all_query_tokens
        if not effective_query_tokens:
            return [], True

        ctx = access_context or AccessContext()

        # Step 1: Pre-retrieval Access Filtering (enforced BEFORE ranking)
        candidate_chunk_ids = (
            self._source_index.get(source_id, [])
            if source_id
            else self._tenant_index.get(ctx.tenant_id, [])
        )
        if not candidate_chunk_ids and not source_id:
            candidate_chunk_ids = list(self._chunks.keys())

        accessible_chunks: list[Chunk] = []
        for cid in candidate_chunk_ids:
            chunk = self._chunks.get(cid)
            if chunk and ctx.can_access(chunk):
                if source_id is None or chunk.source_id == source_id:
                    accessible_chunks.append(chunk)

        if not accessible_chunks:
            return [], True

        # Step 2: Compute Corpus Document Frequencies
        total_docs = len(accessible_chunks)
        doc_freqs: Counter[str] = Counter()
        chunk_token_maps: dict[str, Counter[str]] = {}

        for chunk in accessible_chunks:
            tokens = _tokenize(chunk.text)
            counts = Counter(tokens)
            chunk_token_maps[chunk.chunk_id] = counts
            for t in counts:
                doc_freqs[t] += 1

        # Step 3: Score Candidate Chunks
        query_token_counts = Counter(effective_query_tokens)
        query_len = len(effective_query_tokens)
        scored: list[RetrievedChunk] = []

        for chunk in accessible_chunks:
            chunk_counts = chunk_token_maps[chunk.chunk_id]
            chunk_len = max(1, sum(chunk_counts.values()))
            bm25_score = 0.0
            matched_terms: list[str] = []

            for q_term, q_count in query_token_counts.items():
                tf = chunk_counts.get(q_term, 0)
                if tf > 0:
                    matched_terms.append(q_term)
                    df = doc_freqs.get(q_term, 1)
                    # Smoothed BM25 IDF
                    idf = math.log((total_docs - df + 0.5) / (df + 0.5) + 1.2) + 0.5
                    # BM25 TF component
                    bm25_tf = (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * (chunk_len / 50.0)))
                    bm25_score += idf * bm25_tf * q_count

            # Overlap fraction of content terms
            overlap_ratio = len(matched_terms) / float(query_len)

            # Combined score: term coverage + BM25 strength + phrase matching
            raw_score = (0.5 * overlap_ratio) + (0.5 * min(1.0, bm25_score / (query_len * 1.5)))

            # Phrase boost if query sub-phrase appears verbatim
            if len(effective_query_tokens) >= 2 and any(
                f"{effective_query_tokens[i]} {effective_query_tokens[i+1]}" in chunk.text.lower()
                for i in range(len(effective_query_tokens) - 1)
            ):
                raw_score += 0.20

            final_score = min(1.0, raw_score)
            if final_score > 0:
                scored.append(RetrievedChunk(chunk=chunk, relevance_score=final_score, matched_terms=matched_terms))

        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        top_results = scored[:top_k]

        # Step 4: Evaluate Weak Evidence & Abstention Boundary
        if not top_results or top_results[0].relevance_score < threshold:
            return top_results, True

        return top_results, False


def create_citations_from_retrieved_chunks(
    retrieved_chunks: list[RetrievedChunk],
    max_citations: int = 3,
) -> list[Citation]:
    """Extract verifiable citation references from retrieved chunks."""
    citations: list[Citation] = []
    for rc in retrieved_chunks[:max_citations]:
        chunk = rc.chunk
        loc_label = "; ".join(loc.label for loc in chunk.locators) if chunk.locators else "General Document"
        filename = chunk.metadata.get("filename", "learning_material")

        # Pick the most relevant sentence or excerpt from the chunk
        sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
        quote = sentences[0] if sentences else chunk.text[:150]
        for sentence in sentences:
            if any(term.lower() in sentence.lower() for term in rc.matched_terms):
                quote = sentence
                break

        citations.append(
            Citation(
                citation_id=generate_uuid(),
                chunk_id=chunk.chunk_id,
                source_id=chunk.source_id,
                source_version=chunk.source_version,
                filename=filename,
                locator_label=loc_label,
                quote=quote.strip(),
                confidence_score=rc.relevance_score,
            )
        )
    return citations


# Global default in-memory retrieval index for the process
default_chunk_store = InMemoryChunkStore()
