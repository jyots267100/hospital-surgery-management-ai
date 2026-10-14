"""Thin wrapper around a persistent ChromaDB collection for hospital policy chunks."""
from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.core.exceptions import RAGError
from app.rag.chunker import Chunk
from app.rag.embeddings import SentenceTransformerEmbeddingFunction

logger = logging.getLogger(__name__)


class PolicyVectorStore:
    def __init__(self, persist_directory: Path, collection_name: str, embedding_fn: SentenceTransformerEmbeddingFunction) -> None:
        self._client = chromadb.PersistentClient(
            path=str(persist_directory), settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection_name = collection_name
        self._embedding_fn = embedding_fn
        self._collection = self._client.get_or_create_collection(
            name=collection_name, embedding_function=embedding_fn,
        )

    def reset(self) -> None:
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:  # noqa: BLE001 - collection may not exist yet
            pass
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name, embedding_function=self._embedding_fn,
        )

    def add_chunks(self, chunks: list[Chunk]) -> int:
        if not chunks:
            return 0
        try:
            self._collection.add(
                ids=[c.chunk_id for c in chunks],
                documents=[c.text for c in chunks],
                metadatas=[
                    {
                        "document_name": c.document_name,
                        "page_number": c.page_number,
                        "section": c.section or "",
                        "chunk_id": c.chunk_id,
                    }
                    for c in chunks
                ],
            )
        except Exception as exc:  # noqa: BLE001
            raise RAGError(f"Failed to add chunks to vector store: {exc}") from exc
        return len(chunks)

    def count(self) -> int:
        return self._collection.count()

    def query(self, query_text: str, top_k: int) -> list[dict]:
        try:
            result = self._collection.query(query_texts=[query_text], n_results=top_k)
        except Exception as exc:  # noqa: BLE001
            raise RAGError(f"Vector store query failed: {exc}") from exc

        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]

        hits = []
        for text, meta, distance in zip(documents, metadatas, distances):
            hits.append({
                "text": text,
                "document_name": meta.get("document_name"),
                "page_number": meta.get("page_number"),
                "section": meta.get("section") or None,
                "chunk_id": meta.get("chunk_id"),
                "distance": distance,
                "similarity": max(0.0, 1.0 - distance),
            })
        return hits
