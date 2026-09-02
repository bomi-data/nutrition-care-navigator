"""Real Claude API smoke test (instructions §12). Skipped entirely unless
ANTHROPIC_API_KEY is set -- must never fail the suite in an environment
without credentials.
"""

import pytest

from rag.generation_models import GroundedGenerationRequest, STATUS_OK
from rag.generator import ClaudeGenerationClient, api_key_configured, generate_answer
from rag.retriever import retrieve_for_service

pytestmark = pytest.mark.skipif(
    not api_key_configured(), reason="ANTHROPIC_API_KEY not set -- skipping real Claude API smoke test"
)


def test_real_claude_generates_a_grounded_answer(rag_store, rag_embedder, all_services):
    service_id = "WLF00003248"  # 재가급여
    service_name = next(s.service_name for s in all_services if s.service_id == service_id)

    retrieved = retrieve_for_service(rag_store, rag_embedder, service_id, "어떤 지원을 받을 수 있나요?", top_k=3)
    assert retrieved, "expected retrieval to find evidence for a well-covered real service"

    request = GroundedGenerationRequest(
        service_id=service_id,
        service_name=service_name,
        user_profile_summary="75세, 경기도 화성시, 저소득, 독거, 거동불편",
        recommendation_level="POSSIBLE_MATCH",
        recommendation_reasons=["원하시는 도움과 일치해요"],
        confirmation_needed=["소득 조건 확인 필요"],
        user_question="어떤 지원을 받을 수 있나요?",
        retrieved_documents=retrieved,
    )

    client = ClaudeGenerationClient()
    answer = generate_answer(client, request)

    assert answer.status == STATUS_OK
    assert answer.service_id == service_id
    assert answer.support_explanation.strip() != ""
    assert answer.safety_notice
