"""Tests for SOFT SCORE computation (recommender.scorer)."""

from recommender.filters import apply_hard_filters
from recommender.matcher import evaluate_region
from recommender.models import DesiredSupport, RegionScope, TriState
from recommender.scorer import compute_score

from .conftest import make_service, make_user


def _score(user, service):
    region_check = evaluate_region(user, service)
    return compute_score(user, service, region_check)


def test_service_type_match_raises_score():
    """F: a service matching the user's desired_support scores higher than
    one that does not, all else being equal."""
    user = make_user(desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}))
    matching = make_service(service_type=frozenset({"meal_support"}))
    non_matching = make_service(service_type=frozenset({"community_care"}))

    assert _score(user, matching).normalized_score > _score(user, non_matching).normalized_score


def test_unsure_desired_support_gives_no_service_type_credit():
    user = make_user(desired_support=frozenset({DesiredSupport.UNSURE}))
    service = make_service(service_type=frozenset({"meal_support"}))
    breakdown = _score(user, service)
    achieved, _max = breakdown.components["service_type_match"]
    assert achieved == 0.0


def test_multi_desired_support_partial_intersection_scores_between_zero_and_full():
    user = make_user(
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT, DesiredSupport.COMMUNITY_CARE})
    )
    partial = make_service(service_type=frozenset({"meal_support"}))
    full = make_service(service_type=frozenset({"meal_support", "community_care"}))
    # "home_visit" is RELATED to community_care (v1.3, see
    # recommendation_ranking_final_tuning_report.md §5) -- an empty
    # service_type is the genuinely "asks for nothing this service offers"
    # case now that home_visit itself earns partial credit here.
    none_ = make_service(service_type=frozenset())

    s_partial = _score(user, partial).components["service_type_match"][0]
    s_full = _score(user, full).components["service_type_match"][0]
    s_none = _score(user, none_).components["service_type_match"][0]
    assert s_none == 0.0 < s_partial < s_full


def test_related_service_type_earns_partial_credit_below_exact_match():
    """v1.3 (docs/recommendation_ranking_final_tuning_report.md §5): a
    RELATED (not exact) service_type match now earns partial credit instead
    of the old hard 0 -- e.g. a home_visit-only service for a community_care
    request, or a discharge_support-only service for a community_care
    request. Credit must stay strictly between "no relation" and "exact
    match", and never touch the max (still capped at
    weights['service_type_match_max'])."""
    user = make_user(desired_support=frozenset({DesiredSupport.COMMUNITY_CARE}))
    exact = make_service(service_type=frozenset({"community_care"}))
    related = make_service(service_type=frozenset({"home_visit"}))
    unrelated = make_service(service_type=frozenset({"meal_support"}))

    exact_achieved, max_ = _score(user, exact).components["service_type_match"]
    related_achieved, related_max = _score(user, related).components["service_type_match"]
    unrelated_achieved, _ = _score(user, unrelated).components["service_type_match"]

    assert unrelated_achieved == 0.0 < related_achieved < exact_achieved == max_ == related_max


def test_meal_support_request_credits_supportive_nutrition_service():
    """A service with no meal_support/food_cost_support tag but
    nutrition_relevance=SUPPORTIVE_NUTRITION (e.g. ENR-CHEONAN-02's
    영양지원 content) is food-adjacent enough to earn RELATED credit for a
    meal_support request, without being counted as an EXACT match."""
    user = make_user(desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}))
    service = make_service(
        service_type=frozenset({"community_care"}),
        nutrition_relevance="SUPPORTIVE_NUTRITION",
    )
    breakdown = _score(user, service)
    achieved, max_ = breakdown.components["service_type_match"]
    assert 0.0 < achieved < max_
    assert breakdown.service_type_intersection == frozenset()
    assert breakdown.service_type_related == frozenset({"meal_support"})


def test_eligibility_gate_unknown_never_receives_positive_score_credit():
    """Anti-gaming: a service with many UNKNOWN soft fields must not score
    higher than one with confirmed matches, and UNKNOWN itself contributes
    exactly 0, never a positive amount."""
    user = make_user(
        lives_alone=TriState.TRUE,
        mobility_difficulty=TriState.TRUE,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    sparse = make_service(
        single_household_required=TriState.UNKNOWN,
        homebound_or_mobility_condition=TriState.UNKNOWN,
    )
    confirmed = make_service(
        single_household_required=TriState.TRUE,
        homebound_or_mobility_condition=TriState.TRUE,
    )
    assert _score(user, sparse).normalized_score < _score(user, confirmed).normalized_score
    sh_achieved, _ = _score(user, sparse).components["single_household"]
    mob_achieved, _ = _score(user, sparse).components["mobility"]
    assert sh_achieved == 0.0
    assert mob_achieved == 0.0


def test_soft_mismatch_is_penalized_but_max_possible_unchanged():
    user = make_user(lives_alone=TriState.FALSE, desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}))
    service = make_service(single_household_required=TriState.TRUE)
    breakdown = _score(user, service)
    assert breakdown.single_household_check.score_signal == -1
    assert breakdown.achieved < breakdown.max_possible


def test_region_precision_bonus_only_for_exact_sigungu_match():
    user_precise = make_user(sido="강원특별자치도", sigungu="속초시")
    user_sido_only = make_user(sido="강원특별자치도", sigungu=None)
    service = make_service(region_scope=RegionScope.SIGUNGU, sido="강원특별자치도", sigungu="속초시")

    precise_score = _score(user_precise, service).components["region_precision"][0]
    broad_score = _score(user_sido_only, service).components["region_precision"][0]
    assert precise_score > broad_score == 0.0


def test_nutrition_bonus_inactive_unless_requested():
    service = make_service(nutritionist_involvement="direct")
    user_without = make_user(desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}))
    user_with = make_user(desired_support=frozenset({DesiredSupport.NUTRITION_COUNSELING}))

    assert _score(user_without, service).components["nutrition_bonus"] == (0.0, 0.0)
    achieved, max_ = _score(user_with, service).components["nutrition_bonus"]
    assert achieved == max_ > 0
