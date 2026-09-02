"""Streamlit <-> Grounded RAG Generation translation layer.

Mirrors ``streamlit_ui/adapter.py``'s role for the recommender: pure,
testable functions only -- **no ``import streamlit``, no ``st.*`` calls
anywhere in this file**. ``app/streamlit_app.py`` is the only place that
touches the Streamlit runtime; it assembles widgets and calls the functions
here.

Service boundary (docs/streamlit_rag_integration_report.md §4): a UI card
for service A must never see service B's evidence or answer. Every function
here that deals with one service takes its ``service_id``/``RecommendationResult``
explicitly -- there is no "current service" global, and every retrieval call
goes through ``rag.retriever.retrieve_for_service`` (already scoped to one
service_id) rather than the unscoped whole-corpus search that doesn't even
exist in ``rag``'s public API (rag_retrieval_v1_report.md §8).

Also owns on-demand resource loading (``load_rag_resources``) so
``app/streamlit_app.py`` only needs one ``st.cache_resource``-wrapped call
instead of re-implementing vector store bootstrap logic.
"""

from __future__ import annotations

import os
import sys
import traceback
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from rag.document_builder import build_documents
from rag.embeddings import Embedder
from rag.generation_models import GroundedAnswer, GroundedGenerationRequest, LLMGeneratedFields
from rag.generator import (
    ClaudeGenerationClient,
    FakeGenerationClient,
    GenerationClient,
    api_key_configured,
    generate_answer,
)
from rag.models import RetrievalResult
from rag.retriever import DEFAULT_TOP_K, retrieve_for_service
from rag.vectorstore import DEFAULT_VECTORSTORE_DIR, VectorStore, VectorStoreError
from recommender.loader import load_services
from recommender.models import RecommendationResult, TriState, UserProfile

# ---------------------------------------------------------------------------
# Preset questions (instructions §5)
# ---------------------------------------------------------------------------

PRESET_QUESTIONS: List[str] = [
    "이 서비스는 어떤 서비스인가요?",
    "어떤 지원을 받을 수 있나요?",
    "제가 대상일 가능성이 있나요?",
    "어떻게 신청하나요?",
]


# ---------------------------------------------------------------------------
# UserProfile -> human-readable summary for the generation prompt
# ---------------------------------------------------------------------------

_TRISTATE_LABEL = {
    TriState.TRUE: "예",
    TriState.FALSE: "아니오",
    TriState.UNKNOWN: "확인 필요(모름)",
}


def format_profile_summary(profile: UserProfile) -> str:
    """A short Korean summary of the user's profile, safe to pass into the
    generation prompt. UNKNOWN fields are always rendered as "확인
    필요(모름)" -- never as "아니오"/false (instructions §16)."""
    parts: List[str] = []

    if profile.sido:
        region = profile.sido + (f" {profile.sigungu}" if profile.sigungu else "")
        parts.append(f"거주지: {region}")
    else:
        parts.append("거주지: 확인 필요")

    parts.append(f"연령: {profile.age}세" if profile.age is not None else "연령: 확인 필요")
    parts.append(f"장애 여부: {_TRISTATE_LABEL[profile.has_disability]}")
    parts.append(f"저소득 여부: {_TRISTATE_LABEL[profile.low_income_status]}")
    parts.append(f"독거 여부: {_TRISTATE_LABEL[profile.lives_alone]}")
    parts.append(f"거동불편 여부: {_TRISTATE_LABEL[profile.mobility_difficulty]}")
    parts.append(f"식사준비 어려움: {_TRISTATE_LABEL[profile.meal_preparation_difficulty]}")
    parts.append(f"최근 퇴원: {_TRISTATE_LABEL[profile.recent_discharge]}")

    desired = profile.effective_desired_support()
    if desired:
        parts.append("희망 도움: " + ", ".join(sorted(d.value for d in desired)))
    else:
        parts.append("희망 도움: 특정하지 않음(모든 유형 확인 필요)")

    return ", ".join(parts)


def build_generation_request(
    result: RecommendationResult,
    profile: UserProfile,
    question: str,
    retrieved_documents: Sequence[RetrievalResult],
) -> GroundedGenerationRequest:
    """Assemble a GroundedGenerationRequest for exactly ``result.service_id``.

    ``retrieved_documents`` must already be scoped to that service_id (the
    caller gets this for free by using ``retrieve_for_service`` -- see
    ``run_generation`` below).
    """
    return GroundedGenerationRequest(
        service_id=result.service_id,
        service_name=result.service_name,
        user_profile_summary=format_profile_summary(profile),
        recommendation_level=result.match_level.value,
        recommendation_reasons=list(result.recommendation_reasons),
        confirmation_needed=list(result.confirmation_needed),
        user_question=question,
        retrieved_documents=list(retrieved_documents),
    )


