"""Loads hospital policy documents (.txt or .pdf) from a directory and splits them
into per-page text with metadata, preserving page numbers for citation.

Text files use an explicit "--- PAGE N ---" marker convention (see policies/*.txt).
PDF files are parsed with pypdf, where pages are native.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

_PAGE_MARKER_RE = re.compile(r"-{3,}\s*PAGE\s+(\d+)\s*-{3,}", re.IGNORECASE)


@dataclass
class DocumentPage:
    document_name: str
    page_number: int
    text: str


def _load_txt(path: Path) -> list[DocumentPage]:
    raw = path.read_text(encoding="utf-8")
    matches = list(_PAGE_MARKER_RE.finditer(raw))
    pages: list[DocumentPage] = []

    if not matches:
        # No page markers -- treat the whole file as page 1.
        return [DocumentPage(document_name=path.name, page_number=1, text=raw.strip())]

    # Content before the first marker (title/header block) is prepended to page 1.
    preamble = raw[: matches[0].start()].strip()
    for i, match in enumerate(matches):
        page_number = int(match.group(1))
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        text = raw[start:end].strip()
        if page_number == 1 and preamble:
            text = f"{preamble}\n\n{text}"
        pages.append(DocumentPage(document_name=path.name, page_number=page_number, text=text))
    return pages


def _load_pdf(path: Path) -> list[DocumentPage]:
    reader = PdfReader(str(path))
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(DocumentPage(document_name=path.name, page_number=i, text=text))
    return pages


def load_policy_documents(policy_dir: Path) -> list[DocumentPage]:
    """Loads every .txt and .pdf file in policy_dir into a flat list of pages."""
    pages: list[DocumentPage] = []
    for path in sorted(policy_dir.glob("*")):
        if path.suffix.lower() == ".txt":
            pages.extend(_load_txt(path))
        elif path.suffix.lower() == ".pdf":
            pages.extend(_load_pdf(path))
    return pages
