"""Splits loaded document pages into overlapping text chunks with metadata.

Chunk size/overlap are configurable via CHUNK_SIZE / CHUNK_OVERLAP (defaults:
1000 chars / 150 chars). These defaults were chosen because:
  - Policy paragraphs in this corpus run roughly 400-900 characters, so a
    1000-character chunk usually captures one to two full paragraphs/section
    points without truncating a rule mid-sentence.
  - A 150-character overlap (~15%) is enough to carry a trailing sentence or
    section heading into the next chunk so a rule split across a chunk
    boundary is still retrievable from either side, without tripling storage
    the way a 50% overlap would.

The splitter prefers breaking on paragraph boundaries ("\n\n"), falling back to
sentence boundaries, and only hard-cuts mid-sentence as a last resort.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.rag.loader import DocumentPage

_SECTION_RE = re.compile(r"^SECTION\s+\d+[:.]\s*.+$", re.IGNORECASE | re.MULTILINE)


@dataclass
class Chunk:
    chunk_id: str
    document_name: str
    page_number: int
    section: str | None
    text: str


def _active_section(text: str, offset: int) -> str | None:
    section = None
    for match in _SECTION_RE.finditer(text, 0, offset + 1):
        section = match.group(0).strip()
    return section


def _split_text(text: str, chunk_size: int, chunk_overlap: int) -> list[tuple[int, str]]:
    """Returns (start_offset, chunk_text) pairs covering the whole text."""
    if len(text) <= chunk_size:
        return [(0, text)] if text.strip() else []

    spans: list[tuple[int, str]] = []
    start = 0
    text_len = len(text)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        if end < text_len:
            # Prefer a paragraph break, then a sentence break, within the tail of the window.
            window = text[start:end]
            break_point = window.rfind("\n\n")
            if break_point == -1 or break_point < chunk_size * 0.4:
                sentence_break = max(window.rfind(". "), window.rfind(".\n"))
                if sentence_break != -1 and sentence_break >= chunk_size * 0.4:
                    break_point = sentence_break + 1
            if break_point != -1 and break_point >= chunk_size * 0.4:
                end = start + break_point

        chunk_text = text[start:end].strip()
        if chunk_text:
            spans.append((start, chunk_text))

        if end >= text_len:
            break
        start = max(end - chunk_overlap, start + 1)

    return spans


def chunk_pages(pages: list[DocumentPage], chunk_size: int = 1000, chunk_overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page in pages:
        for i, (offset, chunk_text) in enumerate(_split_text(page.text, chunk_size, chunk_overlap)):
            section = _active_section(page.text, offset)
            chunk_id = f"{page.document_name}::p{page.page_number}::c{i}"
            chunks.append(Chunk(
                chunk_id=chunk_id,
                document_name=page.document_name,
                page_number=page.page_number,
                section=section,
                text=chunk_text,
            ))
    return chunks