# ---------------------------------------------------------------------------
# Session state keys -- always service_id-scoped (instructions §11)
# ---------------------------------------------------------------------------


def answer_session_key(service_id: str) -> str:
    return f"rag_answer::{service_id}"


def pending_question_session_key(service_id: str) -> str:
    return f"rag_pending_question::{service_id}"


def error_session_key(service_id: str) -> str:
    return f"rag_error::{service_id}"


def free_text_session_key(service_id: str) -> str:
    return f"rag_free_text::{service_id}"


# ---------------------------------------------------------------------------
# Generation client selection (instructions §8-9)
# ---------------------------------------------------------------------------

GENERATION_MODE_ENV = "RAG_GENERATION_MODE"
MODE_AUTO = "auto"
MODE_FAKE = "fake"
MODE_CLAUDE = "claude"

_UNAVAILABLE_REASON = (
    "AI 기반 설명 기능이 현재 설정되지 않았습니다. 기존 추천 결과와 공식 원문은 계속 "
    "확인할 수 있습니다."
)


def _default_fake_response(system_prompt: str, user_prompt: str) -> LLMGeneratedFields:
    return LLMGeneratedFields(
        summary="(테스트 모드) CONTEXT에 나온 내용을 바탕으로 한 서비스 요약이에요.",
        why_recommended="(테스트 모드) 추천 이유를 CONTEXT 기준으로 다시 설명해요.",
        eligibility_explanation="(테스트 모드) 관련 조건이 CONTEXT에서 확인돼요. 확정은 아니에요.",
        support_explanation="(테스트 모드) CONTEXT에 나온 지원 내용을 안내해요.",
        application_explanation="",
        confirmation_items=[],
    )


@dataclass
class ResolvedGenerationClient:
    client: Optional[GenerationClient]
    mode: str  # "fake" | "claude" | "unavailable"
    is_fake: bool
    unavailable_reason: Optional[str] = None


def resolve_generation_client(mode_override: Optional[str] = None) -> ResolvedGenerationClient:
    """Decide Fake vs. real Claude vs. unavailable.

    - ``mode_override`` (or the ``RAG_GENERATION_MODE`` env var) == "fake":
      always use ``FakeGenerationClient`` -- for local dev/testing only.
    - == "claude": always try the real API; unavailable if no API key.
    - "auto" (default, and any unrecognized value): use Claude if
      ``ANTHROPIC_API_KEY`` is set, otherwise unavailable. Never silently
      falls back to Fake -- Fake only ever appears via explicit opt-in, so a
      user can never mistake a canned test answer for a real one (§9).
    """
    mode = (mode_override or os.environ.get(GENERATION_MODE_ENV, MODE_AUTO)).strip().lower()

    if mode == MODE_FAKE:
        return ResolvedGenerationClient(
            client=FakeGenerationClient(response_fn=_default_fake_response), mode="fake", is_fake=True
        )

    if mode == MODE_CLAUDE:
        if not api_key_configured():
            return ResolvedGenerationClient(
                client=None, mode="unavailable", is_fake=False, unavailable_reason=_UNAVAILABLE_REASON
            )
        return ResolvedGenerationClient(client=ClaudeGenerationClient(), mode="claude", is_fake=False)

    # auto
    if api_key_configured():
        return ResolvedGenerationClient(client=ClaudeGenerationClient(), mode="claude", is_fake=False)
    return ResolvedGenerationClient(
        client=None, mode="unavailable", is_fake=False, unavailable_reason=_UNAVAILABLE_REASON
    )


# ---------------------------------------------------------------------------
# Vector store / embedder bootstrap (instructions §10)
# ---------------------------------------------------------------------------


def load_rag_resources() -> Tuple[VectorStore, Embedder]:
    """Load the pre-built vector store from disk if present (fast path --
    see rag_retrieval_v1_report.md §18, ~0.04s), otherwise build it once
    in-memory (and best-effort persist it for next time). The caller
    (``app/streamlit_app.py``) wraps this in ``st.cache_resource`` so it
    only ever runs once per app process, not once per rerun/click.
    """
    embedder = Embedder()
    try:
        store = VectorStore.load(DEFAULT_VECTORSTORE_DIR)
    except VectorStoreError:
        services = load_services()
        documents = build_documents(services)
        vectors = embedder.embed_documents([d.content for d in documents])
        store = VectorStore.build(documents, vectors, model_name=embedder.model_name)
        try:
            store.save(DEFAULT_VECTORSTORE_DIR)
        except OSError:
            pass  # best-effort; still usable in-memory for this run
    return store, embedder


