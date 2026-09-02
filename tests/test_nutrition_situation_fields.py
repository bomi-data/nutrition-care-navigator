"""'영양·식생활 상황' UI 보강 작업(신규 필드: frequent_meal_skipping /
grocery_shopping_difficulty / needs_diet_management)에 대한 회귀 테스트.

이 세 필드는 85건 production 데이터에 직접 대응하는 공식 자격조건/서비스
특성 컬럼이 없으므로 matcher/filters/scorer 어디에서도 참조하지 않는다
(recommender/models.py의 UserProfile 필드 주석 참고). 따라서 이 테스트가
확인해야 할 것은 "값이 정상 저장되는가"와 "값이 무엇이든 추천 점수/등급이
전혀 바뀌지 않는가" 두 가지다.
"""

from recommender.models import DesiredSupport, TriState
from recommender.recommender import evaluate_service
from recommender.scorer import compute_score
from recommender.matcher import evaluate_region
from streamlit_ui import adapter

from .conftest import make_service, make_user


# ---------------------------------------------------------------------------
# adapter.build_user_profile: 예/아니요/잘 모르겠어요 3값 모두 정상 저장
# ---------------------------------------------------------------------------


def _build(meal_skipping, grocery_shopping, diet_management):
    return adapter.build_user_profile(
        sido_label="강원특별자치도",
        sigungu_label="속초시",
        age_raw="75",
        disability_answer="잘 모르겠어요",
        low_income_answer="잘 모르겠어요",
        lives_alone_answer="잘 모르겠어요",
        mobility_answer="잘 모르겠어요",
        meal_prep_answer="잘 모르겠어요",
        recent_discharge_answer="잘 모르겠어요",
        desired_support_selected_labels=[],
        meal_skipping_answer=meal_skipping,
        grocery_shopping_answer=grocery_shopping,
        diet_management_answer=diet_management,
    )


def test_new_fields_default_to_unknown_when_not_passed():
    profile = adapter.build_user_profile(
        sido_label="강원특별자치도",
        sigungu_label="속초시",
        age_raw="75",
        disability_answer="잘 모르겠어요",
        low_income_answer="잘 모르겠어요",
        lives_alone_answer="잘 모르겠어요",
        mobility_answer="잘 모르겠어요",
        meal_prep_answer="잘 모르겠어요",
        recent_discharge_answer="잘 모르겠어요",
        desired_support_selected_labels=[],
    )
    assert profile.frequent_meal_skipping is TriState.UNKNOWN
    assert profile.grocery_shopping_difficulty is TriState.UNKNOWN
    assert profile.needs_diet_management is TriState.UNKNOWN


def test_new_fields_store_yes_no_unknown_correctly():
    profile = _build("예", "아니오", "잘 모르겠어요")
    assert profile.frequent_meal_skipping is TriState.TRUE
    assert profile.grocery_shopping_difficulty is TriState.FALSE
    assert profile.needs_diet_management is TriState.UNKNOWN

    profile2 = _build("아니오", "예", "예")
    assert profile2.frequent_meal_skipping is TriState.FALSE
    assert profile2.grocery_shopping_difficulty is TriState.TRUE
    assert profile2.needs_diet_management is TriState.TRUE


# ---------------------------------------------------------------------------
# 결과 화면 요약(nutrition_situation_summary): "예"만 표시, ranking과 무관
# ---------------------------------------------------------------------------


def test_nutrition_situation_summary_lists_only_true_answers():
    profile = _build("예", "예", "아니오")
    summary = adapter.nutrition_situation_summary(profile)
    assert "최근 식사를 자주 거름" in summary
    assert "장보기가 어려움" in summary
    assert "질환 때문에 식사관리가 필요하다고 느낌" not in summary


def test_nutrition_situation_summary_empty_when_nothing_true():
    profile = _build("아니오", "잘 모르겠어요", "아니오")
    assert adapter.nutrition_situation_summary(profile) == []


def test_nutrition_situation_summary_includes_existing_meal_prep_field():
    profile = adapter.build_user_profile(
        sido_label="강원특별자치도",
        sigungu_label="속초시",
        age_raw="75",
        disability_answer="잘 모르겠어요",
        low_income_answer="잘 모르겠어요",
        lives_alone_answer="잘 모르겠어요",
        mobility_answer="잘 모르겠어요",
        meal_prep_answer="예",
        recent_discharge_answer="잘 모르겠어요",
        desired_support_selected_labels=[],
    )
    assert "직접 음식을 준비하기 어려움" in adapter.nutrition_situation_summary(profile)


# ---------------------------------------------------------------------------
# 추천 엔진: 새 필드는 임의 scoring이 없어야 한다 (score/match_level 불변)
# ---------------------------------------------------------------------------


def _score_for(user, service):
    region_check = evaluate_region(user, service)
    return compute_score(user, service, region_check)


def test_new_fields_do_not_change_score_for_any_value_combination():
    service = make_service(service_type=frozenset({"meal_support"}))
    base = make_user(desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}))
    baseline_score = _score_for(base, service)

    combos = [
        (TriState.TRUE, TriState.UNKNOWN, TriState.UNKNOWN),
        (TriState.UNKNOWN, TriState.TRUE, TriState.UNKNOWN),
        (TriState.UNKNOWN, TriState.UNKNOWN, TriState.TRUE),
        (TriState.TRUE, TriState.TRUE, TriState.TRUE),
        (TriState.FALSE, TriState.FALSE, TriState.FALSE),
    ]
    for meal_skip, grocery, diet in combos:
        variant = make_user(
            desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
            frequent_meal_skipping=meal_skip,
            grocery_shopping_difficulty=grocery,
            needs_diet_management=diet,
        )
        variant_score = _score_for(variant, service)
        assert variant_score.achieved == baseline_score.achieved
        assert variant_score.max_possible == baseline_score.max_possible
        assert variant_score.normalized_score == baseline_score.normalized_score


def test_new_fields_do_not_change_recommendation_result_across_all_services(all_services):
    base = make_user(desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}))
    variant = make_user(
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
        frequent_meal_skipping=TriState.TRUE,
        grocery_shopping_difficulty=TriState.TRUE,
        needs_diet_management=TriState.TRUE,
    )

    for service in all_services:
        base_result = evaluate_service(base, service)
        variant_result = evaluate_service(variant, service)
        # hard-exclusion outcome must be identical either way
        assert (base_result is None) == (variant_result is None)
        if base_result is not None:
            assert base_result.match_score == variant_result.match_score
            assert base_result.match_level == variant_result.match_level


def test_meal_preparation_difficulty_field_unaffected_by_new_fields():
    """기존 '식사준비 어려움' 필드(meal_preparation_difficulty)는 문구만
    바뀌었을 뿐, 내부 값과 recommender 연결은 그대로 유지되어야 한다."""
    service = make_service(service_type=frozenset({"meal_support"}))
    user = make_user(
        meal_preparation_difficulty=TriState.TRUE,
        frequent_meal_skipping=TriState.TRUE,
        grocery_shopping_difficulty=TriState.TRUE,
        needs_diet_management=TriState.TRUE,
    )
    score = _score_for(user, service)
    assert score.components["meal_preparation_bonus"] == (10.0, 10.0)
