"""End-to-end tests for recommender.recommend()."""

from recommender.models import DesiredSupport, MatchLevel, TriState
from recommender.recommender import evaluate_service, recommend

from .conftest import make_service, make_user


def test_confirmation_needed_downgrades_match_level():
    """G: a service whose core conditions are UNKNOWN for the user should
    not reach HIGH_MATCH, even with a perfect service_type match."""
    service = make_service(
        disability_required=TriState.TRUE,
        low_income_required=TriState.TRUE,
        service_type=frozenset({"meal_support"}),
        verification_level="A",
    )
    user = make_user(
        sido=service.sido,
        sigungu=service.sigungu,
        has_disability=TriState.UNKNOWN,
        low_income_status=TriState.UNKNOWN,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    result = evaluate_service(user, service)
    assert result is not None
    assert result.match_level is MatchLevel.NEEDS_CONFIRMATION
    assert len(result.confirmation_needed) >= 2


def test_high_match_possible_when_everything_resolved():
    service = make_service(
        disability_required=TriState.FALSE,
        low_income_required=TriState.TRUE,
        single_household_required=TriState.TRUE,
        homebound_or_mobility_condition=TriState.TRUE,
        service_type=frozenset({"meal_support"}),
        verification_level="A",
    )
    user = make_user(
        sido=service.sido,
        sigungu=service.sigungu,
        has_disability=TriState.FALSE,
        low_income_status=TriState.TRUE,
        lives_alone=TriState.TRUE,
        mobility_difficulty=TriState.TRUE,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    result = evaluate_service(user, service)
    assert result is not None
    assert result.match_level is MatchLevel.HIGH_MATCH


def test_zero_service_type_overlap_never_reaches_high_or_possible_match():
    """Regression test for the 2026-08-23 real-user case
    (docs/recommendation_engine_real_case_validation.md): a service that
    passes every eligibility gate but offers a completely different kind of
    help than what the user asked for must not be labeled the same as a
    genuine match, even though it is not hard-excluded either."""
    service = make_service(
        disability_required=TriState.FALSE,
        low_income_required=TriState.FALSE,
        service_type=frozenset({"home_visit"}),  # user wants meal_support only
        verification_level="A",
    )
    user = make_user(
        sido=service.sido,
        sigungu=service.sigungu,
        has_disability=TriState.FALSE,
        low_income_status=TriState.FALSE,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    result = evaluate_service(user, service)
    assert result is not None  # not hard-excluded
    assert result.match_level is MatchLevel.NEEDS_CONFIRMATION
    assert any("직접 관련되지는 않아요" in w for w in result.exclusion_warnings)


def test_service_type_overlap_still_reaches_high_match_when_everything_resolved():
    """The fix must not block genuine matches -- this mirrors
    test_high_match_possible_when_everything_resolved and must keep passing."""
    service = make_service(
        disability_required=TriState.FALSE,
        low_income_required=TriState.TRUE,
        single_household_required=TriState.TRUE,
        homebound_or_mobility_condition=TriState.TRUE,
        service_type=frozenset({"meal_support"}),
        verification_level="A",
    )
    user = make_user(
        sido=service.sido,
        sigungu=service.sigungu,
        has_disability=TriState.FALSE,
        low_income_status=TriState.TRUE,
        lives_alone=TriState.TRUE,
        mobility_difficulty=TriState.TRUE,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    result = evaluate_service(user, service)
    assert result is not None
    assert result.match_level is MatchLevel.HIGH_MATCH


def test_hard_excluded_service_returns_none():
    service = make_service(disability_required=TriState.TRUE)
    user = make_user(sido=service.sido, sigungu=service.sigungu, has_disability=TriState.FALSE)
    assert evaluate_service(user, service) is None


def test_unsure_forces_needs_confirmation_even_with_high_score():
    service = make_service(verification_level="A")
    user = make_user(
        sido=service.sido,
        sigungu=service.sigungu,
        desired_support=frozenset({DesiredSupport.UNSURE}),
    )
    result = evaluate_service(user, service)
    assert result is not None
    assert result.match_level is MatchLevel.NEEDS_CONFIRMATION


def test_deterministic_same_input_same_output(all_services):
    """H: running the same profile twice must produce identical results."""
    user = make_user(sido="강원특별자치도", sigungu=None, age=75)
    run1 = recommend(user, services=all_services, top_k=10)
    run2 = recommend(user, services=all_services, top_k=10)
    assert [r.service_id for r in run1] == [r.service_id for r in run2]
    assert [r.match_score for r in run1] == [r.match_score for r in run2]


def test_top_k_respected(all_services):
    """I: top_k limits the number of returned results."""
    user = make_user(sido=None, sigungu=None, age=None, desired_support=frozenset({DesiredSupport.UNSURE}))
    result_3 = recommend(user, services=all_services, top_k=3)
    result_1 = recommend(user, services=all_services, top_k=1)
    assert len(result_3) <= 3
    assert len(result_1) <= 1


def test_full_dataset_runs_without_exceptions_for_varied_profiles(all_services):
    """J: the full 85-row dataset must run cleanly for a range of profiles,
    including maximally unknown ones."""
    profiles = [
        make_user(),
        make_user(sido=None, sigungu=None, age=None,
                   has_disability=TriState.UNKNOWN, low_income_status=TriState.UNKNOWN,
                   lives_alone=TriState.UNKNOWN, mobility_difficulty=TriState.UNKNOWN,
                   desired_support=frozenset({DesiredSupport.UNSURE})),
        make_user(age=5),
        make_user(age=120),
        make_user(desired_support=frozenset(DesiredSupport)),  # every option at once
    ]
    for profile in profiles:
        results = recommend(profile, services=all_services, top_k=85)
        assert isinstance(results, list)
        for r in results:
            assert 0.0 <= r.match_score <= 100.0


def test_recommend_loads_real_csv_by_default():
    """Sanity check that the default loader path works end-to-end."""
    user = make_user(sido="강원특별자치도", sigungu=None, age=75)
    results = recommend(user, top_k=5)
    assert len(results) <= 5
    assert all(r.match_score >= 0 for r in results)
