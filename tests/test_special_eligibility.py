"""v1.2 fix: special_eligibility_required gate.

docs/recommendation_engine_v1_2_validation.md §7-8 -- WLF00000098(국가유공자
재가복지지원)/WLF00003248(재가급여) are both region_scope=NATIONAL with
disability_required/low_income_required = unknown/false, so none of the
existing HARD-gate fields could ever flag them as needing confirmation --
they could reach HIGH_MATCH by default for any general user, even though
their real original text requires an institutionally-certified special
status (보훈 registration / a formal 장기요양등급 판정) that nothing else
in the data represents. Direct reading of target_original/criteria_original
for all 85 rows found exactly these 2 rows warrant the flag -- see the
report's full audit table for the reviewed-and-rejected candidates.
"""

from recommender.filters import apply_hard_filters
from recommender.matcher import evaluate_special_eligibility
from recommender.models import MatchStatus, TriState
from recommender.recommender import recommend

from .conftest import make_service, make_user


def test_evaluate_special_eligibility_neutral_when_not_required():
    service = make_service(special_eligibility_required=TriState.UNKNOWN)
    check = evaluate_special_eligibility(service)
    assert check.status is MatchStatus.UNKNOWN
    assert check.confirmation_needed is False


def test_evaluate_special_eligibility_flags_confirmation_when_required():
    service = make_service(
        special_eligibility_required=TriState.TRUE,
        special_eligibility_note="국가유공자 등록 필요",
    )
    check = evaluate_special_eligibility(service)
    assert check.status is MatchStatus.UNKNOWN  # never MATCH -- nothing confirms the user has it
    assert check.confirmation_needed is True
    assert "국가유공자 등록 필요" in check.reason


def test_special_eligibility_never_hard_excludes():
    """UNKNOWN != FALSE still holds -- a flagged service must never be
    HARD-excluded outright, only downgraded via open_count (rules_spec.md
    §5's core principle, unchanged by this addition)."""
    service = make_service(special_eligibility_required=TriState.TRUE)
    user = make_user()
    result = apply_hard_filters(user, service)
    assert result.passed is True


def test_special_eligibility_counts_toward_open_count():
    service = make_service(special_eligibility_required=TriState.TRUE)
    user = make_user()
    result = apply_hard_filters(user, service)
    assert result.open_count() >= 1


# ---------------------------------------------------------------------------
# Real data: the two rows actually flagged, and everyone else untouched
# ---------------------------------------------------------------------------


def test_only_known_real_services_are_flagged(all_services):
    """WLF00000098/WLF00003248 are the original v1.2 audit's 2 hits.
    ENR-CHEONAN-02 (의료·요양 통합돌봄) was added by the Cheonan production
    merge -- its 통합판정(건보공단)/통합지원회의 procedural gate is the same
    pattern (see docs/cheonan_official_enrichment_report.md)."""
    flagged = [s.service_id for s in all_services if s.special_eligibility_required is TriState.TRUE]
    assert sorted(flagged) == ["ENR-CHEONAN-02", "WLF00000098", "WLF00003248"]


def test_flagged_services_never_reach_high_match_for_a_general_user(all_services):
    """The exact regression this fix targets: instructions(v1.2) §7 --
    "일반 사용자에게 HIGH_MATCH처럼 보이는 것을 방지". Uses a desired_support
    that actually overlaps home_visit (both flagged services' service_type)
    so the test exercises the realistic case where they'd otherwise have
    scored highly, not a case where they're excluded by desired_support
    mismatch anyway.
    """
    user = make_user(
        sido="강원특별자치도", sigungu="춘천시", age=70,
        has_disability=TriState.UNKNOWN, low_income_status=TriState.UNKNOWN,
        lives_alone=TriState.UNKNOWN, mobility_difficulty=TriState.UNKNOWN,
        meal_preparation_difficulty=TriState.UNKNOWN, recent_discharge=TriState.UNKNOWN,
    )
    from recommender.models import DesiredSupport

    user = make_user(
        sido=user.sido, sigungu=user.sigungu, age=user.age,
        desired_support=frozenset({DesiredSupport.HOME_VISIT}),
    )
    results = recommend(user, services=all_services, top_k=85)
    for r in results:
        if r.service_id in ("WLF00000098", "WLF00003248"):
            assert r.match_level.value != "HIGH_MATCH", (
                f"{r.service_id} reached HIGH_MATCH for a general user with no stated "
                "special eligibility -- the gate is not working"
            )


def test_flagged_services_still_appear_not_deleted(all_services):
    """Never hard-excluded -- still visible with a confirmation message,
    per instructions §9 ("무조건 제외되지 않고 confirmation 처리되는지").
    top_k covers every service that can pass the filter (len(all_services),
    not the old hardcoded 85) so this stays a "not excluded" check, not an
    incidental top-K ranking cutoff -- see
    docs/recommendation_ranking_final_tuning_report.md."""
    user = make_user(sido=None, sigungu=None)  # NATIONAL services are region-independent
    results = recommend(user, services=all_services, top_k=len(all_services))
    ids = {r.service_id for r in results}
    assert "WLF00000098" in ids
    assert "WLF00003248" in ids
