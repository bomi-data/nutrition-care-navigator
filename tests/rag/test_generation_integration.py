"""End-to-end Generation test against the real recommender + real RAG
retrieval, reusing the same 화성시 real-user profile validated in
tests/test_real_case_gyeonggi_hwaseong.py. Uses FakeGenerationClient (no
network) -- see tests/rag/test_generation_smoke.py for the real-API check.
"""

from recommender.models import DesiredSupport, MatchLevel, TriState, UserProfile
from recommender.recommender import recommend

from rag.generation_models import LLMGeneratedFields, STATUS_OK
from rag.generator import FakeGenerationClient, generate_answer
from rag.generation_models import GroundedGenerationRequest
from rag.retriever import retrieve_for_service

PROFILE = UserProfile(
    sido="경기도",
    sigungu="화성시 동탄구",
    age=75,
    has_disability=TriState.FALSE,
    low_income_status=TriState.TRUE,
    lives_alone=TriState.TRUE,
    mobility_difficulty=TriState.TRUE,
    meal_preparation_difficulty=TriState.TRUE,
    recent_discharge=TriState.FALSE,
    desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
)


def _profile_summary() -> str:
    return (
        "75세, 경기도 화성시 동탄구 거주, 장애 없음, 저소득, 독거, 거동불편, "
        "식사준비 어려움, 최근 퇴원 없음, 희망 도움: 식사/반찬 지원"
    )


def _well_behaved_fake_client() -> FakeGenerationClient:
    def respond(system_prompt: str, user_prompt: str) -> LLMGeneratedFields:
        return LLMGeneratedFields(
            summary="어르신께 식사를 지원하는 서비스예요.",
            why_recommended="원하시는 식사 지원과 이 서비스가 일치해요.",
            eligibility_explanation="관련 조건이 CONTEXT에서 확인돼요. 확정은 아니며 추가 확인이 필요해요.",
            support_explanation="CONTEXT에 나온 지원 내용을 그대로 안내드려요.",
            application_explanation="",
            confirmation_items=[],
        )

    return FakeGenerationClient(response_fn=respond)


def test_hwaseong_case_generation_does_not_change_recommendation(all_services, rag_store, rag_embedder):
    before = recommend(PROFILE, services=all_services, top_k=5)
    assert before, "expected at least one surviving candidate"
    top_before = before[0]

    retrieved = retrieve_for_service(rag_store, rag_embedder, top_before.service_id, "왜 추천되었나요?")
    request = GroundedGenerationRequest(
        service_id=top_before.service_id,
        service_name=top_before.service_name,
        user_profile_summary=_profile_summary(),
        recommendation_level=top_before.match_level.value,
        recommendation_reasons=top_before.recommendation_reasons,
        confirmation_needed=top_before.confirmation_needed,
        user_question="왜 추천되었나요?",
        retrieved_documents=retrieved,
    )

    client = _well_behaved_fake_client()
    answer = generate_answer(client, request)

    after = recommend(PROFILE, services=all_services, top_k=5)
    assert [(r.service_id, r.match_score, r.match_level) for r in before] == [
        (r.service_id, r.match_score, r.match_level) for r in after
    ], "generation must never mutate or influence recommender output"

    assert answer.service_id == top_before.service_id
    assert answer.status == STATUS_OK
    assert answer.evidence  # some official-source evidence was found
    assert top_before.match_level is MatchLevel.HIGH_MATCH  # unchanged from the existing regression test


def test_hwaseong_case_can_answer_what_and_what_to_confirm(all_services, rag_store, rag_embedder):
    results = recommend(PROFILE, services=all_services, top_k=1)
    top = results[0]
    client = _well_behaved_fake_client()

    for question in ("무엇을 지원하나요?", "어떤 부분을 확인해야 하나요?"):
        retrieved = retrieve_for_service(rag_store, rag_embedder, top.service_id, question)
        request = GroundedGenerationRequest(
            service_id=top.service_id,
            service_name=top.service_name,
            user_profile_summary=_profile_summary(),
            recommendation_level=top.match_level.value,
            recommendation_reasons=top.recommendation_reasons,
            confirmation_needed=top.confirmation_needed,
            user_question=question,
            retrieved_documents=retrieved,
        )
        answer = generate_answer(client, request)
        assert answer.service_id == top.service_id
        assert answer.safety_notice
