"""Regression test for the first real Streamlit user test (2026-08-23).

Profile: 75-year-old, 경기도 화성시 동탄구, not disabled, low-income,
lives alone, mobility difficulty, meal-prep difficulty, no recent
discharge, wants meal_support only.

This is deliberately NOT a "service X must be #1" test -- the task
instructions explicitly warn against overfitting to one example. Instead
it checks the general properties the diagnosis in
docs/recommendation_engine_real_case_validation.md established should
always hold for a profile like this.
"""

from recommender.models import DesiredSupport, MatchLevel, TriState, UserProfile
from recommender.recommender import recommend

PROFILE = UserProfile(
    sido="경기도",
    sigungu="화성시 동탄구",
    age=75,
    has_disability=TriState.FALSE,
    low_income_status=TriState.TRUE,
    lives_alone=TriState.TRUE,
    mobility_difficulty=TriState.TRUE,
    meal_preparation_difficulty=TriState.TRUE,
    recent_discharge=TriState.FALSE,
    desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
)


def test_top_result_is_a_direct_meal_support_match(all_services):
    results = recommend(PROFILE, services=all_services, top_k=5)
    assert results, "expected at least one surviving candidate"
    top = results[0]
    assert "meal_support" in top.service_type
    assert top.match_level is MatchLevel.HIGH_MATCH


def test_no_region_mismatched_service_survives(all_services):
    results = recommend(PROFILE, services=all_services, top_k=85)
    for r in results:
        scope = r.region["region_scope"]
        assert scope == "NATIONAL" or r.region["sido"] == "경기도", (
            f"{r.service_id} region {r.region} should not have survived the region gate"
        )


def test_services_with_no_service_type_overlap_are_capped_at_needs_confirmation(all_services):
    """This is the core fix from the real-case review: a service that does
    not offer meal_support at all must never be labeled HIGH_MATCH or
    POSSIBLE_MATCH just because it happened to pass every eligibility gate
    and nothing more relevant was left in the candidate pool."""
    results = recommend(PROFILE, services=all_services, top_k=85)
    for r in results:
        if "meal_support" not in r.service_type:
            assert r.match_level is MatchLevel.NEEDS_CONFIRMATION, (
                f"{r.service_id} has no meal_support overlap but is {r.match_level}"
            )


def test_unknown_service_side_fields_do_not_hard_exclude(all_services):
    """WLF00004001 has disability_required/single_household_required=unknown
    and must still pass (UNKNOWN is never treated as a disqualifier)."""
    results = recommend(PROFILE, services=all_services, top_k=85)
    ids = {r.service_id for r in results}
    assert "WLF00004001" in ids


def test_deterministic_repeat_run(all_services):
    run1 = recommend(PROFILE, services=all_services, top_k=5)
    run2 = recommend(PROFILE, services=all_services, top_k=5)
    assert [(r.service_id, r.match_score, r.match_level) for r in run1] == [
        (r.service_id, r.match_score, r.match_level) for r in run2
    ]


def test_small_candidate_pool_is_a_documented_data_coverage_limit_not_a_crash(all_services):
    """화성시 has zero directly-scoped services in the 85-row dataset, so a
    very small result count (here: 3) is the correct, honest outcome -- not
    an error. This test just guards against the pipeline silently returning
    nothing or raising instead."""
    results = recommend(PROFILE, services=all_services, top_k=5)
    assert 1 <= len(results) <= 5
