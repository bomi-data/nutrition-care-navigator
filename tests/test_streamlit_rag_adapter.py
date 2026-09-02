"""Tests for streamlit_ui.rag_adapter -- the UI <-> Grounded RAG Generation
translation layer. No Streamlit runtime involved; plain function tests plus
the real (session-scoped) vector store/embedder fixtures for the
service-boundary tests.
"""

from recommender.models import (
    DesiredSupport,
    MatchLevel,
    RecommendationResult,
    TriState,
    UserProfile,
)
from rag.generation_models import GroundedAnswer, SAFETY_NOTICE, STATUS_OK
from rag.generator import FakeGenerationClient
from streamlit_ui import rag_adapter as ra


def _result(service_id="WLF00003248", service_name="재가급여", match_level=MatchLevel.HIGH_MATCH):
    return RecommendationResult(
        service_id=service_id,
        service_name=service_name,
        region={"sido": "경기도", "sigungu": "화성시 동탄구", "region_scope": "SIGUNGU"},
        service_type=["home_visit"],
        match_score=76.5,
        match_level=match_level,
        matched_conditions=["거주 지역이 일치해요"],
        unknown_conditions=[],
        exclusion_warnings=[],
        confirmation_needed=["소득 조건 확인 필요"],
        recommendation_reasons=["원하시는 도움과 일치해요"],
        verification_level="A",
        nutritionist_involvement="not_specified",
    )


