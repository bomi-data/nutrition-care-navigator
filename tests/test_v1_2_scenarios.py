"""v1.2 diagnostic scenarios (instructions §13 / docs/
recommendation_engine_v1_2_validation.md §9-11), run against the real
85-service dataset. Each scenario documents what the diagnostic pass
actually found -- including the cases where "no change" is the *correct*,
expected outcome (data limitation, not a bug) rather than assuming more
sensitivity is always better.
"""

from recommender.models import DesiredSupport, MatchLevel, TriState, UserProfile
from recommender.recommender import recommend

HWASEONG_BASE = dict(
    sido="경기도", sigungu="화성시 동탄구",
    age=75,
    has_disability=TriState.FALSE, low_income_status=TriState.TRUE,
    lives_alone=TriState.TRUE, mobility_difficulty=TriState.TRUE,
    meal_preparation_difficulty=TriState.TRUE, recent_discharge=TriState.FALSE,
    desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
)


def test_scenario_1_hwaseong_meal_support_top_result_is_reasonable(all_services):
    """A real meal_support candidate exists for this region (WLF00004001,
    SIDO-scope 경기도) -- it should surface, reasonably ranked."""
    results = recommend(UserProfile(**HWASEONG_BASE), services=all_services, top_k=5)
    assert results
    top = results[0]
    assert "meal_support" in top.service_type
    assert top.match_level in (MatchLevel.HIGH_MATCH, MatchLevel.POSSIBLE_MATCH)


def test_scenario_2_disability_change_has_no_effect_in_a_disability_data_poor_region(all_services):
    """CONFIRMED DATA_LIMITATION, not a scoring bug (report §disability):
    zero of the 3 region-surviving candidates for 화성시 동탄구 have any
    disability_required structuring, so disability=아니오->예 legitimately
    changes nothing here. (Contrast with test_special_eligibility.py /
    tests/test_scenarios.py's 성동구 case, where the exact same input DOES
    reorder results dramatically once a disability-structured candidate is
    actually in range.)
    """
    before = recommend(UserProfile(**HWASEONG_BASE), services=all_services, top_k=5)
    kw = dict(HWASEONG_BASE)
    kw["has_disability"] = TriState.TRUE
    after = recommend(UserProfile(**kw), services=all_services, top_k=5)

    assert [(r.service_id, r.match_score) for r in before] == [(r.service_id, r.match_score) for r in after]


def test_scenario_3_low_income_required_service_is_hard_excluded_when_user_says_no(all_services):
    """WLF00004001 has low_income_required=true -- switching the user to
    definitively NOT low-income must hard-exclude it (rules_spec.md §5
    matrix row #2), the one HARD gate genuinely exercised by this profile."""
    before = recommend(UserProfile(**HWASEONG_BASE), services=all_services, top_k=5)
    before_ids = {r.service_id for r in before}
    assert "WLF00004001" in before_ids

    kw = dict(HWASEONG_BASE)
    kw["low_income_status"] = TriState.FALSE
    after = recommend(UserProfile(**kw), services=all_services, top_k=5)
    after_ids = {r.service_id for r in after}
    assert "WLF00004001" not in after_ids


def test_scenario_4_unknown_sigungu_widens_the_candidate_pool(all_services):
    """Removing sigungu specificity should never shrink the candidate pool
    -- SIDO-scope services with sigungu=UNKNOWN degrade to UNKNOWN (not
    excluded), so the pool can only stay the same size or grow."""
    before = recommend(UserProfile(**HWASEONG_BASE), services=all_services, top_k=85)
    kw = dict(HWASEONG_BASE)
    kw["sigungu"] = None
    after = recommend(UserProfile(**kw), services=all_services, top_k=85)
    assert len(after) >= len(before)


