from __future__ import annotations

from pathlib import Path

from app.rag.ingest import ingest_policy_directory
from app.rag.retriever import PolicyRetriever
from app.rag.vector_store import PolicyVectorStore


class PolicyService:
    """Facade over the RAG retriever + ingestion pipeline used by tools and the API."""

    def __init__(self, retriever: PolicyRetriever, vector_store: PolicyVectorStore, policy_dir: Path,
                 chunk_size: int, chunk_overlap: int) -> None:
        self._retriever = retriever
        self._vector_store = vector_store
        self._policy_dir = policy_dir
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    def search(self, query: str, top_k: int | None = None) -> dict:
        return self._retriever.retrieve(query, top_k=top_k)

    def reingest(self) -> dict:
        return ingest_policy_directory(
            policy_dir=self._policy_dir,
            vector_store=self._vector_store,
            chunk_size=self._chunk_size,
            chunk_overlap=self._chunk_overlap,
            reset=True,
        )

    def collection_size(self) -> int:
        return self._vector_store.count()
