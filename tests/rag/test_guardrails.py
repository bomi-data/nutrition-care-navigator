from rag.generation_models import GroundedAnswer, GroundedGenerationRequest, LLMGeneratedFields, SAFETY_NOTICE, STATUS_OK
from rag.guardrails import (
    check_groundedness,
    find_overclaim_phrases,
    find_unsupported_amounts,
    find_unsupported_contacts,
    missing_sections_ko,
    sanitize_answer,
    sanitize_text,
    sections_with_evidence,
)
from rag.models import RetrievalResult


def _doc(section, content, service_id="WLF00003248"):
    return RetrievalResult(
        service_id=service_id, service_name="재가급여", section=section, content=content, score=0.9, metadata={}
    )


def test_sections_with_evidence():
    docs = [_doc("target", "..."), _doc("support", "...")]
    assert sections_with_evidence(docs) == {"target", "support"}


def test_missing_sections_ko_lists_absent_sections_in_korean():
    docs = [_doc("target", "...")]
    missing = missing_sections_ko(docs)
    assert "선정기준 정보 없음" in missing
    assert "지원내용 정보 없음" in missing
    assert "신청방법 정보 없음" in missing
    assert "지원대상 정보 없음" not in missing


def test_missing_sections_ko_empty_when_all_present():
    docs = [_doc(s, "...") for s in ("target", "criteria", "support", "application")]
    assert missing_sections_ko(docs) == []


def test_find_overclaim_phrases_detects_banned_wording():
    assert "지원 대상입니다" in find_overclaim_phrases("이 서비스는 지원 대상입니다.")
    assert find_overclaim_phrases("관련 조건이 확인돼요.") == []


def test_find_unsupported_contacts_flags_phone_not_in_evidence():
    text = "문의는 02-9999-9999로 하세요."
    evidence = "이 서비스의 지원내용은 도시락 배달입니다."
    found = find_unsupported_contacts(text, evidence)
    assert found  # the phone number is not grounded in evidence


def test_find_unsupported_contacts_allows_phone_present_in_evidence():
    text = "문의는 033-640-2745로 하세요."
    evidence = "문의처: 속초시 사회복지과 033-640-2745"
    assert find_unsupported_contacts(text, evidence) == []


def test_find_unsupported_contacts_flags_url_not_in_evidence():
    text = "자세한 내용은 https://fake-welfare-site.example.com 참고하세요."
    evidence = "도시락 배달 서비스입니다."
    assert find_unsupported_contacts(text, evidence)


def test_find_unsupported_amounts_flags_money_not_in_evidence():
    text = "월 500,000원을 지원합니다."
    evidence = "도시락 배달 서비스입니다."
    assert find_unsupported_amounts(text, evidence)


def test_find_unsupported_amounts_allows_amount_present_in_evidence():
    text = "1식 9,000원 배달비 포함으로 지원됩니다."
    evidence = "무료 영양음식 조리·배달 / 1식 9,000원 배달비 포함"
    assert find_unsupported_amounts(text, evidence) == []


def _request(confirmation_needed=None, retrieved_documents=None):
    return GroundedGenerationRequest(
        service_id="WLF00003248",
        service_name="재가급여",
        user_profile_summary="75세",
        recommendation_level="HIGH_MATCH",
        recommendation_reasons=["일치해요"],
        confirmation_needed=confirmation_needed or [],
        user_question="신청 조건이 무엇인가요?",
        retrieved_documents=retrieved_documents or [],
    )


def test_check_groundedness_flags_all_categories():
    request = _request(
        confirmation_needed=["소득 조건 확인 필요"],
        retrieved_documents=[_doc("criteria", "65세 이상 노인")],  # no application evidence
    )
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="지원 대상입니다.",
        support_explanation="문의는 02-1234-5678로, 월 300,000원 지원됩니다.",
        application_explanation="주민센터에 방문 신청하세요.",  # fabricated: no application evidence
        confirmation_items=[],  # dropped confirmation_needed
    )
    report = check_groundedness(fields, request)
    assert report.eligibility_overclaim_phrases
    assert report.fabricated_application is True
    assert report.fabricated_contacts
    assert report.unsupported_amounts
    assert report.unknown_coercion is True
    assert report.passed is False


def test_check_groundedness_passes_for_clean_grounded_fields():
    request = _request(
        confirmation_needed=[],
        retrieved_documents=[_doc("support", "1식 9,000원 배달비 포함")],
    )
    fields = LLMGeneratedFields(
        summary="식사를 배달해주는 서비스예요.",
        why_recommended="원하시는 도움과 일치해요.",
        eligibility_explanation="대상일 가능성이 있어요.",
        support_explanation="1식 9,000원 배달비 포함으로 지원돼요.",
        application_explanation="",
        confirmation_items=[],
    )
    report = check_groundedness(fields, request)
    assert report.passed is True


def test_sanitize_text_replaces_overclaim_phrase():
    cleaned = sanitize_text("당신은 지원 대상입니다.", "무관한 근거 텍스트")
    assert "지원 대상입니다" not in cleaned
    assert "대상일 가능성이 있어요" in cleaned


def test_sanitize_text_redacts_unsupported_phone():
    cleaned = sanitize_text("문의: 02-9999-9999", "이 서비스는 도시락 배달입니다.")
    assert "02-9999-9999" not in cleaned
    assert "[출처 확인 필요]" in cleaned


def test_sanitize_text_keeps_phone_supported_by_evidence():
    cleaned = sanitize_text("문의: 033-640-2745", "문의처: 033-640-2745")
    assert "033-640-2745" in cleaned


def test_sanitize_answer_cleans_every_llm_field():
    evidence = "이 서비스는 도시락 배달입니다."
    answer = GroundedAnswer(
        service_id="WLF00003248",
        service_name="재가급여",
        summary="지원 대상입니다.",
        why_recommended="받을 수 있습니다.",
        eligibility_explanation="신청할 수 있습니다.",
        support_explanation="문의: 02-9999-9999",
        application_explanation="",
        confirmation_items=["지원 대상입니다."],
        evidence=[],
        insufficient_information=[],
        safety_notice=SAFETY_NOTICE,
        status=STATUS_OK,
    )
    sanitize_answer(answer, evidence)
    for text in (
        answer.summary,
        answer.why_recommended,
        answer.eligibility_explanation,
        answer.support_explanation,
        *answer.confirmation_items,
    ):
        assert "지원 대상입니다" not in text
        assert "받을 수 있습니다" not in text
        assert "신청할 수 있습니다" not in text
    assert "02-9999-9999" not in answer.support_explanation
