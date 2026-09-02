"""UI 문구 정리 회귀 테스트: 사용자 화면에 내부 변수명/CSV 필드명이 그대로
노출되지 않는지 확인한다. recommender.py의 값/로직은 건드리지 않았으므로,
추천 결과(service_id/match_score/match_level)는 이 변경 전후로 완전히
동일해야 한다 -- 이는 tests/test_real_case_gyeonggi_hwaseong.py 등 기존
회귀 테스트가 이미 그대로 통과하는 것으로 보장된다.
"""

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from recommender.models import UserProfile
from recommender.recommender import evaluate_service
from streamlit_ui import adapter

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")

# app.py가 실제로 화면에 내보낼 수 있는 원시 내부 토큰들 -- 이 토큰들이
# adapter.humanize_internal_tokens()를 거치지 않은 채로 화면에 그대로
# 남아있으면 안 된다.
_RAW_TOKENS_MUST_NOT_APPEAR = [
    "meal_support",
    "food_cost_support",
    "nutrition_counseling",
    "home_visit",
    "community_care",
    "discharge_support",
    "target_original",
    "criteria_original",
    "support_original",
    "application_original",
]


# ---------------------------------------------------------------------------
# adapter.humanize_internal_tokens -- 순수 함수 단위 테스트
# ---------------------------------------------------------------------------


def test_humanize_replaces_service_type_tag_with_existing_ui_label():
    text = "원하시는 도움(meal_support)과 이 서비스의 제공 내용이 일치해요."
    result = adapter.humanize_internal_tokens(text)
    assert "meal_support" not in result
    # "④ 서비스 유형"/"원하는 도움"에서 이미 쓰는 것과 동일한 라벨을 재사용
    assert adapter.service_type_tag_label("meal_support") in result


def test_humanize_replaces_multiple_tags_in_one_sentence():
    text = "원하시는 도움(food_cost_support, meal_support)과 완전히 같지는 않지만 관련이 있는 지원을 제공해요."
    result = adapter.humanize_internal_tokens(text)
    assert "food_cost_support" not in result
    assert "meal_support" not in result


def test_humanize_replaces_original_field_names_even_with_attached_korean_particle():
    """실제 production data_quality_note(WLF00001291)에 있는 문장과 동일한
    패턴: 한국어 조사가 영문 토큰 바로 뒤에 붙어 있어도 치환되어야 한다."""
    text = "데이터 참고사항: target_original과 criteria_original이 완전히 동일한 문장."
    result = adapter.humanize_internal_tokens(text)
    assert "target_original" not in result
    assert "criteria_original" not in result
    assert "지원 대상 원문" in result
    assert "선정 기준 원문" in result


def test_humanize_leaves_ambiguous_unknown_tokens_untouched():
    """매핑에 없는 내부 key(예: eligibility_summary)는 임의로 번역하지 않고
    그대로 둔다."""
    text = "criteria_original/eligibility_summary에 텍스트로만 보존됨"
    result = adapter.humanize_internal_tokens(text)
    assert "eligibility_summary" in result  # untouched, not guessed at
    assert "criteria_original" not in result


def test_humanize_is_a_no_op_on_plain_korean_text():
    text = "장애 조건에 해당하는 것으로 보여요."
    assert adapter.humanize_internal_tokens(text) == text


def test_humanize_handles_empty_string():
    assert adapter.humanize_internal_tokens("") == ""


# ---------------------------------------------------------------------------
# 앱 레벨 최종 검수 (§7): 실제 화면에 raw 토큰이 전혀 남아있지 않아야 한다
# ---------------------------------------------------------------------------


def _all_rendered_text(at: AppTest) -> str:
    chunks = []
    chunks += [m.value for m in at.markdown]
    chunks += [c.value for c in at.caption]
    chunks += [i.value for i in at.info]
    chunks += [w.value for w in at.warning]
    return "\n".join(chunks)


