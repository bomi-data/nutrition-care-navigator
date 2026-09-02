"""Automated versions of the 10 user scenarios from
docs/recommendation_rules_spec.md §13, run against the real 85-row dataset.

These are sanity/regression checks (no exceptions, sane candidate counts,
valid score range) -- the full narrative results (top-5 lists, reasons,
confirmations) are reported separately in
docs/recommendation_engine_v1_report.md, generated from the same profiles.
No scenario asserts a specific "correct" service_id -- per the task
instructions, we test that the pipeline behaves logically, not that a
pre-decided answer comes out on top.
"""

from recommender.models import DesiredSupport, MatchLevel, TriState, UserProfile
from recommender.recommender import recommend

MS = DesiredSupport.MEAL_SUPPORT
CC = DesiredSupport.COMMUNITY_CARE
DS = DesiredSupport.DISCHARGE_SUPPORT
UNSURE = DesiredSupport.UNSURE
T, F, U = TriState.TRUE, TriState.FALSE, TriState.UNKNOWN


SCENARIOS = {
    "75세 독거+식사준비어려움": UserProfile(
        sido="강원특별자치도", sigungu=None, age=75,
        lives_alone=T, meal_preparation_difficulty=T,
        desired_support=frozenset({MS}),
    ),
    "70세 저소득+거동불편": UserProfile(
        sido="경상남도", sigungu=None, age=70,
        low_income_status=T, mobility_difficulty=T,
        desired_support=frozenset({MS}),
    ),
    "68세 장애+식사지원": UserProfile(
        sido="서울특별시", sigungu="성동구", age=68,
        has_disability=T, meal_preparation_difficulty=T,
        desired_support=frozenset({MS}),
    ),
    "66세 취약조건 없음": UserProfile(
        sido="전북특별자치도", sigungu=None, age=66,
        has_disability=F, low_income_status=F, lives_alone=F, mobility_difficulty=F,
        desired_support=frozenset({MS}),
    ),
    "지역만 입력, 나머지 모름": UserProfile(
        sido="강원특별자치도", sigungu=None, age=None,
        desired_support=frozenset({UNSURE}),
    ),
    "40세 연령 명백 불일치": UserProfile(
        sido="강원특별자치도", sigungu=None, age=40,
        has_disability=F, low_income_status=F,
        desired_support=frozenset({MS}),
    ),
    "시군구 명백 불일치": UserProfile(
        sido="제주특별자치도", sigungu="서귀포시", age=75,
        low_income_status=T, lives_alone=T, meal_preparation_difficulty=T,
        desired_support=frozenset({MS}),
    ),
    "대부분 정보 모름(지역조차 모름)": UserProfile(
        sido=None, sigungu=None, age=None,
        desired_support=frozenset({UNSURE}),
    ),
    "여러 서비스유형 필요": UserProfile(
        sido="강원특별자치도", sigungu=None, age=75,
        low_income_status=T, meal_preparation_difficulty=T,
        desired_support=frozenset({MS, CC}),
    ),
    "최근 퇴원+재택생활지원": UserProfile(
        sido="경상남도", sigungu=None, age=72,
        mobility_difficulty=T, recent_discharge=T,
        desired_support=frozenset({DS, CC}),
    ),
}


def test_all_ten_scenarios_run_without_exceptions_and_return_sane_results(all_services):
    for name, profile in SCENARIOS.items():
        results = recommend(profile, services=all_services, top_k=5)
        assert isinstance(results, list), name
        assert len(results) <= 5, name
        for r in results:
            assert 0.0 <= r.match_score <= 100.0, name
            assert r.match_level in (
                MatchLevel.HIGH_MATCH,
                MatchLevel.POSSIBLE_MATCH,
                MatchLevel.NEEDS_CONFIRMATION,
            ), name


def test_unsure_scenarios_never_reach_high_match(all_services):
    for name in ("지역만 입력, 나머지 모름", "대부분 정보 모름(지역조차 모름)"):
        results = recommend(SCENARIOS[name], services=all_services, top_k=85)
        assert all(r.match_level is not MatchLevel.HIGH_MATCH for r in results), name


def test_age_mismatch_scenario_excludes_most_age_restricted_services(all_services):
    results = recommend(SCENARIOS["40세 연령 명백 불일치"], services=all_services, top_k=85)
    # every surviving service must NOT have a plain numeric age gate above 40
    for r in results:
        svc = next(s for s in all_services if s.service_id == r.service_id)
        if svc.age_condition_type.value == "SIMPLE_MIN" and svc.min_age is not None:
            assert svc.min_age <= 40, r.service_id


def test_region_mismatch_scenario_only_keeps_matching_or_national_services(all_services):
    results = recommend(SCENARIOS["시군구 명백 불일치"], services=all_services, top_k=85)
    for r in results:
        assert r.region["region_scope"] in ("NATIONAL",) or r.region["sido"] == "제주특별자치도"
