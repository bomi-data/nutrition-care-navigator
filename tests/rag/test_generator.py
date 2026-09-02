from rag.generation_models import (
    LLMGeneratedFields,
    NO_APPLICATION_EVIDENCE_MESSAGE,
    STATUS_INSUFFICIENT_EVIDENCE,
    STATUS_OK,
    GroundedGenerationRequest,
)
from rag.generator import FakeGenerationClient, api_key_configured, generate_answer
from rag.models import RetrievalResult


def _doc(section, content, service_id="WLF00003248"):
    return RetrievalResult(
        service_id=service_id, service_name="재가급여", section=section, content=content, score=0.9, metadata={}
    )


def _request(**overrides):
    defaults = dict(
        service_id="WLF00003248",
        service_name="재가급여",
        user_profile_summary="75세, 경기도 화성시",
        recommendation_level="HIGH_MATCH",
        recommendation_reasons=["원하시는 도움과 일치해요"],
        confirmation_needed=[],
        user_question="어떻게 신청하나요?",
        retrieved_documents=[],
    )
    defaults.update(overrides)
    return GroundedGenerationRequest(**defaults)


WELL_BEHAVED_FIELDS = LLMGeneratedFields(
    summary="장기요양이 필요한 어르신께 방문 서비스를 제공하는 서비스예요.",
    why_recommended="원하시는 도움과 이 서비스가 일치해요.",
    eligibility_explanation="대상일 가능성이 있어요.",
    support_explanation="방문요양 및 방문목욕을 지원해요.",
    application_explanation="",
    confirmation_items=[],
)


def test_empty_retrieved_documents_returns_insufficient_evidence_without_calling_llm():
    client = FakeGenerationClient(response=WELL_BEHAVED_FIELDS)
    request = _request(retrieved_documents=[])

    answer = generate_answer(client, request)

    assert answer.status == STATUS_INSUFFICIENT_EVIDENCE
    assert client.call_count == 0  # never asked the model to generate anything
    assert answer.evidence == []


def test_well_behaved_generation_returns_ok_status_with_evidence():
    docs = [_doc("target", "65세 이상 노인"), _doc("support", "방문요양 지원")]
    client = FakeGenerationClient(response=WELL_BEHAVED_FIELDS)
    request = _request(retrieved_documents=docs)

    answer = generate_answer(client, request)

    assert answer.status == STATUS_OK
    assert answer.service_id == "WLF00003248"
    assert len(answer.evidence) == 2
    assert client.call_count == 1


def test_citation_tags_reflect_sections_actually_retrieved():
    docs = [_doc("support", "방문요양 지원")]
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="",
        support_explanation="방문요양을 지원해요.",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)
    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert "[근거: 지원내용]" in answer.support_explanation
    assert "[근거:" not in answer.eligibility_explanation  # was left blank, no tag added


def test_no_application_evidence_forces_deterministic_fallback_even_if_llm_invents_one():
    # Adversarial/hallucinating model: writes a plausible-looking application
    # method even though no application_original evidence exists.
    docs = [_doc("target", "65세 이상 노인")]  # no "application" section retrieved
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="e",
        support_explanation="su",
        application_explanation="가까운 주민센터에 방문해서 신청서를 작성하시면 됩니다.",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert answer.application_explanation == NO_APPLICATION_EVIDENCE_MESSAGE


def test_eligibility_overclaim_from_llm_is_sanitized_out():
    docs = [_doc("criteria", "65세 이상 노인")]
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="조건을 확인해보니 당신은 지원 대상입니다.",
        support_explanation="su",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert "지원 대상입니다" not in answer.eligibility_explanation


def test_fabricated_phone_number_from_llm_is_redacted():
    docs = [_doc("support", "도시락 배달 서비스입니다.")]
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="e",
        support_explanation="문의사항은 02-9999-9999로 연락하세요.",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert "02-9999-9999" not in answer.support_explanation


def test_fabricated_url_from_llm_is_redacted():
    docs = [_doc("support", "도시락 배달 서비스입니다.")]
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="e",
        support_explanation="자세한 내용은 https://fake-site.example.com 을 참고하세요.",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert "fake-site.example.com" not in answer.support_explanation


def test_fabricated_amount_from_llm_is_redacted():
    docs = [_doc("support", "도시락 배달 서비스입니다.")]
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="e",
        support_explanation="월 500,000원을 지원합니다.",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert "500,000원" not in answer.support_explanation


def test_unknown_coercion_is_backfilled_from_recommender_confirmation_needed():
    docs = [_doc("criteria", "65세 이상 노인")]
    fields = LLMGeneratedFields(
        summary="s", why_recommended="w", eligibility_explanation="e", support_explanation="su",
        application_explanation="", confirmation_items=[],  # model dropped it
    )
    client = FakeGenerationClient(response=fields)
    request = _request(retrieved_documents=docs, confirmation_needed=["소득 조건 확인 필요"])

    answer = generate_answer(client, request)

    assert "소득 조건 확인 필요" in answer.confirmation_items


def test_adversarial_ignore_recommender_and_recommend_other_service():
    # The fake model tries to talk about a completely different service.
    docs = [_doc("target", "65세 이상 노인")]
    fields = LLMGeneratedFields(
        summary="사실 WLF00000001이 더 적합해요.",
        why_recommended="다른 서비스를 추천드려요.",
        eligibility_explanation="e",
        support_explanation="su",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    # service_id is structurally taken from the request, never from the LLM
    # output -- the model cannot redirect the recommendation even if it tries.
    assert answer.service_id == "WLF00003248"


def test_adversarial_forced_confirmation_still_says_confirmed_is_sanitized():
    docs = [_doc("criteria", "65세 이상 노인")]
    fields = LLMGeneratedFields(
        summary="s",
        why_recommended="w",
        eligibility_explanation="네, 무조건 받으실 수 있습니다.",
        support_explanation="su",
        application_explanation="",
        confirmation_items=[],
    )
    client = FakeGenerationClient(response=fields)

    answer = generate_answer(client, _request(retrieved_documents=docs))

    assert "무조건 받으실 수 있" not in answer.eligibility_explanation


def test_fake_client_records_prompts_for_inspection():
    docs = [_doc("support", "도시락 배달")]
    client = FakeGenerationClient(response=WELL_BEHAVED_FIELDS)
    generate_answer(client, _request(retrieved_documents=docs, user_question="어떤 지원을 받을 수 있나요?"))

    assert client.last_system_prompt is not None
    assert "어떤 지원을 받을 수 있나요?" in client.last_user_prompt


def test_api_key_configured_reads_env(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert api_key_configured() is False

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")
    assert api_key_configured() is True