def _profile(**overrides):
    defaults = dict(
        sido="경기도",
        sigungu="화성시 동탄구",
        age=75,
        has_disability=TriState.UNKNOWN,
        low_income_status=TriState.TRUE,
        lives_alone=TriState.TRUE,
        mobility_difficulty=TriState.TRUE,
        meal_preparation_difficulty=TriState.TRUE,
        recent_discharge=TriState.FALSE,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    defaults.update(overrides)
    return UserProfile(**defaults)


# ---------------------------------------------------------------------------
# format_profile_summary
# ---------------------------------------------------------------------------


def test_format_profile_summary_never_renders_unknown_as_no():
    profile = _profile(has_disability=TriState.UNKNOWN)
    summary = ra.format_profile_summary(profile)
    assert "장애 여부: 확인 필요" in summary
    assert "장애 여부: 아니오" not in summary


def test_format_profile_summary_includes_region_and_age():
    profile = _profile()
    summary = ra.format_profile_summary(profile)
    assert "경기도" in summary
    assert "화성시 동탄구" in summary
    assert "75세" in summary


def test_format_profile_summary_handles_missing_region_and_age():
    profile = _profile(sido=None, sigungu=None, age=None)
    summary = ra.format_profile_summary(profile)
    assert "거주지: 확인 필요" in summary
    assert "연령: 확인 필요" in summary


# ---------------------------------------------------------------------------
# build_generation_request
# ---------------------------------------------------------------------------


def test_build_generation_request_maps_recommendation_result_fields():
    result = _result()
    profile = _profile()
    request = ra.build_generation_request(result, profile, "어떻게 신청하나요?", [])

    assert request.service_id == result.service_id
    assert request.service_name == result.service_name
    assert request.recommendation_level == "HIGH_MATCH"
    assert request.recommendation_reasons == result.recommendation_reasons
    assert request.confirmation_needed == result.confirmation_needed
    assert request.user_question == "어떻게 신청하나요?"


# ---------------------------------------------------------------------------
# Session state keys
# ---------------------------------------------------------------------------


def test_session_keys_are_unique_per_service_id():
    keys_a = {
        ra.answer_session_key("A"),
        ra.pending_question_session_key("A"),
        ra.error_session_key("A"),
        ra.free_text_session_key("A"),
    }
    keys_b = {
        ra.answer_session_key("B"),
        ra.pending_question_session_key("B"),
        ra.error_session_key("B"),
        ra.free_text_session_key("B"),
    }
    assert keys_a.isdisjoint(keys_b)
    assert len(keys_a) == 4  # the 4 kinds of key are distinct from each other too


# ---------------------------------------------------------------------------
# resolve_generation_client
# ---------------------------------------------------------------------------


def test_resolve_generation_client_fake_mode_always_available(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resolved = ra.resolve_generation_client(mode_override="fake")
    assert resolved.mode == "fake"
    assert resolved.is_fake is True
    assert resolved.client is not None


def test_resolve_generation_client_claude_mode_without_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resolved = ra.resolve_generation_client(mode_override="claude")
    assert resolved.mode == "unavailable"
    assert resolved.client is None
    assert resolved.unavailable_reason


def test_resolve_generation_client_claude_mode_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")
    resolved = ra.resolve_generation_client(mode_override="claude")
    assert resolved.mode == "claude"
    assert resolved.is_fake is False
    assert resolved.client is not None


def test_resolve_generation_client_auto_mode_follows_api_key_presence(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    resolved = ra.resolve_generation_client(mode_override="auto")
    assert resolved.mode == "unavailable"

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")
    resolved = ra.resolve_generation_client(mode_override="auto")
    assert resolved.mode == "claude"


def test_resolve_generation_client_reads_env_var_when_no_override(monkeypatch):
    monkeypatch.setenv(ra.GENERATION_MODE_ENV, "fake")
    resolved = ra.resolve_generation_client()
    assert resolved.mode == "fake"


# ---------------------------------------------------------------------------
# run_generation / safe_run_generation -- service boundary + error handling
# ---------------------------------------------------------------------------


def test_run_generation_raises_when_client_unavailable(rag_store, rag_embedder):
    unavailable = ra.ResolvedGenerationClient(client=None, mode="unavailable", is_fake=False, unavailable_reason="no key")
    try:
        ra.run_generation(unavailable, rag_store, rag_embedder, _result(), _profile(), "어떻게 신청하나요?")
        assert False, "expected GenerationUnavailableError"
    except ra.GenerationUnavailableError:
        pass


def test_safe_run_generation_unavailable_returns_reason_not_exception(rag_store, rag_embedder):
    unavailable = ra.ResolvedGenerationClient(client=None, mode="unavailable", is_fake=False, unavailable_reason="설정 안 됨")
    outcome = ra.safe_run_generation(unavailable, rag_store, rag_embedder, _result(), _profile(), "질문")
    assert outcome.answer is None
    assert outcome.unavailable_reason == "설정 안 됨"
    assert outcome.error_message is None


class _ExplodingClient:
    def generate(self, system_prompt, user_prompt):
        raise RuntimeError("secret internal detail sk-should-not-leak")


def test_safe_run_generation_catches_client_errors_without_leaking_details(rag_store, rag_embedder):
    resolved = ra.ResolvedGenerationClient(client=_ExplodingClient(), mode="claude", is_fake=False)
    outcome = ra.safe_run_generation(resolved, rag_store, rag_embedder, _result(), _profile(), "질문")

    assert outcome.answer is None
    assert outcome.error_message is not None
    assert "sk-should-not-leak" not in outcome.error_message
    assert "secret internal detail" not in outcome.error_message


def test_safe_run_generation_service_boundary_two_services_stay_separate(rag_store, rag_embedder):
    fake = FakeGenerationClient(response_fn=ra._default_fake_response)
    resolved = ra.ResolvedGenerationClient(client=fake, mode="fake", is_fake=True)

    result_a = _result(service_id="WLF00003248", service_name="재가급여")
    result_b = _result(service_id="WLF00000664", service_name="노인맞춤돌봄지원 강화 사업")

    outcome_a = ra.safe_run_generation(resolved, rag_store, rag_embedder, result_a, _profile(), "어떤 지원을 받을 수 있나요?")
    outcome_b = ra.safe_run_generation(resolved, rag_store, rag_embedder, result_b, _profile(), "어떤 지원을 받을 수 있나요?")

    assert outcome_a.answer is not None and outcome_b.answer is not None
    assert outcome_a.answer.service_id == "WLF00003248"
    assert outcome_b.answer.service_id == "WLF00000664"
    for e in outcome_a.answer.evidence:
        assert e.service_id == "WLF00003248"
    for e in outcome_b.answer.evidence:
        assert e.service_id == "WLF00000664"


def test_load_rag_resources_returns_usable_store_and_embedder():
    store, embedder = ra.load_rag_resources()
    assert len(store) > 0
    vec = embedder.embed_query("테스트 질문")
    assert vec is not None


# ---------------------------------------------------------------------------
# Display formatting
# ---------------------------------------------------------------------------


def _answer(**overrides) -> GroundedAnswer:
    defaults = dict(
        service_id="WLF00003248",
        service_name="재가급여",
        summary="요약",
        why_recommended="이유",
        eligibility_explanation="",
        support_explanation="지원 설명",
        application_explanation="",
        confirmation_items=["소득 조건 확인 필요"],
        evidence=[],
        insufficient_information=[],
        safety_notice=SAFETY_NOTICE,
        status=STATUS_OK,
    )
    defaults.update(overrides)
    return GroundedAnswer(**defaults)


def test_answer_display_fields_omits_empty_fields_and_keeps_order():
    answer = _answer()
    fields = ra.answer_display_fields(answer)
    labels = [label for label, _ in fields]
    assert labels == ["서비스 요약", "왜 추천되었나요?", "지원 내용"]
    assert "자격 관련 설명" not in labels  # was empty
    assert "신청 방법" not in labels  # was empty


def test_evidence_grouped_by_section_orders_and_filters(rag_store, rag_embedder):
    from rag.generation_models import EvidenceItem

    evidence = [
        EvidenceItem(section="application", section_label="신청방법", content="app text", service_id="X", score=0.5),
        EvidenceItem(section="target", section_label="지원대상", content="target text", service_id="X", score=0.9),
    ]
    grouped = ra.evidence_grouped_by_section(evidence)
    sections = [s for s, _, _ in grouped]
    assert sections == ["target", "application"]  # fixed display order, not insertion order
    assert grouped[0][2] == ["target text"]


def test_evidence_grouped_by_section_empty_when_no_evidence():
    assert ra.evidence_grouped_by_section([]) == []
