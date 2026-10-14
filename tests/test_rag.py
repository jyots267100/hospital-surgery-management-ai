from __future__ import annotations

from pathlib import Path

from app.rag.chunker import chunk_pages
from app.rag.loader import load_policy_documents

POLICY_DIR = Path(__file__).resolve().parent.parent / "policies"


def test_loader_splits_pages_by_marker():
    pages = load_policy_documents(POLICY_DIR)
    cancellation_pages = [p for p in pages if p.document_name == "surgery_cancellation_policy.txt"]
    assert len(cancellation_pages) == 4
    assert all(p.text for p in cancellation_pages)


def test_loader_preserves_page_numbers():
    pages = load_policy_documents(POLICY_DIR)
    cancellation_pages = [p for p in pages if p.document_name == "surgery_cancellation_policy.txt"]
    assert [p.page_number for p in cancellation_pages] == [1, 2, 3, 4]


def test_chunker_respects_size_bound():
    pages = load_policy_documents(POLICY_DIR)
    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=150)
    # A small overshoot is allowed when no good break point exists, but chunks
    # should never be wildly larger than the configured size.
    assert all(len(c.text) <= 1300 for c in chunks)


def test_chunker_assigns_section_metadata():
    pages = load_policy_documents(POLICY_DIR)
    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=150)
    cancellation_chunks = [c for c in chunks if c.document_name == "surgery_cancellation_policy.txt"]
    assert any(c.section and "SECTION 3" in c.section.upper() for c in cancellation_chunks)


def test_chunker_assigns_unique_chunk_ids():
    pages = load_policy_documents(POLICY_DIR)
    chunks = chunk_pages(pages, chunk_size=1000, chunk_overlap=150)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_retrieval_returns_relevant_chunks_with_citations(policy_service):
    result = policy_service.search("Can a completed surgery be cancelled?")
    assert result["sufficient_evidence"] is True
    assert any("surgery_cancellation_policy" in c for c in result["citations"])
    assert all(c.startswith("[") for c in result["citations"])


def test_retrieval_insufficient_evidence_for_offtopic_query(policy_service):
    result = policy_service.search("What is the weather like in Tokyo tomorrow?")
    assert result["sufficient_evidence"] is False
    assert result["citations"] == []


def test_retrieval_metadata_includes_page_and_document(policy_service):
    result = policy_service.search("Can an operating room have two overlapping surgeries booked at the same time?")
    assert result["sufficient_evidence"] is True
    for hit in result["hits"]:
        assert hit["document_name"]
        assert hit["page_number"]


def test_ingestion_chunk_count_positive(policy_service):
    assert policy_service.collection_size() > 0
