"""Thin wrapper around a persistent Chroma collection used for the policy RAG index.

Embeddings use Chroma's bundled default embedding function (a local ONNX MiniLM model). This is
deliberately chosen over `sentence-transformers`/torch to keep memory usage low enough for a
Render/Railway free-tier web service, while still being a fully local, free, deterministic
embedding model (no API key, no per-call cost).
"""
from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions

from app.config import CHROMA_COLLECTION_NAME, CHROMA_PERSIST_DIR
from app.rag.chunking import Chunk

_client = None
_collection = None


def _get_client():
    global _client
    if _client is None:
        CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(CHROMA_PERSIST_DIR),
            settings=chromadb.config.Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(reset: bool = False):
    global _collection
    client = _get_client()
    embedding_fn = embedding_functions.DefaultEmbeddingFunction()

    if reset:
        try:
            client.delete_collection(CHROMA_COLLECTION_NAME)
        except Exception:
            pass
        _collection = None

    if _collection is None:
        _collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def add_chunks(chunks: list[Chunk]) -> None:
    if not chunks:
        return
    collection = get_collection()
    collection.add(
        ids=[c.chunk_id for c in chunks],
        documents=[c.text for c in chunks],
        metadatas=[
            {
                "doc_id": c.doc_id,
                "doc_title": c.doc_title,
                "category": c.category,
                "section": c.section,
                "source_file": c.source_file,
                "format": c.format,
            }
            for c in chunks
        ],
    )


def count() -> int:
    return get_collection().count()


def query(query_text: str, top_k: int, where: dict | None = None) -> dict:
    collection = get_collection()
    return collection.query(
        query_texts=[query_text],
        n_results=top_k,
        where=where,
    )


def get_by_doc(doc_id: str) -> dict:
    collection = get_collection()
    return collection.get(where={"doc_id": doc_id})
