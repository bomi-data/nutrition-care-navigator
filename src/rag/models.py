"""Typed data structures for the RAG retrieval layer.

RAG never decides *which* service_id gets recommended -- that is entirely
``src/recommender``'s job (rule-based, already validated: see
``docs/recommendation_engine_v1_report.md``). RAG only retrieves official
source passages for a service_id the recommender has already selected. See
``docs/rag_retrieval_v1_report.md`` §1-2 for the full role boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Sections -- one per official-source field in
# data/processed/welfare_services_recommendation_ready.csv (rag_retrieval_v1
# _report.md §4). Fixed vocabulary, not user-extensible.
# ---------------------------------------------------------------------------

SECTION_TARGET = "target"          # target_original -- 지원대상
SECTION_CRITERIA = "criteria"      # criteria_original -- 선정기준
SECTION_SUPPORT = "support"        # support_original -- 지원내용
SECTION_APPLICATION = "application"  # application_original -- 신청방법

ALL_SECTIONS = (SECTION_TARGET, SECTION_CRITERIA, SECTION_SUPPORT, SECTION_APPLICATION)


@dataclass(frozen=True)
class RAGDocument:
    """One retrievable unit: one section, or one sub-chunk of a section, of
    a single service's official source text.

    ``doc_id`` is stable and deterministic (``{service_id}::{section}::{chunk_index}``)
    so the vector store's FAISS integer ids can always be mapped back to a
    document without re-embedding anything.
    """

    doc_id: str
    service_id: str
    service_name: str
    section: str  # one of ALL_SECTIONS
    content: str
    chunk_index: int
    chunk_count: int  # how many chunks this section was split into

    sido: Optional[str]
    sigungu: Optional[str]
    service_type_primary: str
    verification_level: str
    source_type: str  # ServiceRecord.source_api ("local" / "central")

    def metadata(self) -> dict:
        return {
            "doc_id": self.doc_id,
            "service_id": self.service_id,
            "service_name": self.service_name,
            "section": self.section,
            "sido": self.sido,
            "sigungu": self.sigungu,
            "service_type_primary": self.service_type_primary,
            "verification_level": self.verification_level,
            "source_type": self.source_type,
            "chunk_index": self.chunk_index,
            "chunk_count": self.chunk_count,
        }


@dataclass(frozen=True)
class RetrievalResult:
    """One row of a retrieval response -- enough for an LLM step (not built
    in this stage) to cite exactly which official passage it used."""

    service_id: str
    service_name: str
    section: str
    content: str
    score: float  # cosine similarity, higher = more relevant (not a distance)
    metadata: dict

    def as_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "section": self.section,
            "content": self.content,
            "score": self.score,
            "metadata": self.metadata,
        }
