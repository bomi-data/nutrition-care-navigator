import pytest

from rag.generation_models import (
    EvidenceItem,
    GroundedAnswer,
    GroundedGenerationRequest,
    LLMGeneratedFields,
    SAFETY_NOTICE,
    STATUS_OK,
)
from rag.models import RetrievalResult


def test_request_defaults_to_empty_retrieved_documents():
    req = GroundedGenerationRequest(
        service_id="WLF00003248",
        service_name="재가급여",
        user_profile_summary="75세, 경기도 화성시",
        recommendation_level="HIGH_MATCH",
        recommendation_reasons=["원하시는 도움과 일치해요"],
        confirmation_needed=[],
        user_question="이 서비스는 어떤 서비스인가요?",
    )
    assert req.retrieved_documents == []


def test_llm_generated_fields_requires_core_text_fields():
    with pytest.raises(Exception):
        LLMGeneratedFields()  # missing required fields


def test_llm_generated_fields_confirmation_items_defaults_to_empty_list():
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="e",
        support_explanation="su",
        application_explanation="a",
    )
    assert fields.confirmation_items == []


def test_evidence_item_as_dict_has_required_keys():
    item = EvidenceItem(
        section="support",
        section_label="지원내용",
        content="도시락 배달",
        service_id="WLF00003248",
        score=0.9,
    )
    d = item.as_dict()
    for key in ("section", "section_label", "content", "service_id", "score"):
        assert key in d


def test_grounded_answer_as_dict_structure():
    answer = GroundedAnswer(
        service_id="WLF00003248",
        service_name="재가급여",
        summary="요약",
        why_recommended="이유",
        eligibility_explanation="자격 설명",
        support_explanation="지원 설명",
        application_explanation="신청 설명",
        confirmation_items=["소득 조건 확인 필요"],
        evidence=[],
        insufficient_information=[],
        safety_notice=SAFETY_NOTICE,
        status=STATUS_OK,
    )
    d = answer.as_dict()
    for key in (
        "service_id",
        "service_name",
        "summary",
        "why_recommended",
        "eligibility_explanation",
        "support_explanation",
        "application_explanation",
        "confirmation_items",
        "evidence",
        "insufficient_information",
        "safety_notice",
        "status",
    ):
        assert key in d
    assert d["status"] == STATUS_OK
