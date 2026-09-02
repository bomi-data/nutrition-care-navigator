"""Tests for HARD FILTER orchestration (recommender.filters).

Covers: hard-exclude on clear region/age/disability/low_income conflicts,
and -- critically -- that UNKNOWN never triggers a hard exclusion.
"""

from recommender.filters import apply_hard_filters
from recommender.models import AgeConditionType, RegionScope, TriState

from .conftest import make_service, make_user


def test_unknown_conditions_never_hard_exclude():
    """D: a service that states disability/low_income requirements, when
    the user answers UNKNOWN to everything, must still PASS the gate."""
    service = make_service(
        disability_required=TriState.TRUE,
        low_income_required=TriState.TRUE,
        region_scope=RegionScope.SIGUNGU,
    )
    user = make_user(
        sido=service.sido,
        sigungu=None,  # unknown
        age=None,  # unknown
        has_disability=TriState.UNKNOWN,
        low_income_status=TriState.UNKNOWN,
    )
    result = apply_hard_filters(user, service)
    assert result.passed is True
    assert result.exclusion_reason == ""


def test_disability_true_user_false_hard_excludes():
    """E: disability_required=TRUE + user explicitly not disabled -> exclude."""
    service = make_service(disability_required=TriState.TRUE)
    user = make_user(sido=service.sido, sigungu=service.sigungu, has_disability=TriState.FALSE)
    result = apply_hard_filters(user, service)
    assert result.passed is False
    assert "장애" in result.exclusion_reason


def test_low_income_true_user_false_hard_excludes():
    service = make_service(low_income_required=TriState.TRUE)
    user = make_user(sido=service.sido, sigungu=service.sigungu, low_income_status=TriState.FALSE)
    result = apply_hard_filters(user, service)
    assert result.passed is False


def test_clear_age_mismatch_hard_excludes():
    service = make_service(age_condition_type=AgeConditionType.SIMPLE_MIN, min_age=65)
    user = make_user(sido=service.sido, sigungu=service.sigungu, age=30)
    result = apply_hard_filters(user, service)
    assert result.passed is False
    assert "65" in result.exclusion_reason


def test_clear_region_mismatch_hard_excludes():
    service = make_service(region_scope=RegionScope.SIDO, sido="경기도", sigungu=None)
    user = make_user(sido="서울특별시", sigungu=None)
    result = apply_hard_filters(user, service)
    assert result.passed is False


def test_compound_age_below_threshold_does_not_exclude():
    service = make_service(
        age_condition_type=AgeConditionType.COMPOUND,
        min_age=65,
        age_condition_note="복합 조건",
    )
    user = make_user(sido=service.sido, sigungu=service.sigungu, age=40)
    result = apply_hard_filters(user, service)
    assert result.passed is True


def test_open_count_counts_only_service_required_user_unknown():
    service = make_service(
        disability_required=TriState.TRUE,
        low_income_required=TriState.TRUE,
        region_scope=RegionScope.SIGUNGU,
    )
    user = make_user(
        sido=service.sido,
        sigungu=None,
        age=None,
        has_disability=TriState.UNKNOWN,
        low_income_status=TriState.UNKNOWN,
    )
    result = apply_hard_filters(user, service)
    # region(unknown, service is SIGUNGU-scope and specifies a location) +
    # disability(unknown) + low_income(unknown) = 3 open items.
    # age is NONE-condition here (no min_age set) so it does not add one.
    assert result.open_count() == 3


def test_no_open_count_when_service_does_not_state_the_condition():
    service = make_service()  # everything UNKNOWN/None by default
    user = make_user(
        sido=service.sido,
        sigungu=service.sigungu,
        has_disability=TriState.UNKNOWN,
        low_income_status=TriState.UNKNOWN,
    )
    result = apply_hard_filters(user, service)
    assert result.open_count() == 0
