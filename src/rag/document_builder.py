"""Builds RAGDocuments from ServiceRecords, one document per (service, section).

Reuses ``recommender.models.ServiceRecord`` / ``recommender.loader`` as the
single source of truth for service data -- RAG does not re-read or
re-parse the CSV independently, and never imports anything from
``recommender`` beyond these read-only types (docs/rag_retrieval_v1_report.md
§3-4).
"""

from __future__ import annotations

import re
from typing import List, Sequence

from recommender.models import ServiceRecord

from .models import (
    ALL_SECTIONS,
    RAGDocument,
    SECTION_APPLICATION,
    SECTION_CRITERIA,
    SECTION_SUPPORT,
    SECTION_TARGET,
)

# Placeholder values that mean "no real content" in this corpus (confirmed by
# inspecting the CSV -- 25/85 application_original values are the literal
# string "[]", not a missing/empty cell). Must be excluded, never embedded as
# if they were real text. See docs/rag_retrieval_v1_report.md §3.
_EMPTY_MARKERS = {"", "[]"}

_SECTION_FIELD = {
    SECTION_TARGET: "target_original",
    SECTION_CRITERIA: "criteria_original",
    SECTION_SUPPORT: "support_original",
    SECTION_APPLICATION: "application_original",
}

# Sub-chunking only triggers above this length. Measured length distribution
# (docs/rag_retrieval_v1_report.md §5): median section length is 30-95 chars,
# 90th percentile is 130-250 chars, and only ~4-6 sections per field exceed
# 300 chars. 400 was chosen so the overwhelming majority of sections stay as
# a single field-unit chunk, and only genuine outliers (multi-program bullet
# lists, the longest of which is 1286 chars) get split.
CHUNK_SIZE = 400
CHUNK_OVERLAP = 60

# Natural break points actually used by the source agencies in this corpus:
# circled numerals (①②...), the "●" bullet, newlines, and sentence-final
# punctuation. Preferred over blind fixed-length cuts because splitting mid
# numbered-item would separate a program's name from its price/condition.
_BREAK_PATTERN = re.compile(r"(?<=[.!?])\s+|(?=[①②③④⑤⑥⑦⑧⑨⑩])|(?=●)|(?=\n)")


def _split_long_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split ``text`` on natural boundaries into <= ~chunk_size pieces,
    carrying ``overlap`` trailing characters into the next chunk so a
    condition/price split across a chunk boundary still has some context on
    both sides. Falls back to a fixed sliding window only if no natural
    break exists inside an over-long piece. No-op for text within chunk_size.
    """
    if len(text) <= chunk_size:
        return [text]

    pieces = [p for p in _BREAK_PATTERN.split(text) if p and p.strip()]
    if not pieces:
        pieces = [text]

    chunks: List[str] = []
    current = ""
    for piece in pieces:
        if current and len(current) + len(piece) > chunk_size:
            chunks.append(current.strip())
            current = current[-overlap:] + piece
        else:
            current += piece
    if current.strip():
        chunks.append(current.strip())

    final: List[str] = []
    for c in chunks:
        if len(c) <= chunk_size * 1.5:
            final.append(c)
        else:
            start = 0
            while start < len(c):
                final.append(c[start : start + chunk_size])
                start += chunk_size - overlap
    return final


def build_documents(services: Sequence[ServiceRecord]) -> List[RAGDocument]:
    """Build one or more RAGDocuments per (service, section).

    A section whose original field is empty or the "[]" placeholder is
    skipped entirely -- it is never turned into an empty-content document.
    Use ``count_excluded_sections`` to report how many were skipped.
    """
    documents: List[RAGDocument] = []
    for service in services:
        for section in ALL_SECTIONS:
            field_name = _SECTION_FIELD[section]
            text = (getattr(service, field_name, "") or "").strip()
            if text in _EMPTY_MARKERS:
                continue

            chunks = _split_long_text(text)
            for idx, chunk in enumerate(chunks):
                documents.append(
                    RAGDocument(
                        doc_id=f"{service.service_id}::{section}::{idx}",
                        service_id=service.service_id,
                        service_name=service.service_name,
                        section=section,
                        content=chunk,
                        chunk_index=idx,
                        chunk_count=len(chunks),
                        sido=service.sido,
                        sigungu=service.sigungu,
                        service_type_primary=service.service_type_primary,
                        verification_level=service.verification_level,
                        source_type=service.source_api,
                    )
                )
    return documents


def count_excluded_sections(services: Sequence[ServiceRecord]) -> int:
    """Count sections skipped because the original field was empty or the
    "[]" placeholder -- used only for the build report
    (docs/rag_retrieval_v1_report.md §12), not part of the retrievable corpus.
    """
    count = 0
    for service in services:
        for section in ALL_SECTIONS:
            field_name = _SECTION_FIELD[section]
            text = (getattr(service, field_name, "") or "").strip()
            if text in _EMPTY_MARKERS:
                count += 1
    return count
