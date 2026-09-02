"""Tests for the pure comparison functions in recommender.matcher.

Covers: (A) the full 3x3 MATCH/MISMATCH/UNKNOWN matrix, (B) NATIONAL/SIDO/
SIGUNGU region rules, (C) age SIMPLE_MIN / COMPOUND handling.
"""

import pytest

from recommender.matcher import (
    evaluate_age,
    evaluate_region,
    evaluate_tristate,
    is_age_compound_uncertain,
    region_needs_sigungu_confirmation,
)
from recommender.models import AgeConditionType, MatchStatus, RegionScope, TriState

from .conftest import make_service, make_user

T, F, U = TriState.TRUE, TriState.FALSE, TriState.UNKNOWN


# ---------------------------------------------------------------------------
# A. Full 3x3 matrix (rules_spec.md §5)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "service_value,user_value,expected_status,expected_confirm",
    [
        (T, T, MatchStatus.MATCH, False),
        (T, F, MatchStatus.MISMATCH, False),
        (T, U, MatchStatus.UNKNOWN, True),
        (F, T, MatchStatus.MATCH, False),
        (F, F, MatchStatus.MATCH, False),
        (F, U, MatchStatus.MATCH, False),
        (U, T, MatchStatus.UNKNOWN, False),
        (U, F, MatchStatus.UNKNOWN, False),
        (U, U, MatchStatus.UNKNOWN, False),
    ],
)
def test_tristate_matrix(service_value, user_value, expected_status, expected_confirm):
    check = evaluate_tristate("field", service_value, user_value, field_label_ko="테스트")
    assert check.status is expected_status
    assert check.confirmation_needed is expected_confirm
    assert check.reason  # always carries a human-readable reason


def test_service_unknown_never_becomes_mismatch():
    """A service that never states a condition must never look like an
    active disqualifier, no matter what the user answers."""
    for user_value in (T, F, U):
        check = evaluate_tristate("field", U, user_value, field_label_ko="테스트")
        assert check.status is not MatchStatus.MISMATCH


def test_user_unknown_never_becomes_mismatch():
    """UNKNOWN must never be silently treated as FALSE."""
    for service_value in (T, F, U):
        check = evaluate_tristate("field", service_value, U, field_label_ko="테스트")
        assert check.status is not MatchStatus.MISMATCH


def test_score_signal_only_positive_on_true_true():
    assert evaluate_tristate("f", T, T, field_label_ko="x").score_signal == 1
    assert evaluate_tristate("f", T, F, field_label_ko="x").score_signal == -1
    for sv, uv in [(T, U), (F, T), (F, F), (F, U), (U, T), (U, F), (U, U)]:
        assert evaluate_tristate("f", sv, uv, field_label_ko="x").score_signal == 0


# ---------------------------------------------------------------------------
# B. Region rules
# ---------------------------------------------------------------------------


def test_region_national_never_excludes_even_with_no_user_region():
    service = make_service(region_scope=RegionScope.NATIONAL, sido=None, sigungu=None)
    user = make_user(sido=None, sigungu=None)
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.MATCH


def test_region_sido_match():
    service = make_service(region_scope=RegionScope.SIDO, sido="경기도", sigungu=None)
    user = make_user(sido="경기도", sigungu=None)
    assert evaluate_region(user, service).status is MatchStatus.MATCH


def test_region_sido_mismatch_excludable():
    service = make_service(region_scope=RegionScope.SIDO, sido="경기도", sigungu=None)
    user = make_user(sido="서울특별시", sigungu=None)
    assert evaluate_region(user, service).status is MatchStatus.MISMATCH


def test_region_sido_user_missing_is_unknown_not_excluded():
    service = make_service(region_scope=RegionScope.SIDO, sido="경기도", sigungu=None)
    user = make_user(sido=None, sigungu=None)
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.UNKNOWN
    assert check.confirmation_needed is True


def test_region_sigungu_exact_match():
    service = make_service(region_scope=RegionScope.SIGUNGU, sido="강원특별자치도", sigungu="속초시")
    user = make_user(sido="강원특별자치도", sigungu="속초시")
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.MATCH
    assert check.score_signal == 1  # precision bonus signal


def test_region_sigungu_different_sigungu_excludable():
    service = make_service(region_scope=RegionScope.SIGUNGU, sido="강원특별자치도", sigungu="속초시")
    user = make_user(sido="강원특별자치도", sigungu="평창군")
    assert evaluate_region(user, service).status is MatchStatus.MISMATCH


def test_region_sigungu_different_sido_excludable_without_checking_sigungu():
    service = make_service(region_scope=RegionScope.SIGUNGU, sido="강원특별자치도", sigungu="속초시")
    user = make_user(sido="서울특별시", sigungu="속초시")  # nonsensical but must still exclude on sido
    assert evaluate_region(user, service).status is MatchStatus.MISMATCH


def test_region_sigungu_missing_user_sigungu_is_unknown_not_excluded():
    service = make_service(region_scope=RegionScope.SIGUNGU, sido="강원특별자치도", sigungu="속초시")
    user = make_user(sido="강원특별자치도", sigungu=None)
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.UNKNOWN
    assert check.confirmation_needed is True
    assert region_needs_sigungu_confirmation(user, service) is True


# ---------------------------------------------------------------------------
# C. Age rules
# ---------------------------------------------------------------------------


def test_age_simple_min_clear_mismatch_excludable():
    service = make_service(age_condition_type=AgeConditionType.SIMPLE_MIN, min_age=65)
    user = make_user(age=40)
    assert evaluate_age(user, service).status is MatchStatus.MISMATCH


def test_age_simple_min_pass():
    service = make_service(age_condition_type=AgeConditionType.SIMPLE_MIN, min_age=65)
    user = make_user(age=70)
    assert evaluate_age(user, service).status is MatchStatus.MATCH


def test_age_simple_min_user_unknown_not_excluded():
    service = make_service(age_condition_type=AgeConditionType.SIMPLE_MIN, min_age=65)
    user = make_user(age=None)
    check = evaluate_age(user, service)
    assert check.status is MatchStatus.UNKNOWN
    assert check.confirmation_needed is True


def test_age_none_condition_is_always_unknown_neutral():
    service = make_service(age_condition_type=AgeConditionType.NONE, min_age=None)
    user = make_user(age=30)
    check = evaluate_age(user, service)
    assert check.status is MatchStatus.UNKNOWN
    assert check.confirmation_needed is False


def test_age_compound_never_hard_excludes_even_when_below_threshold():
    service = make_service(
        age_condition_type=AgeConditionType.COMPOUND,
        min_age=65,
        age_condition_note="65세 이상 또는 노인성질환 65세 미만",
    )
    user = make_user(age=40)
    check = evaluate_age(user, service)
    assert check.status is not MatchStatus.MISMATCH
    assert is_age_compound_uncertain(user, service) is True


def test_age_compound_above_threshold_is_match_not_forced_confirmation():
    service = make_service(
        age_condition_type=AgeConditionType.COMPOUND,
        min_age=65,
        age_condition_note="65세 이상 또는 노인성질환 65세 미만",
    )
    user = make_user(age=70)
    check = evaluate_age(user, service)
    assert check.status is MatchStatus.MATCH
    assert is_age_compound_uncertain(user, service) is False
