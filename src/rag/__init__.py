"""RAG retrieval layer -- evidence search only, never recommendation.

Public API:

    from rag import (
        build_documents, Embedder, VectorStore,
        retrieve, retrieve_for_service,
    )

See docs/rag_retrieval_v1_report.md for the full design and the role
boundary against src/recommender (which alone decides match_score /
match_level / which service_ids get recommended).
"""

from .document_builder import build_documents, count_excluded_sections
from .embeddings import Embedder
from .generation_models import (
    EvidenceItem,
    GroundedAnswer,
    GroundedGenerationRequest,
    LLMGeneratedFields,
)
from .generator import (
    ClaudeGenerationClient,
    FakeGenerationClient,
    GenerationClient,
    api_key_configured,
    generate_answer,
)
from .guardrails import GroundednessReport, check_groundedness
from .models import ALL_SECTIONS, RAGDocument, RetrievalResult
from .retriever import infer_section_hint, retrieve, retrieve_for_service
from .vectorstore import VectorStore, VectorStoreError

__all__ = [
    "build_documents",
    "count_excluded_sections",
    "Embedder",
    "ALL_SECTIONS",
    "RAGDocument",
    "RetrievalResult",
    "infer_section_hint",
    "retrieve",
    "retrieve_for_service",
    "VectorStore",
    "VectorStoreError",
    # Generation v1
    "EvidenceItem",
    "GroundedAnswer",
    "GroundedGenerationRequest",
    "LLMGeneratedFields",
    "ClaudeGenerationClient",
    "FakeGenerationClient",
    "GenerationClient",
    "api_key_configured",
    "generate_answer",
    "GroundednessReport",
    "check_groundedness",
]
