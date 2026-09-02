"""v1.2 fix: sigungu sub-district ("구") granularity fallback.

docs/recommendation_engine_v1_2_validation.md §region -- region_codes.csv
(the Streamlit dropdown's source) lists 39 sub-district entries across 8+
major cities (화성시 동탄구, 전주시 덕진구, 수원시 권선구, ...), but every
single one of the 71 SIGUNGU-scope rows in the real welfare-service CSV
uses only the parent city/county name. Selecting a sub-district therefore
used to silently HARD-exclude every real, eligible city-wide service for
that city -- confirmed here with the actual dataset (WLF00002047, 전주시).
"""

from recommender.filters import apply_hard_filters
from recommender.matcher import evaluate_region
from recommender.models import MatchStatus, RegionScope

from .conftest import make_service, make_user


def test_sigungu_service_matches_user_sub_district_of_same_city():
    service = make_service(sido="경기도", sigungu="화성시", region_scope=RegionScope.SIGUNGU)
    user = make_user(sido="경기도", sigungu="화성시 동탄구")
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.MATCH
    assert check.score_signal > 0  # still counts as full region-precision credit


def test_sigungu_service_still_excludes_a_genuinely_different_city():
    service = make_service(sido="경기도", sigungu="화성시", region_scope=RegionScope.SIGUNGU)
    user = make_user(sido="경기도", sigungu="수원시 권선구")
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.MISMATCH


def test_sigungu_service_still_excludes_different_city_without_sub_district():
    service = make_service(sido="경기도", sigungu="화성시", region_scope=RegionScope.SIGUNGU)
    user = make_user(sido="경기도", sigungu="수원시")
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.MISMATCH


def test_exact_match_without_sub_district_still_works_unchanged():
    service = make_service(sido="경기도", sigungu="화성시", region_scope=RegionScope.SIGUNGU)
    user = make_user(sido="경기도", sigungu="화성시")
    check = evaluate_region(user, service)
    assert check.status is MatchStatus.MATCH
    assert check.score_signal > 0


def test_real_jeonju_service_no_longer_hard_excluded_for_a_sub_district_user(all_services):
    """WLF00002047 (저소득 거동불편 장애인도시락배달, 전주시, meal_support)
    is real, city-scoped data -- before the fix, a 전주시 덕진구 resident
    would never see it even though it applies to all of 전주시."""
    service = next(s for s in all_services if s.service_id == "WLF00002047")
    assert service.sigungu == "전주시"  # confirms the real data has no sub-district granularity

    user = make_user(sido="전북특별자치도", sigungu="전주시 덕진구")
    result = apply_hard_filters(user, service)
    assert result.region_check.status is not MatchStatus.MISMATCH
