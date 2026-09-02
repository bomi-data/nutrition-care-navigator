"""Retrieval entry points.

Two hard rules enforced here (docs/rag_retrieval_v1_report.md §8-9):

1. Every retrieval call takes an explicit ``service_ids`` (or single
   ``service_id``) argument. There is no "search the whole 85-service
   corpus" function exported from this module -- the recommender decides
   which service_id(s) are in play *before* RAG ever runs, and RAG cannot
   widen that set back out. This is what keeps cross-service contamination
   at zero (see tests/rag/test_contamination.py).
2. A section keyword hint narrows the search first, but never *excludes*
   evidence outright: if the hinted section(s) don't fill top_k, remaining
   slots are backfilled with plain vector similarity over the same
   service-scoped candidate set. A missed keyword rule can only reorder
   results, never drop evidence that would otherwise have been found.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from .embeddings import Embedder
from .models import (
    ALL_SECTIONS,
    RetrievalResult,
    SECTION_APPLICATION,
    SECTION_CRITERIA,
    SECTION_SUPPORT,
    SECTION_TARGET,
)
from .vectorstore import VectorStore

DEFAULT_TOP_K = 3

# Keyword -> candidate section(s), checked in order, first match wins.
# Deliberately small and literal (no LLM, no fuzzy matching) so behavior is
# predictable and auditable. "누가"/"대상"/"자격" type questions can be
# answered from either target or criteria in this corpus (both fields
# describe eligibility, just at different granularity -- see
# docs/rag_retrieval_v1_report.md §9), so both are hinted together.
_SECTION_KEYWORD_RULES: List[tuple] = [
    (("신청", "어떻게", "방법", "서류", "접수", "어디에"), (SECTION_APPLICATION,)),
    (("얼마나", "얼마", "몇 번", "몇번", "횟수", "주기", "지원 내용", "무엇을", "혜택", "제공", "받을 수"), (SECTION_SUPPORT,)),
    (("저소득", "수급자", "차상위", "소득", "선정기준", "기준"), (SECTION_CRITERIA,)),
    (("거동", "장애", "독거", "나이", "연령", "대상", "자격", "누가", "이용할 수"), (SECTION_TARGET, SECTION_CRITERIA)),
]


def infer_section_hint(query: str) -> Optional[Sequence[str]]:
    """Best-effort keyword rule -> candidate section(s), or None if nothing
    matched (ambiguous queries like "이거 괜찮나요?" fall through to plain
    vector search over every section -- see §18 of the report)."""
    for keywords, sections in _SECTION_KEYWORD_RULES:
        if any(kw in query for kw in keywords):
            return sections
    return None


def retrieve(
    store: VectorStore,
    embedder: Embedder,
    query: str,
    service_ids: Sequence[str],
    top_k: int = DEFAULT_TOP_K,
) -> List[RetrievalResult]:
    """Retrieve the top_k most relevant document chunks for ``query``,
    restricted to ``service_ids``. Never returns a document belonging to any
    other service_id.
    """
    if not query or not query.strip():
        return []
    if not service_ids:
        return []

    candidates = store.documents_for_service_ids(service_ids)
    if not candidates:
        return []
    candidate_rows = [row for row, _ in candidates]

    query_vector = embedder.embed_query(query)
    hinted_sections = infer_section_hint(query)

    results = []
    seen_doc_ids = set()

    if hinted_sections:
        for doc, score in store.search_within(query_vector, candidate_rows, top_k, section_filter=hinted_sections):
            if doc.doc_id not in seen_doc_ids:
                results.append((doc, score))
                seen_doc_ids.add(doc.doc_id)

    if len(results) < top_k:
        for doc, score in store.search_within(query_vector, candidate_rows, top_k + len(seen_doc_ids), section_filter=None):
            if doc.doc_id in seen_doc_ids:
                continue
            results.append((doc, score))
            seen_doc_ids.add(doc.doc_id)
            if len(results) >= top_k:
                break

    # Intentionally NOT re-sorted by score across the two groups: hinted-
    # section results (already sorted among themselves) are kept ahead of
    # vector-only fallback results, so the section hint actually prioritizes
    # instead of being immediately overridden by a higher-scoring document
    # from an unrelated section. See module docstring rule 2.
    results = results[:top_k]

    return [
        RetrievalResult(
            service_id=doc.service_id,
            service_name=doc.service_name,
            section=doc.section,
            content=doc.content,
            score=score,
            metadata=doc.metadata(),
        )
        for doc, score in results
    ]


def retrieve_for_service(
    store: VectorStore,
    embedder: Embedder,
    service_id: str,
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> List[RetrievalResult]:
    """Convenience wrapper for the single-service case."""
    return retrieve(store, embedder, query, service_ids=[service_id], top_k=top_k)
