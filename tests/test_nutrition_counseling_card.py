"""'영양상담도 함께 확인해보세요' 연결 안내 카드 회귀 테스트.

이 카드는 기존 서비스 추천과 무관한 "안내 노출 여부"만 결정하는 UI
기능이다 -- recommender ranking/match_level에는 전혀 관여하지 않는다
(streamlit_ui/adapter.py의 nutrition_counseling_suggested 참고). 이 파일은
1) adapter의 트리거 판단 함수, 2) 실제 앱에서 카드가 뜨는 조건과 문구,
3) 카드 노출 여부와 무관하게 기존 서비스 추천 결과가 동일하게 유지되는지를
확인한다.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from recommender.models import TriState
from streamlit_ui import adapter

from .conftest import make_user

APP_PATH = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


# ---------------------------------------------------------------------------
# adapter.nutrition_counseling_suggested -- 순수 함수 단위 테스트
# ---------------------------------------------------------------------------


def test_suggested_false_when_all_unknown():
    user = make_user()
    assert adapter.nutrition_counseling_suggested(user) is False


@pytest.mark.parametrize(
    "field",
    [
        "frequent_meal_skipping",
        "grocery_shopping_difficulty",
        "meal_preparation_difficulty",
        "needs_diet_management",
    ],
)
def test_suggested_true_when_any_single_field_is_true(field):
    user = make_user(**{field: TriState.TRUE})
    assert adapter.nutrition_counseling_suggested(user) is True


def test_suggested_false_when_all_false():
    user = make_user(
        frequent_meal_skipping=TriState.FALSE,
        grocery_shopping_difficulty=TriState.FALSE,
        meal_preparation_difficulty=TriState.FALSE,
        needs_diet_management=TriState.FALSE,
    )
    assert adapter.nutrition_counseling_suggested(user) is False


# ---------------------------------------------------------------------------
# 앱 레벨 시나리오: 75세, 4개 항목 모두 "예"
# ---------------------------------------------------------------------------


def _fill_hwaseong_profile_all_nutrition_difficulties(at: AppTest) -> AppTest:
    at.selectbox[0].select("경기도").run(timeout=60)
    at.selectbox[1].select("화성시 동탄구").run(timeout=60)
    at.text_input[0].input("75").run(timeout=60)
    at.radio(key="meal_skipping").set_value("예").run(timeout=60)
    at.radio(key="grocery_shopping").set_value("예").run(timeout=60)
    at.radio(key="meal_prep").set_value("예").run(timeout=60)
    at.radio(key="diet_management").set_value("예").run(timeout=60)
    at.radio(key="disability").set_value("아니오").run(timeout=60)
    at.radio(key="low_income").set_value("예").run(timeout=60)
    at.radio(key="lives_alone").set_value("예").run(timeout=60)
    at.radio(key="mobility").set_value("예").run(timeout=60)
    at.radio(key="recent_discharge").set_value("아니오").run(timeout=60)
    at.multiselect[0].select("식사/도시락/반찬 지원").run(timeout=60)
    at.button[0].click().run(timeout=60)
    return at


def test_card_appears_with_expected_texts_when_all_four_answers_are_yes(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=60)
    at = _fill_hwaseong_profile_all_nutrition_difficulties(at)

    assert list(at.exception) == []

    all_text = "\n".join(m.value for m in at.markdown) + "\n" + "\n".join(c.value for c in at.caption)

    assert "영양상담도 함께 확인해보세요" in all_text
    assert "식생활 어려움 확인" in all_text
    assert "영양상담 필요 가능성 안내" in all_text
    assert "우리동네 보건소" in all_text
    assert "영양상담" in all_text

    # 사용자가 "예"라고 답한 4개 항목이 자연스러운 한국어 문구로 모두 표시됨
    assert "최근 식사를 자주 거름" in all_text
    assert "장보기가 어려움" in all_text
    assert "직접 음식을 준비하기 어려움" in all_text
    assert "질환 때문에 식사관리가 필요하다고 느낌" in all_text

    # 내부 필드명이 그대로 노출되지 않음
    for internal_name in (
        "frequent_meal_skipping",
        "grocery_shopping_difficulty",
        "needs_diet_management",
        "meal_preparation_difficulty",
    ):
        assert internal_name not in all_text

    # 금지된 단정적/진단적 표현이 전혀 쓰이지 않음
    for forbidden in (
        "영양상담이 필요합니다",
        "영양위험군입니다",
        "영양불량 위험이 있습니다",
        "전문가 상담이 필요합니다",
        "질환별 영양관리가 필요합니다",
        "영양불량",
        "영양위험군",
    ):
        assert forbidden not in all_text


def test_card_absent_when_no_nutrition_difficulty_reported(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")
    at = AppTest.from_file(APP_PATH)
    at.run(timeout=60)
    at.selectbox[0].select("경기도").run(timeout=60)
    at.selectbox[1].select("화성시 동탄구").run(timeout=60)
    at.text_input[0].input("75").run(timeout=60)
    at.radio(key="low_income").set_value("예").run(timeout=60)
    at.multiselect[0].select("식사/도시락/반찬 지원").run(timeout=60)
    at.button[0].click().run(timeout=60)

    assert list(at.exception) == []
    all_text = "\n".join(m.value for m in at.markdown)
    assert "영양상담도 함께 확인해보세요" not in all_text


# ---------------------------------------------------------------------------
# 기존 서비스 추천 결과는 카드 노출 여부와 무관하게 동일해야 한다
# ---------------------------------------------------------------------------


def _fill_hwaseong_profile_baseline(at: AppTest) -> AppTest:
    """_fill_hwaseong_profile_all_nutrition_difficulties와 동일하되, 새로
    추가된 3개 필드(meal_skipping/grocery_shopping/diet_management)만
    기본값(잘 모르겠어요/UNKNOWN)으로 남겨둔다 -- 그래야 두 프로필의 차이가
    신규 필드에만 있고, 기존 필드(meal_prep 등)는 완전히 동일하게 유지된다.
    """
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
    return at


def test_existing_recommendation_results_unchanged_by_the_new_card(monkeypatch):
    monkeypatch.setenv("RAG_GENERATION_MODE", "fake")

    at_without = AppTest.from_file(APP_PATH)
    at_without.run(timeout=60)
    at_without = _fill_hwaseong_profile_baseline(at_without)
    results_without = at_without.session_state["results"]

    at_with = AppTest.from_file(APP_PATH)
    at_with.run(timeout=60)
    at_with = _fill_hwaseong_profile_all_nutrition_difficulties(at_with)
    results_with = at_with.session_state["results"]

    assert [(r.service_id, r.match_score, r.match_level) for r in results_without] == [
        (r.service_id, r.match_score, r.match_level) for r in results_with
    ]