def test_no_raw_internal_tokens_in_rendered_screen_for_hwaseong_case(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=60)
    at.selectbox[0].select("경기도").run(timeout=60)
    at.selectbox[1].select("화성시 동탄구").run(timeout=60)
    at.text_input[0].input("75").run(timeout=60)
    at.radio(key="meal_prep").set_value("예").run(timeout=60)
    at.radio(key="disability").set_value("아니오").run(timeout=60)
    at.radio(key="low_income").set_value("예").run(timeout=60)
    at.radio(key="lives_alone").set_value("예").run(timeout=60)
    at.radio(key="mobility").set_value("예").run(timeout=60)
    at.radio(key="recent_discharge").set_value("아니오").run(timeout=60)
    at.multiselect[0].select("식사/도시락/반찬 지원").run(timeout=60)
    at.button[0].click().run(timeout=60)

    assert list(at.exception) == []
    text = _all_rendered_text(at)
    for token in _RAW_TOKENS_MUST_NOT_APPEAR:
        assert token not in text, f"raw internal token leaked to UI: {token}"


# ---------------------------------------------------------------------------
# 전체 85건 서비스 전수 점검 (§2/§7): recommender가 생성하는 5개 설명
# 문자열 목록(matched_conditions/unknown_conditions/exclusion_warnings/
# confirmation_needed/recommendation_reasons) 전체를 대상으로, humanize 이후
# "snake_case로 보이는 영문 토큰"이 남아있는지 광범위하게 훑는다. 이미 알려진
# (의미가 불분명해 일부러 손대지 않은) provenance 메모 조각만 남아있어야
# 한다 -- 새로운 leak이 생기면 이 테스트가 실패한다.
# ---------------------------------------------------------------------------

_SNAKE_CASE_TOKEN_PATTERN = re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b")

# ENR-CHEONAN-01/02의 data_quality_note에만 있는, 의미가 불분명한 내부 감사
# 메모(provenance key=value) 조각. 이번 작업에서 임의로 번역하지 않고 그대로
# 두기로 한 항목 -- 최종 보고에서 사용자에게 별도로 알린다.
_KNOWN_AMBIGUOUS_RESIDUAL_TOKENS = {
    "official_url",
    "source_verified_by",
    "user_manual_check",
    "verified_at",
    "source_note",
    "manual_source_check_required",
    "nutrition_relevance",
    "special_eligibility_required",
}


def test_only_known_ambiguous_tokens_remain_across_all_85_services(all_services):
    profile = UserProfile()  # 지역/연령/자격 전부 UNKNOWN -> 85건 전부 하드필터 통과
    unexpected: dict = {}

    for service in all_services:
        result = evaluate_service(profile, service)
        if result is None:
            continue
        texts = (
            list(result.matched_conditions)
            + list(result.unknown_conditions)
            + list(result.exclusion_warnings)
            + list(result.confirmation_needed)
            + list(result.recommendation_reasons)
        )
        for text in texts:
            cleaned = adapter.humanize_internal_tokens(text)
            for token in _SNAKE_CASE_TOKEN_PATTERN.findall(cleaned):
                if token not in _KNOWN_AMBIGUOUS_RESIDUAL_TOKENS:
                    unexpected.setdefault(token, []).append(service.service_id)

    assert not unexpected, f"unexpected raw internal token(s) leaked to UI: {unexpected}"


def test_no_raw_internal_tokens_when_food_cost_support_and_nutrition_selected(monkeypatch):
    """target_original/criteria_original이 완전히 동일한 데이터 품질 메모를
    가진 실제 서비스(WLF00001291)가 결과에 섞여 나올 수 있는 폭넓은 검색
    조건으로, 참고 사항(exclusion_warnings) 경로까지 함께 점검한다."""
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=60)
    at.multiselect[0].select("식비/식재료 지원").run(timeout=60)
    at.multiselect[0].select("영양상담").run(timeout=60)
    at.button[0].click().run(timeout=60)

    assert list(at.exception) == []
    text = _all_rendered_text(at)
    for token in _RAW_TOKENS_MUST_NOT_APPEAR:
        assert token not in text, f"raw internal token leaked to UI: {token}"
