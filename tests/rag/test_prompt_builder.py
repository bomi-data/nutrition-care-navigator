from rag.generation_models import GroundedGenerationRequest
from rag.models import RetrievalResult
from rag.prompt_builder import SYSTEM_PROMPT, build_user_prompt


def _request(retrieved_documents=None, **overrides):
    defaults = dict(
        service_id="WLF00003248",
        service_name="재가급여",
        user_profile_summary="75세, 경기도 화성시, 저소득, 독거, 거동불편, 식사준비 어려움",
        recommendation_level="HIGH_MATCH",
        recommendation_reasons=["원하시는 도움(meal_support)과 이 서비스가 일치해요"],
        confirmation_needed=["소득 조건 확인 필요"],
        user_question="어떻게 신청하나요?",
    )
    defaults.update(overrides)
    return GroundedGenerationRequest(retrieved_documents=retrieved_documents or [], **defaults)


def test_system_prompt_bans_eligibility_confirmation_phrases():
    for phrase in ("신청할 수 있습니다", "지원 대상입니다", "받을 수 있습니다"):
        assert phrase in SYSTEM_PROMPT


def test_system_prompt_forbids_inventing_contact_and_amounts():
    assert "전화번호" in SYSTEM_PROMPT
    assert "URL" in SYSTEM_PROMPT
    assert "지원금액" in SYSTEM_PROMPT


def test_system_prompt_forbids_changing_recommendation_level():
    assert "recommendation_level" in SYSTEM_PROMPT


def test_user_prompt_includes_service_and_question():
    req = _request()
    prompt = build_user_prompt(req)
    assert "WLF00003248" in prompt
    assert "재가급여" in prompt
    assert "어떻게 신청하나요?" in prompt
    assert "HIGH_MATCH" in prompt


def test_user_prompt_marks_missing_sections_explicitly():
    docs = [
        RetrievalResult(
            service_id="WLF00003248",
            service_name="재가급여",
            section="support",
            content="장기요양요원이 방문하여 서비스를 제공합니다.",
            score=0.9,
            metadata={},
        )
    ]
    req = _request(retrieved_documents=docs)
    prompt = build_user_prompt(req)
    assert "[지원내용]" in prompt
    assert "장기요양요원이 방문하여" in prompt
    # sections with no retrieved evidence must say so explicitly, not be silent
    assert "[지원대상] 근거 없음" in prompt
    assert "[선정기준] 근거 없음" in prompt
    assert "[신청방법] 근거 없음" in prompt


def test_user_prompt_includes_recommendation_reasons_and_confirmation_needed():
    req = _request()
    prompt = build_user_prompt(req)
    assert "원하시는 도움(meal_support)과 이 서비스가 일치해요" in prompt
    assert "소득 조건 확인 필요" in prompt
