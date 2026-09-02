"""End-to-end Streamlit UI tests using Streamlit's official AppTest
framework (streamlit.testing.v1) -- runs the real app/streamlit_app.py
script and simulates real widget interactions (select/click/input), without
a browser. Covers instructions §21 A-L.

These are slower than plain function tests (they execute the whole script,
including the cached RAG resource bootstrap on first use) but they are the
only tests in this suite that actually exercise app/streamlit_app.py itself
rather than the adapter functions it calls.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


def _new_app() -> AppTest:
    return AppTest.from_file(APP_PATH)


def _fill_hwaseong_profile(at: AppTest) -> AppTest:
    """75세/경기도 화성시 동탄구/저소득/독거/거동불편/식사준비어려움/식사지원 희망
    -- the same real-user case validated in tests/test_real_case_gyeonggi_hwaseong.py
    and tests/rag/test_generation_integration.py."""
    at.selectbox[0].select("경기도").run(timeout=60)
    at.selectbox[1].select("화성시 동탄구").run(timeout=60)
    at.text_input[0].input("75").run(timeout=60)
    at.radio(key="disability").set_value("아니오").run(timeout=60)
    at.radio(key="low_income").set_value("예").run(timeout=60)
    at.radio(key="lives_alone").set_value("예").run(timeout=60)
    at.radio(key="mobility").set_value("예").run(timeout=60)
    at.radio(key="meal_prep").set_value("예").run(timeout=60)
    at.radio(key="recent_discharge").set_value("아니오").run(timeout=60)
    at.multiselect[0].select("식사/도시락/반찬 지원").run(timeout=60)
    at.button[0].click().run(timeout=60)
    return at


def _fill_food_cost_profile(at: AppTest) -> AppTest:
    """Surfaces WLF00003036 (application_original == '[]' in the real CSV,
    docs/rag_retrieval_v1_report.md §3) as the #1 result -- used for the
    "application info missing" UI check (§21-F)."""
    at.selectbox[0].select("전남광주통합특별시").run(timeout=60)
    at.selectbox[1].select("장성군").run(timeout=60)
    at.text_input[0].input("70").run(timeout=60)
    at.multiselect[0].select("식비/식재료 지원").run(timeout=60)
    at.button[0].click().run(timeout=60)
    return at


def _preset_button_service_ids(at: AppTest) -> list:
    ids = []
    for b in at.button:
        if b.key and b.key.startswith("preset_") and b.key.endswith("_0"):
            ids.append(b.key[len("preset_") : -len("_0")])
    return ids


# ---------------------------------------------------------------------------
# A. 추천 실행만 했을 때 Claude API가 호출되지 않음 (on-demand 원칙)
# ---------------------------------------------------------------------------


def test_A_search_alone_does_not_trigger_generation(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)

    assert list(at.exception) == []
    service_ids = _preset_button_service_ids(at)
    assert service_ids, "expected at least one result card"

    for sid in service_ids:
        with pytest.raises(KeyError):
            _ = at.session_state[f"rag_answer::{sid}"]


# ---------------------------------------------------------------------------
# B/C/D. 서비스별 질문이 서로 섞이지 않음
# ---------------------------------------------------------------------------


def test_BCD_each_service_question_stays_scoped_to_its_own_card(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)

    service_ids = _preset_button_service_ids(at)
    assert len(service_ids) >= 2, "need at least 2 result cards for this test"
    sid1, sid2 = service_ids[0], service_ids[1]

    at.button(key=f"preset_{sid1}_1").click().run(timeout=60)
    assert list(at.exception) == []

    answer1 = at.session_state[f"rag_answer::{sid1}"]
    assert answer1.service_id == sid1
    assert all(e.service_id == sid1 for e in answer1.evidence)
    with pytest.raises(KeyError):
        _ = at.session_state[f"rag_answer::{sid2}"]  # service 2 untouched (B/C)

    at.button(key=f"preset_{sid2}_1").click().run(timeout=60)
    answer1_again = at.session_state[f"rag_answer::{sid1}"]
    answer2 = at.session_state[f"rag_answer::{sid2}"]

    # D: service 1's answer must not have changed or leaked into service 2
    assert answer1_again.service_id == sid1
    assert answer2.service_id == sid2
    assert all(e.service_id == sid2 for e in answer2.evidence)
    assert answer1_again.summary == answer1.summary


# ---------------------------------------------------------------------------
# E. 질문 변경 후 정상 재생성
# ---------------------------------------------------------------------------


def test_E_changing_question_regenerates_for_same_service(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)
    sid = _preset_button_service_ids(at)[0]

    at.button(key=f"preset_{sid}_0").click().run(timeout=60)
    pending_1 = at.session_state[f"rag_pending_question::{sid}"]

    at.button(key=f"preset_{sid}_3").click().run(timeout=60)
    pending_2 = at.session_state[f"rag_pending_question::{sid}"]

    assert pending_1 != pending_2
    assert pending_2 == "어떻게 신청하나요?"
    assert list(at.exception) == []


# ---------------------------------------------------------------------------
# F. application 정보 없는 서비스 처리
# ---------------------------------------------------------------------------


def test_F_missing_application_evidence_shows_fixed_fallback_text(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_food_cost_profile(at)

    service_ids = _preset_button_service_ids(at)
    assert "WLF00003036" in service_ids

    at.button(key="preset_WLF00003036_3").click().run(timeout=60)  # "어떻게 신청하나요?"

    answer = at.session_state["rag_answer::WLF00003036"]
    from rag.generation_models import NO_APPLICATION_EVIDENCE_MESSAGE

    assert answer.application_explanation == NO_APPLICATION_EVIDENCE_MESSAGE


# ---------------------------------------------------------------------------
# G. API Key 없음
# ---------------------------------------------------------------------------


def test_G_no_api_key_shows_info_message_and_does_not_crash(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("RAG_GENERATION_MODE", "claude")  # force real-client path, no fake fallback
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)

    assert list(at.exception) == []
    info_texts = [i.value for i in at.info]
    assert any("AI 기반 설명 기능이 현재 설정되지 않았습니다" in t for t in info_texts)
    # the recommendation itself must still be fully usable
    assert _preset_button_service_ids(at) == []  # no question buttons rendered when unavailable
    assert len(at.markdown) > 0


# ---------------------------------------------------------------------------
# H. Claude API 오류
# ---------------------------------------------------------------------------


class _ExplodingClient:
    def generate(self, system_prompt, user_prompt):
        raise RuntimeError("simulated network failure, should never reach the user")


def test_H_generation_error_is_caught_and_does_not_leak_details(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-fake-key")
    monkeypatch.setenv("RAG_GENERATION_MODE", "claude")

    from streamlit_ui import rag_adapter

    monkeypatch.setattr(rag_adapter, "ClaudeGenerationClient", lambda: _ExplodingClient())

    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)
    sid = _preset_button_service_ids(at)[0]

    at.button(key=f"preset_{sid}_0").click().run(timeout=60)

    assert list(at.exception) == []  # app itself never crashes
    warning_texts = [w.value for w in at.warning]
    assert any("AI 설명을 불러오지 못했습니다" in t for t in warning_texts)
    assert not any("simulated network failure" in t for t in warning_texts)
    assert not any("sk-test-fake-key" in t for t in warning_texts)


# ---------------------------------------------------------------------------
# I. UNKNOWN 입력 (모든 tri-state를 기본값 "잘 모르겠어요"로 둔 채 검색)
# ---------------------------------------------------------------------------


def test_I_all_unknown_input_does_not_crash(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    # deliberately leave every tri-state radio at its default (index=2 == "잘 모르겠어요")
    at.multiselect[0].select("식사/도시락/반찬 지원").run(timeout=60)
    at.button[0].click().run(timeout=60)

    assert list(at.exception) == []
    service_ids = _preset_button_service_ids(at)
    if service_ids:
        sid = service_ids[0]
        at.button(key=f"preset_{sid}_2").click().run(timeout=60)  # "제가 대상일 가능성이 있나요?"
        assert list(at.exception) == []
        answer = at.session_state[f"rag_answer::{sid}"]
        # UNKNOWN must never be coerced into a confirmed statement
        for forbidden in ("신청할 수 있습니다", "지원 대상입니다", "받을 수 있습니다"):
            assert forbidden not in answer.eligibility_explanation


# ---------------------------------------------------------------------------
# J. 자유 질문
# ---------------------------------------------------------------------------


def test_J_free_text_question_is_answered_within_service_boundary(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)
    sid = _preset_button_service_ids(at)[0]

    at.text_input(key=f"rag_free_text::{sid}").input("반찬도 같이 배달되나요?").run(timeout=60)
    at.button(key=f"submit_free_{sid}").click().run(timeout=60)

    assert list(at.exception) == []
    pending = at.session_state[f"rag_pending_question::{sid}"]
    assert pending == "반찬도 같이 배달되나요?"
    answer = at.session_state[f"rag_answer::{sid}"]
    assert answer.service_id == sid


# ---------------------------------------------------------------------------
# K. 페이지 rerun 이후 추천 결과 유지
# ---------------------------------------------------------------------------


def test_K_recommendation_results_survive_an_unrelated_rerun(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)
    service_ids_before = _preset_button_service_ids(at)

    # trigger a rerun unrelated to the search button (typing in a free-text
    # box) -- st.session_state["results"] must not be recomputed/lost.
    sid = service_ids_before[0]
    at.text_input(key=f"rag_free_text::{sid}").input("아무 질문").run(timeout=60)

    service_ids_after = _preset_button_service_ids(at)
    assert service_ids_after == service_ids_before


# ---------------------------------------------------------------------------
# L. 기존 공식 원문 expander 정상 작동
# ---------------------------------------------------------------------------


def test_L_existing_official_text_expander_still_works(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)

    expander_labels = [e.label for e in at.expander]
    assert any("자세히 보기" in label for label in expander_labels)


# ---------------------------------------------------------------------------
# 화성 사례 회귀 테스트 (instructions §20): 1위/match_score/match_level이
# RAG 질문을 실행하기 전후로 정확히 동일해야 하고, 그 1위 서비스에 대해
# "어떤 지원을 받을 수 있나요?" 전체 파이프라인이 연결되는지 확인합니다.
# ---------------------------------------------------------------------------


def test_hwaseong_case_recommendation_unchanged_by_rag_pipeline(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = _new_app()
    at.run(timeout=60)
    at = _fill_hwaseong_profile(at)

    results_before = at.session_state["results"]
    top_before = results_before[0]
    assert top_before.match_level.value == "HIGH_MATCH"  # matches the existing regression test

    sid = top_before.service_id
    at.button(key=f"preset_{sid}_1").click().run(timeout=60)  # "어떤 지원을 받을 수 있나요?"

    results_after = at.session_state["results"]
    top_after = results_after[0]

    assert [(r.service_id, r.match_score, r.match_level) for r in results_before] == [
        (r.service_id, r.match_score, r.match_level) for r in results_after
    ]
    assert top_after.service_id == top_before.service_id
    assert top_after.match_score == top_before.match_score
    assert top_after.match_level == top_before.match_level

    answer = at.session_state[f"rag_answer::{sid}"]
    assert answer.service_id == sid
    assert answer.support_explanation.strip() != ""
