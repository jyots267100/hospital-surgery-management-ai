"""CLI entry point to (re-)ingest hospital policy documents into ChromaDB.

Usage:
    python scripts/ingest_policies.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings  # noqa: E402
from app.core.logging_config import configure_logging  # noqa: E402
from app.rag.embeddings import get_embedding_function  # noqa: E402
from app.rag.ingest import ingest_policy_directory  # noqa: E402
from app.rag.vector_store import PolicyVectorStore  # noqa: E402


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    embedding_fn = get_embedding_function(settings.embedding_model)
    vector_store = PolicyVectorStore(
        persist_directory=Path(settings.chroma_persist_directory),
        collection_name=settings.chroma_collection_name,
        embedding_fn=embedding_fn,
    )
    result = ingest_policy_directory(
        policy_dir=settings.policy_docs_path,
        vector_store=vector_store,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    print(f"Ingested documents: {result['documents_ingested']}")
    print(f"Pages: {result['page_count']}, Chunks stored: {result['chunk_count']}")


if __name__ == "__main__":
    main()
