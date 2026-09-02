"""Generation orchestration: request -> (Python evidence gate) -> Claude ->
(Python deterministic overrides + sanitization) -> GroundedAnswer.

The ``GenerationClient`` abstraction exists specifically so this module --
and every test of it except the explicit smoke test -- never has to call the
real Claude API (docs/rag_generation_v1_report.md §11).
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Protocol

from .generation_models import (
    NO_APPLICATION_EVIDENCE_MESSAGE,
    SAFETY_NOTICE,
    SECTION_LABELS_KO,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_OK,
    EvidenceItem,
    GroundedAnswer,
    GroundedGenerationRequest,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    LLMGeneratedFields,
)
from .guardrails import (
    evidence_text_blob,
    has_any_evidence,
    missing_sections_ko,
    sanitize_answer,
    sections_with_evidence,
)
from .prompt_builder import SYSTEM_PROMPT, build_user_prompt

DEFAULT_MODEL = "claude-opus-5"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"


def api_key_configured() -> bool:
    """True only if ANTHROPIC_API_KEY is set and non-blank -- gates the
    real-API smoke test (instructions §12). Other Anthropic auth methods
    (OAuth profile, WIF) are intentionally not probed here; this project
    uses the plain API-key flow documented in .env.example."""
    return bool(os.environ.get(ANTHROPIC_API_KEY_ENV, "").strip())


class GenerationClient(Protocol):
    """Anything that can turn a (system_prompt, user_prompt) pair into
    ``LLMGeneratedFields``. ``ClaudeGenerationClient`` and
    ``FakeGenerationClient`` both implement this -- ``generate_answer``
    never knows or cares which one it got."""

    def generate(self, system_prompt: str, user_prompt: str) -> LLMGeneratedFields: ...


class ClaudeGenerationClient:
    """Real Claude API client. Imports ``anthropic`` lazily so this module
    (and everything that imports it) stays importable even when the
    ``anthropic`` package or an API key isn't available -- required by
    instructions §3 ("API Key가 없는 환경에서도 import나 기존 테스트가 깨지지
    않아야 합니다")."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: Optional[str] = None):
        self.model = model
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self._api_key) if self._api_key else anthropic.Anthropic()
        return self._client

    def generate(self, system_prompt: str, user_prompt: str) -> LLMGeneratedFields:
        client = self._get_client()
        response = client.messages.parse(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            output_format=LLMGeneratedFields,
        )
        return response.parsed_output


class FakeGenerationClient:
    """Deterministic stand-in for tests. Pass a fixed ``response`` or a
    ``response_fn(system_prompt, user_prompt) -> LLMGeneratedFields`` to
    control exactly what "the model" returns -- including deliberately
    adversarial output, to verify guardrails catch it regardless of model
    behavior."""

    def __init__(
        self,
        response: Optional[LLMGeneratedFields] = None,
        response_fn: Optional[Callable[[str, str], LLMGeneratedFields]] = None,
    ):
        self._response = response
        self._response_fn = response_fn
        self.last_system_prompt: Optional[str] = None
        self.last_user_prompt: Optional[str] = None
        self.call_count = 0

    def generate(self, system_prompt: str, user_prompt: str) -> LLMGeneratedFields:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        self.call_count += 1
        if self._response_fn is not None:
            return self._response_fn(system_prompt, user_prompt)
        if self._response is not None:
            return self._response
        return LLMGeneratedFields(
            summary="",
            why_recommended="",
            eligibility_explanation="",
            support_explanation="",
            application_explanation="",
            confirmation_items=[],
        )


def _insufficient_evidence_answer(request: GroundedGenerationRequest) -> GroundedAnswer:
    return GroundedAnswer(
        service_id=request.service_id,
        service_name=request.service_name,
        summary=INSUFFICIENT_EVIDENCE_MESSAGE,
        why_recommended=INSUFFICIENT_EVIDENCE_MESSAGE,
        eligibility_explanation=INSUFFICIENT_EVIDENCE_MESSAGE,
        support_explanation=INSUFFICIENT_EVIDENCE_MESSAGE,
        application_explanation=INSUFFICIENT_EVIDENCE_MESSAGE,
        confirmation_items=list(request.confirmation_needed),
        evidence=[],
        insufficient_information=[f"{label} 정보 없음" for label in SECTION_LABELS_KO.values()],
        safety_notice=SAFETY_NOTICE,
        status=STATUS_INSUFFICIENT_EVIDENCE,
    )


def _append_citation_tags(answer: GroundedAnswer, present_sections) -> GroundedAnswer:
    def tag_for(*sections: str) -> str:
        labels = [SECTION_LABELS_KO[s] for s in sections if s in present_sections]
        if not labels:
            return ""
        return " " + " ".join(f"[근거: {l}]" for l in labels)

    if answer.eligibility_explanation.strip():
        answer.eligibility_explanation += tag_for("target", "criteria")
    if answer.support_explanation.strip():
        answer.support_explanation += tag_for("support")
    if answer.application_explanation.strip():
        answer.application_explanation += tag_for("application")
    return answer


def generate_answer(client: GenerationClient, request: GroundedGenerationRequest) -> GroundedAnswer:
    """Full pipeline for one service_id + one user_question.

    Never calls the retriever or the recommender -- ``request`` must already
    carry everything needed (docs/rag_generation_v1_report.md §4).
    """
    if not has_any_evidence(request.retrieved_documents):
        # §9: insufficient evidence is decided in Python, before Claude runs.
        return _insufficient_evidence_answer(request)

    fields = client.generate(SYSTEM_PROMPT, build_user_prompt(request))

    present_sections = sections_with_evidence(request.retrieved_documents)
    evidence = [
        EvidenceItem(
            section=r.section,
            section_label=SECTION_LABELS_KO[r.section],
            content=r.content,
            service_id=r.service_id,
            score=r.score,
        )
        for r in request.retrieved_documents
    ]

    answer = GroundedAnswer(
        service_id=request.service_id,
        service_name=request.service_name,
        summary=fields.summary,
        why_recommended=fields.why_recommended,
        eligibility_explanation=fields.eligibility_explanation,
        support_explanation=fields.support_explanation,
        application_explanation=fields.application_explanation,
        confirmation_items=list(fields.confirmation_items),
        evidence=evidence,
        insufficient_information=missing_sections_ko(request.retrieved_documents),
        safety_notice=SAFETY_NOTICE,
        status=STATUS_OK,
    )

    # §8: deterministic override, never trust the LLM's own judgment here --
    # applies even if Claude ignored the system prompt and wrote something.
    if "application" not in present_sections:
        answer.application_explanation = NO_APPLICATION_EVIDENCE_MESSAGE

    # §10-E guardrail (UNKNOWN coercion): if the recommender flagged items
    # needing confirmation but Claude dropped them from confirmation_items,
    # backfill with the recommender's own (already-safe, already-Korean)
    # strings verbatim -- never invented text, just not silently lost.
    if not answer.confirmation_items and request.confirmation_needed:
        answer.confirmation_items = list(request.confirmation_needed)

    # §10 enforcement: sanitize every LLM-authored field against the actual
    # evidence text, independent of whether Claude followed instructions.
    evidence_blob = evidence_text_blob(request.retrieved_documents)
    answer = sanitize_answer(answer, evidence_blob)

    # §16: citation tags, computed from retrieved sections, not from
    # anything Claude claims it used.
    answer = _append_citation_tags(answer, present_sections)

    return answer
