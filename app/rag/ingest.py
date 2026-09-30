"""Ingest the policy corpus into the Chroma vector store.

Usage:
    python -m app.rag.ingest [--reset]

Runs deterministically: files are processed in sorted filename order and chunking has no
randomness, so re-running ingest on an unchanged corpus produces the same chunk IDs/content.
Safe to run on every deploy/startup (idempotent thanks to --reset rebuilding the collection).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from app.config import CORPUS_DIR
from app.rag import vector_store
from app.rag.chunking import chunk_document

SUPPORTED_SUFFIXES = {".md", ".html", ".htm", ".txt"}


def iter_corpus_files(corpus_dir: Path) -> list[Path]:
    return sorted(p for p in corpus_dir.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)


def run_ingest(corpus_dir: Path = CORPUS_DIR, reset: bool = True) -> int:
    start = time.time()
    vector_store.get_collection(reset=reset)

    files = iter_corpus_files(corpus_dir)
    if not files:
        print(f"No corpus files found in {corpus_dir}", file=sys.stderr)
        return 0

    total_chunks = 0
    for path in files:
        chunks = chunk_document(path)
        vector_store.add_chunks(chunks)
        total_chunks += len(chunks)
        print(f"  {path.name}: {len(chunks)} chunks")

    elapsed = time.time() - start
    print(
        f"Ingested {len(files)} documents, {total_chunks} chunks into "
        f"'{vector_store.get_collection().name}' in {elapsed:.2f}s "
        f"(collection count={vector_store.count()})"
    )
    return total_chunks


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest the CPDA policy corpus into Chroma.")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not delete the existing collection before ingesting (append instead).",
    )
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=CORPUS_DIR,
        help="Directory containing policy documents (default: %(default)s)",
    )
    args = parser.parse_args()
    run_ingest(corpus_dir=args.corpus_dir, reset=not args.no_reset)


if __name__ == "__main__":
    main()
