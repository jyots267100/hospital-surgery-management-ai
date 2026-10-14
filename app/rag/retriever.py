"""High-level policy retrieval: query -> ranked chunks with an insufficient-evidence
signal, so the agent can honestly say "I don't have enough information" instead of
guessing at policy content.
"""
from __future__ import annotations

from app.core.security import wrap_untrusted_content
from app.rag.vector_store import PolicyVectorStore

# Below this cosine-similarity threshold, retrieved chunks are considered too
# weak to ground an answer. Chosen empirically against this corpus: on-topic
# queries against the six seeded policies consistently score above ~0.3, while
# off-topic queries (e.g. "what's the weather") score below it.
MIN_RELEVANCE_SCORE = 0.30


class PolicyRetriever:
    def __init__(self, vector_store: PolicyVectorStore, top_k: int) -> None:
        self._vector_store = vector_store
        self._top_k = top_k

    def retrieve(self, query: str, top_k: int | None = None) -> dict:
        hits = self._vector_store.query(query, top_k or self._top_k)
        relevant_hits = [h for h in hits if h["similarity"] >= MIN_RELEVANCE_SCORE]

        citations = [
            f"[{h['document_name']} - Page {h['page_number']}]" + (f" ({h['section']})" if h["section"] else "")
            for h in relevant_hits
        ]
        context_blocks = [
            wrap_untrusted_content(citations[i], h["text"]) for i, h in enumerate(relevant_hits)
        ]

        return {
            "query": query,
            "hits": relevant_hits,
            "all_hits": hits,
            "citations": citations,
            "context": "\n\n".join(context_blocks),
            "sufficient_evidence": len(relevant_hits) > 0,
        }
