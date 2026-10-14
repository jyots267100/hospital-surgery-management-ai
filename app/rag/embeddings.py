"""Hugging Face sentence-transformers embedding function for ChromaDB.

Loaded once per process (model download/initialization is expensive) and reused
by both the ingestion pipeline and the retriever.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from chromadb import Documents, EmbeddingFunction, Embeddings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingFunction(EmbeddingFunction):
    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        logger.info("Loading embedding model '%s'", model_name)
        self._model = SentenceTransformer(model_name)

    def __call__(self, input: Documents) -> Embeddings:  # noqa: A002 - Chroma's required signature
        vectors = self._model.encode(list(input), show_progress_bar=False, convert_to_numpy=True)
        return vectors.tolist()


@lru_cache
def get_embedding_function(model_name: str) -> SentenceTransformerEmbeddingFunction:
    return SentenceTransformerEmbeddingFunction(model_name)