# ---------------------------------------------------------------------------
# End-to-end on-demand generation (retrieval -> generation), one service_id
# ---------------------------------------------------------------------------


class GenerationUnavailableError(Exception):
    """Raised when no generation client is available (no API key, auto/claude
    mode). Distinct from a runtime API failure -- see GenerationOutcome."""


def run_generation(
    resolved: ResolvedGenerationClient,
    store: VectorStore,
    embedder: Embedder,
    result: RecommendationResult,
    profile: UserProfile,
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> GroundedAnswer:
    """service_id -> retrieve_for_service -> generate_answer, all scoped to
    ``result.service_id``. Raises ``GenerationUnavailableError`` if no
    client is configured, or whatever the underlying client raises on
    failure (network/auth/etc.) -- see ``safe_run_generation`` for the
    UI-safe wrapper that catches these.
    """
    if resolved.client is None:
        raise GenerationUnavailableError(resolved.unavailable_reason or _UNAVAILABLE_REASON)

    retrieved = retrieve_for_service(store, embedder, result.service_id, question, top_k=top_k)
    request = build_generation_request(result, profile, question, retrieved)
    return generate_answer(resolved.client, request)


@dataclass
class GenerationOutcome:
    answer: Optional[GroundedAnswer]
    error_message: Optional[str]
    unavailable_reason: Optional[str]


_GENERATION_ERROR_MESSAGE = (
    "AI 설명을 불러오지 못했습니다. 추천 결과와 공식 원문은 계속 확인할 수 있습니다."
)


def safe_run_generation(
    resolved: ResolvedGenerationClient,
    store: VectorStore,
    embedder: Embedder,
    result: RecommendationResult,
    profile: UserProfile,
    question: str,
    top_k: int = DEFAULT_TOP_K,
) -> GenerationOutcome:
    """UI-safe wrapper: never raises. Logs the real exception server-side
    only (stderr) -- the returned message never contains exception text or
    any credential (instructions §17/§24)."""
    if resolved.client is None:
        return GenerationOutcome(answer=None, error_message=None, unavailable_reason=resolved.unavailable_reason)

    try:
        answer = run_generation(resolved, store, embedder, result, profile, question, top_k=top_k)
        return GenerationOutcome(answer=answer, error_message=None, unavailable_reason=None)
    except Exception as e:  # pragma: no cover - defensive catch-all, mirrors app.py's existing pattern
        print("[rag_adapter] generation failed:", repr(e), file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return GenerationOutcome(answer=None, error_message=_GENERATION_ERROR_MESSAGE, unavailable_reason=None)


# ---------------------------------------------------------------------------
# GroundedAnswer -> display-ready structures
# ---------------------------------------------------------------------------

SECTION_DISPLAY_ORDER = ("target", "criteria", "support", "application")


def evidence_grouped_by_section(evidence) -> List[Tuple[str, str, List[str]]]:
    """(section, section_label, [content, ...]) tuples in a fixed display
    order, only for sections that actually have evidence -- used to render
    the "답변 근거 보기" expander (instructions §14)."""
    by_section: Dict[str, List[str]] = {}
    label_by_section: Dict[str, str] = {}
    for e in evidence:
        by_section.setdefault(e.section, []).append(e.content)
        label_by_section[e.section] = e.section_label

    return [
        (section, label_by_section[section], by_section[section])
        for section in SECTION_DISPLAY_ORDER
        if section in by_section
    ]


def answer_display_fields(answer: GroundedAnswer) -> List[Tuple[str, str]]:
    """(label, text) pairs for non-empty GroundedAnswer text fields, in a
    fixed order. Empty fields are omitted (instructions §12: "빈 필드는
    숨겨도 됩니다")."""
    fields = [
        ("서비스 요약", answer.summary),
        ("왜 추천되었나요?", answer.why_recommended),
        ("자격 관련 설명", answer.eligibility_explanation),
        ("지원 내용", answer.support_explanation),
        ("신청 방법", answer.application_explanation),
    ]
    return [(label, text) for label, text in fields if text and text.strip()]