def test_scenario_5_desired_support_type_change_reorders_results(all_services):
    """춘천시 has real service_type diversity (WLF00005308 covers all three
    tags; WLF00000098/WLF00003248 are home_visit-only) -- switching
    desired_support must visibly change which services can even reach
    HIGH_MATCH/POSSIBLE_MATCH (rule 5: no service_type overlap -> capped at
    NEEDS_CONFIRMATION)."""
    base = dict(
        sido="강원특별자치도", sigungu="춘천시", age=70,
        has_disability=TriState.UNKNOWN, low_income_status=TriState.UNKNOWN,
        lives_alone=TriState.UNKNOWN, mobility_difficulty=TriState.UNKNOWN,
        meal_preparation_difficulty=TriState.UNKNOWN, recent_discharge=TriState.UNKNOWN,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    meal_results = recommend(UserProfile(**base), services=all_services, top_k=85)
    meal_levels = {r.service_id: r.match_level for r in meal_results}

    kw = dict(base)
    kw["desired_support"] = frozenset({DesiredSupport.HOME_VISIT})
    visit_results = recommend(UserProfile(**kw), services=all_services, top_k=85)
    visit_levels = {r.service_id: r.match_level for r in visit_results}

    # home_visit-only services must improve (never worsen) once the user's
    # desired_support actually overlaps their service_type.
    for sid in ("WLF00000098", "WLF00003248"):
        assert meal_levels.get(sid) is MatchLevel.NEEDS_CONFIRMATION  # no overlap with meal_support
        assert visit_levels.get(sid) is not MatchLevel.NEEDS_CONFIRMATION  # overlap now exists


def test_scenario_6_general_elderly_user_does_not_get_high_match_special_eligibility_service(all_services):
    """instructions §13 scenario 6: a general elderly user with no stated
    special eligibility must never see WLF00000098/WLF00003248 as
    HIGH_MATCH (the exact regression the special_eligibility_required gate
    targets -- see tests/test_special_eligibility.py for the focused unit
    tests)."""
    user = UserProfile(
        sido="강원특별자치도", sigungu="춘천시", age=70,
        has_disability=TriState.UNKNOWN, low_income_status=TriState.UNKNOWN,
        lives_alone=TriState.UNKNOWN, mobility_difficulty=TriState.UNKNOWN,
        meal_preparation_difficulty=TriState.UNKNOWN, recent_discharge=TriState.UNKNOWN,
        desired_support=frozenset({DesiredSupport.COMMUNITY_CARE}),
    )
    results = recommend(user, services=all_services, top_k=85)
    for r in results:
        if r.service_id in ("WLF00000098", "WLF00003248"):
            assert r.match_level is not MatchLevel.HIGH_MATCH


def test_scenario_7_special_eligibility_unknown_is_not_excluded(all_services):
    """instructions §13 scenario 7: UNKNOWN special eligibility must never
    hard-exclude -- the two flagged services still appear, with a
    confirmation message, for any region-eligible user."""
    user = UserProfile(
        sido=None, sigungu=None, age=70,  # NATIONAL services are region-independent
        has_disability=TriState.UNKNOWN, low_income_status=TriState.UNKNOWN,
        lives_alone=TriState.UNKNOWN, mobility_difficulty=TriState.UNKNOWN,
        meal_preparation_difficulty=TriState.UNKNOWN, recent_discharge=TriState.UNKNOWN,
        desired_support=frozenset({DesiredSupport.HOME_VISIT}),
    )
    results = recommend(user, services=all_services, top_k=85)
    ids = {r.service_id for r in results}
    assert "WLF00000098" in ids
    assert "WLF00003248" in ids
    for r in results:
        if r.service_id in ("WLF00000098", "WLF00003248"):
            assert any("특수 자격요건" in c for c in r.confirmation_needed)


def test_scenario_8_sparse_info_service_never_outscores_a_confirmed_match(all_services):
    """instructions §13 scenario 8: a service the system knows almost
    nothing about (WLF00000098 -- disability/low_income both unknown,
    special_eligibility unresolved) must never outscore, for the same
    user, a service with an actual confirmed structural match
    (WLF00004001 -- low_income_required=true and the user genuinely is
    low-income). Complements test_scorer.py's existing anti-gaming test at
    the single-service level with an end-to-end recommend() check.
    """
    results = recommend(UserProfile(**HWASEONG_BASE), services=all_services, top_k=85)
    scores = {r.service_id: r.match_score for r in results}
    assert "WLF00004001" in scores and "WLF00000098" in scores
    assert scores["WLF00004001"] > scores["WLF00000098"]
