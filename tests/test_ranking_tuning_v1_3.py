"""v1.3 ranking tuning (docs/recommendation_ranking_final_tuning_report.md).

Real-Streamlit-user-reported symptom: for a Cheonan profile, switching
desired_support between meal_support and community_care produced an
IDENTICAL Top-4 composition and order. Root-caused to two separate things:

  1. Only 4 services pass the hard filter for this profile at all (region
     coverage limitation -- not a scoring bug, see the report §0/§8).
  2. Within those 4, the OLD binary service_type intersection gave the two
     Cheonan services an identical 0-credit tie under meal_support (neither
     has the meal_support tag), so a deterministic tie-break always put
     them in the same order regardless of desired_support.

Fix: _service_type_component (scorer.py) now grades EXACT vs RELATED vs
NEUTRAL service_type relevance instead of pure binary intersection,
using only existing fields (service_type tags + nutrition_relevance).
special_eligibility_required-gated services (WLF00000098/WLF00003248/
ENR-CHEONAN-02) must still never reach HIGH_MATCH.
"""
from recommender.loader import load_services
from recommender.models import DesiredSupport, TriState, UserProfile
from recommender.recommender import recommend

PRODUCTION_SERVICES = load_services()  # real 87-row production data


def _cheonan_profile(desired, disability=TriState.FALSE):
    return UserProfile(
        sido="충청남도", sigungu="천안시", age=75,
        low_income_status=TriState.TRUE, lives_alone=TriState.TRUE,
        mobility_difficulty=TriState.TRUE, meal_preparation_difficulty=TriState.TRUE,
        has_disability=disability, recent_discharge=TriState.UNKNOWN,
        desired_support=frozenset({desired}),
    )


def test_desired_support_changes_top4_order_for_the_reported_cheonan_profile():
    meal = recommend(_cheonan_profile(DesiredSupport.MEAL_SUPPORT), services=PRODUCTION_SERVICES, top_k=10)
    community = recommend(_cheonan_profile(DesiredSupport.COMMUNITY_CARE), services=PRODUCTION_SERVICES, top_k=10)
    meal_order = [r.service_id for r in meal][:4]
    community_order = [r.service_id for r in community][:4]
    # same DATA_COVERAGE-limited candidate pool (only 4 services pass the
    # hard filter for this profile), but the ORDER must no longer be frozen.
    assert set(meal_order) == set(community_order)
    assert meal_order != community_order


def test_community_care_request_ranks_exact_match_above_related_above_unrelated():
    results = recommend(_cheonan_profile(DesiredSupport.COMMUNITY_CARE), services=PRODUCTION_SERVICES, top_k=10)
    by_id = {r.service_id: r for r in results}
    # ENR-CHEONAN-01/02: exact "community_care" tag match
    # WLF00000098/WLF00003248: only "home_visit" -- RELATED, not exact
    assert by_id["ENR-CHEONAN-01"].match_score > by_id["WLF00000098"].match_score
    assert by_id["ENR-CHEONAN-02"].match_score > by_id["WLF00003248"].match_score


def test_meal_support_request_ranks_nutrition_adjacent_service_above_pure_community_care():
    results = recommend(_cheonan_profile(DesiredSupport.MEAL_SUPPORT), services=PRODUCTION_SERVICES, top_k=10)
    by_id = {r.service_id: r for r in results}
    # ENR-CHEONAN-02 (nutrition_relevance=SUPPORTIVE_NUTRITION) is food-adjacent;
    # ENR-CHEONAN-01 (service_type={community_care} only, no nutrition signal) is not.
    assert by_id["ENR-CHEONAN-02"].match_score > by_id["ENR-CHEONAN-01"].match_score


def test_special_eligibility_service_never_reaches_high_match_regardless_of_desired_support():
    for desired in (DesiredSupport.MEAL_SUPPORT, DesiredSupport.COMMUNITY_CARE):
        results = recommend(_cheonan_profile(desired), services=PRODUCTION_SERVICES, top_k=10)
        for r in results:
            if r.service_id in ("WLF00000098", "WLF00003248", "ENR-CHEONAN-02"):
                assert r.match_level.value != "HIGH_MATCH", (
                    f"{r.service_id} ({desired.value}) reached HIGH_MATCH despite "
                    "special_eligibility_required=True"
                )


def test_general_user_never_produces_high_match_from_unknown_heavy_profile():
    """§9 Test 5: an almost-entirely-UNKNOWN profile must never yield HIGH_MATCH."""
    user = UserProfile(
        sido="충청남도", sigungu="천안시",
        desired_support=frozenset({DesiredSupport.COMMUNITY_CARE}),
    )
    results = recommend(user, services=PRODUCTION_SERVICES, top_k=10)
    assert all(r.match_level.value != "HIGH_MATCH" for r in results)


def test_disability_yes_no_identical_for_cheonan_is_data_coverage_not_logic_bug():
    """§8: disability truly has zero region-eligible candidate with
    disability_required=true for this Cheonan profile, so D0/D1/D2 must be
    identical -- documented as DATA_COVERAGE_ISSUE, not silently 'fixed' by
    inventing a disability scoring bonus (explicitly forbidden this turn)."""
    no = recommend(_cheonan_profile(DesiredSupport.COMMUNITY_CARE, disability=TriState.FALSE), services=PRODUCTION_SERVICES, top_k=10)
    yes = recommend(_cheonan_profile(DesiredSupport.COMMUNITY_CARE, disability=TriState.TRUE), services=PRODUCTION_SERVICES, top_k=10)
    unknown = recommend(_cheonan_profile(DesiredSupport.COMMUNITY_CARE, disability=TriState.UNKNOWN), services=PRODUCTION_SERVICES, top_k=10)
    scores_no = [(r.service_id, r.match_score) for r in no]
    scores_yes = [(r.service_id, r.match_score) for r in yes]
    scores_unknown = [(r.service_id, r.match_score) for r in unknown]
    assert scores_no == scores_yes == scores_unknown
