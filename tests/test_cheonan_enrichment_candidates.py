"""Cheonan enrichment candidates (docs/cheonan_official_enrichment_report.md).

Validates the two user-verified Cheonan records living in
data/processed/welfare_services_enrichment_cheonan_verified.csv -- a
SEPARATE candidate file, NOT merged into welfare_services_recommendation_ready.csv.
These tests exercise that file directly plus the classification decisions
made from the official text (no schema change, no recommender modification).
"""

from pathlib import Path

from recommender.loader import load_services
from recommender.models import DesiredSupport, MatchLevel, TriState
from recommender.recommender import recommend

from .conftest import make_user

NEW_CSV = Path("data/processed/welfare_services_enrichment_cheonan_verified.csv")


def _load_new():
    return {s.service_id: s for s in load_services(csv_path=NEW_CSV)}


def test_file_loads_as_two_valid_service_records():
    services = _load_new()
    assert set(services) == {"ENR-CHEONAN-01", "ENR-CHEONAN-02"}


def test_service_a_does_not_claim_meal_support():
    a = _load_new()["ENR-CHEONAN-01"]
    assert "meal_support" not in a.service_type
    assert a.low_income_required is TriState.TRUE
    assert a.min_age == 65


def test_service_a_has_no_institutional_gate():
    a = _load_new()["ENR-CHEONAN-01"]
    assert a.special_eligibility_required is TriState.FALSE


def test_service_b_does_not_equate_nutrition_support_with_meal_support():
    b = _load_new()["ENR-CHEONAN-02"]
    assert "meal_support" not in b.service_type
    assert b.nutrition_relevance == "SUPPORTIVE_NUTRITION"


def test_service_b_disability_is_unknown_not_true():
    """장애인 is one of several parallel target categories (not the sole
    requirement) -- same convention as the existing WLF00006261 precedent,
    per recommendation_data_readiness.md's disability_required rule."""
    b = _load_new()["ENR-CHEONAN-02"]
    assert b.disability_required is TriState.UNKNOWN


def test_service_b_carries_discharge_support_tag():
    b = _load_new()["ENR-CHEONAN-02"]
    assert "discharge_support" in b.service_type
    assert "community_care" in b.service_type


def test_service_b_gated_by_special_eligibility_procedure():
    """통합판정(건보공단) + 통합지원회의 gate -- mirrors WLF00003248's
    장기요양등급 판정 precedent. This is what keeps disability/discharge
    signals from ever producing an unconditional HIGH_MATCH."""
    b = _load_new()["ENR-CHEONAN-02"]
    assert b.special_eligibility_required is TriState.TRUE
    assert "통합판정" in b.special_eligibility_note or "통합 판정" in b.special_eligibility_note


def test_service_b_never_reaches_high_match_from_disability_alone():
    services = list(_load_new().values())
    user = make_user(
        sido="충청남도", sigungu="천안시", age=60,
        has_disability=TriState.TRUE,
        desired_support=frozenset({DesiredSupport.COMMUNITY_CARE}),
    )
    results = recommend(user, services=services, top_k=5)
    b_result = next(r for r in results if r.service_id == "ENR-CHEONAN-02")
    assert b_result.match_level is not MatchLevel.HIGH_MATCH
    assert b_result.confirmation_needed  # non-empty: special eligibility always flags


def test_service_a_hard_excludes_under_65_with_no_alternate_path():
    services = list(_load_new().values())
    user = make_user(
        sido="충청남도", sigungu="천안시", age=60,
        low_income_status=TriState.TRUE,
        desired_support=frozenset({DesiredSupport.COMMUNITY_CARE}),
    )
    results = recommend(user, services=services, top_k=5)
    assert all(r.service_id != "ENR-CHEONAN-01" for r in results)
