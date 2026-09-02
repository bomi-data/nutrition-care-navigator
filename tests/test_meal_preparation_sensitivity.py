"""v1.2 fix: meal_preparation_difficulty was a required UserProfile input
with zero code path in matcher/filters/scorer (docs/
recommendation_engine_v1_2_validation.md §meal_prep). Confirmed via `grep`
before the fix -- the field was read nowhere outside models.py.
"""

from recommender.scorer import compute_score
from recommender.matcher import evaluate_region
from recommender.models import TriState

from .conftest import make_service, make_user


def _score_for(user, service):
    region_check = evaluate_region(user, service)
    return compute_score(user, service, region_check)


def test_meal_preparation_true_boosts_a_meal_support_service():
    service = make_service(service_type=frozenset({"meal_support"}))
    user_unknown = make_user(meal_preparation_difficulty=TriState.UNKNOWN)
    user_true = make_user(meal_preparation_difficulty=TriState.TRUE)

    score_unknown = _score_for(user_unknown, service)
    score_true = _score_for(user_true, service)

    assert score_true.achieved > score_unknown.achieved
    assert score_true.components["meal_preparation_bonus"] == (10.0, 10.0)


def test_meal_preparation_false_never_penalizes():
    service = make_service(service_type=frozenset({"meal_support"}))
    user_unknown = make_user(meal_preparation_difficulty=TriState.UNKNOWN)
    user_false = make_user(meal_preparation_difficulty=TriState.FALSE)

    assert _score_for(user_false, service).achieved == _score_for(user_unknown, service).achieved
    assert _score_for(user_false, service).components["meal_preparation_bonus"] == (0.0, 0.0)


def test_meal_preparation_true_does_not_credit_a_non_meal_service():
    service = make_service(service_type=frozenset({"home_visit"}))
    user_true = make_user(meal_preparation_difficulty=TriState.TRUE)
    achieved, max_ = _score_for(user_true, service).components["meal_preparation_bonus"]
    assert achieved == 0.0
    assert max_ == 10.0  # still enters the denominator -- non-meal services score relatively lower


def test_meal_preparation_unknown_never_enters_denominator():
    service = make_service(service_type=frozenset({"meal_support"}))
    user = make_user(meal_preparation_difficulty=TriState.UNKNOWN)
    assert _score_for(user, service).components["meal_preparation_bonus"] == (0.0, 0.0)
