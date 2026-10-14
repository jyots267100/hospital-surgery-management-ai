"""Orchestrates the full ingestion pipeline: load -> chunk -> embed -> store.

Used by scripts/ingest_policies.py (one-off CLI ingestion) and by the
POST /api/v1/policies/ingest API endpoint (re-ingestion at runtime).
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.rag.chunker import chunk_pages
from app.rag.loader import load_policy_documents
from app.rag.vector_store import PolicyVectorStore

logger = logging.getLogger(__name__)


def ingest_policy_directory(
    policy_dir: Path,
    vector_store: PolicyVectorStore,
    chunk_size: int,
    chunk_overlap: int,
    reset: bool = True,
) -> dict:
    pages = load_policy_documents(policy_dir)
    chunks = chunk_pages(pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    if reset:
        vector_store.reset()
    added = vector_store.add_chunks(chunks)

    document_names = sorted({p.document_name for p in pages})
    logger.info("Ingested %d documents, %d pages, %d chunks", len(document_names), len(pages), added)
    return {
        "documents_ingested": document_names,
        "page_count": len(pages),
        "chunk_count": added,
    }
