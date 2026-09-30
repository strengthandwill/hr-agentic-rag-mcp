"""Top-k retrieval with a lightweight lexical rerank on top of vector similarity.

Reranking approach: Chroma returns cosine distance for the top `fetch_k` candidates; we combine
that with a simple keyword-overlap score (fraction of query terms present verbatim in the chunk)
so that chunks mentioning the user's exact terms (e.g. a specific policy word like "overseas" or
"encashment") are not out-ranked by purely semantic neighbours. This is a small, explainable
reranking step appropriate for a short, well-structured policy corpus.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import RETRIEVAL_TOP_K
from app.rag import vector_store

_WORD_RE = re.compile(r"[a-z0-9]+")


@dataclass
class RetrievedChunk:
    chunk_id: str
    doc_id: str
    doc_title: str
    category: str
    section: str
    source_file: str
    snippet: str
    vector_score: float
    keyword_score: float
    combined_score: float


def _keyword_overlap(query: str, text: str) -> float:
    query_terms = set(_WORD_RE.findall(query.lower()))
    if not query_terms:
        return 0.0
    text_terms = set(_WORD_RE.findall(text.lower()))
    hits = sum(1 for t in query_terms if t in text_terms)
    return hits / len(query_terms)


def retrieve(
    query_text: str,
    top_k: int = RETRIEVAL_TOP_K,
    doc_id_filter: str | None = None,
    fetch_k_multiplier: int = 3,
) -> list[RetrievedChunk]:
    where = {"doc_id": doc_id_filter} if doc_id_filter else None
    fetch_k = max(top_k * fetch_k_multiplier, top_k)
    raw = vector_store.query(query_text, top_k=fetch_k, where=where)

    ids = raw.get("ids", [[]])[0]
    docs = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    dists = raw.get("distances", [[]])[0]

    candidates: list[RetrievedChunk] = []
    for chunk_id, doc_text, meta, dist in zip(ids, docs, metas, dists):
        vector_score = max(0.0, 1.0 - dist)  # cosine distance -> similarity
        keyword_score = _keyword_overlap(query_text, doc_text)
        combined = 0.7 * vector_score + 0.3 * keyword_score
        candidates.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                doc_id=meta.get("doc_id", "unknown"),
                doc_title=meta.get("doc_title", "unknown"),
                category=meta.get("category", "unknown"),
                section=meta.get("section", "unknown"),
                source_file=meta.get("source_file", "unknown"),
                snippet=doc_text[:600],
                vector_score=round(vector_score, 4),
                keyword_score=round(keyword_score, 4),
                combined_score=round(combined, 4),
            )
        )

    candidates.sort(key=lambda c: c.combined_score, reverse=True)
    return candidates[:top_k]
