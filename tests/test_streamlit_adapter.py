"""Tests for streamlit_ui.adapter -- the UI <-> recommender translation
layer. No Streamlit runtime is involved; these are plain function tests."""

from pathlib import Path

import pytest

from recommender.models import DesiredSupport, MatchLevel, TriState
from streamlit_ui import adapter


def test_answer_to_tristate_maps_all_three_labels():
    assert adapter.answer_to_tristate("예") is TriState.TRUE
    assert adapter.answer_to_tristate("아니오") is TriState.FALSE
    assert adapter.answer_to_tristate("잘 모르겠어요") is TriState.UNKNOWN


def test_answer_to_tristate_unrecognized_defaults_to_unknown_not_false():
    assert adapter.answer_to_tristate(None) is TriState.UNKNOWN
    assert adapter.answer_to_tristate("") is TriState.UNKNOWN
    assert adapter.answer_to_tristate("아무말") is TriState.UNKNOWN


def test_labels_to_desired_support_round_trip():
    labels = ["식사/도시락/반찬 지원", "지역사회 통합돌봄"]
    result = adapter.labels_to_desired_support(labels)
    assert result == frozenset({DesiredSupport.MEAL_SUPPORT, DesiredSupport.COMMUNITY_CARE})


def test_labels_to_desired_support_unsure():
    result = adapter.labels_to_desired_support(["어떤 도움이 필요한지 모르겠어요"])
    assert result == frozenset({DesiredSupport.UNSURE})


def test_labels_to_desired_support_ignores_unknown_labels():
    assert adapter.labels_to_desired_support(["존재하지 않는 옵션"]) == frozenset()


def test_match_level_labels_are_possibility_phrased_not_confirmed():
    for level in MatchLevel:
        label = adapter.match_level_label(level)
        for forbidden in ("신청 가능", "자격 있음", "수급 가능", "확정"):
            assert forbidden not in label


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("  ", None),
        ("abc", None),
        ("-5", None),
        ("999", None),
        ("75", 75),
        (" 68 ", 68),
        ("0", 0),
        ("130", 130),
    ],
)
def test_parse_age(raw, expected):
    assert adapter.parse_age(raw) == expected


def test_build_user_profile_placeholder_region_becomes_none():
    profile = adapter.build_user_profile(
        sido_label=adapter.NO_SIDO_SELECTED,
        sigungu_label=adapter.NO_SIGUNGU_SELECTED,
        age_raw="75",
        disability_answer="예",
        low_income_answer="잘 모르겠어요",
        lives_alone_answer="예",
        mobility_answer="아니오",
        meal_prep_answer="예",
        recent_discharge_answer="잘 모르겠어요",
        desired_support_selected_labels=["식사/도시락/반찬 지원"],
    )
    assert profile.sido is None
    assert profile.sigungu is None
    assert profile.age == 75
    assert profile.has_disability is TriState.TRUE
    assert profile.low_income_status is TriState.UNKNOWN
    assert profile.lives_alone is TriState.TRUE
    assert profile.mobility_difficulty is TriState.FALSE
    assert profile.desired_support == frozenset({DesiredSupport.MEAL_SUPPORT})
    assert profile.respondent_type == "self"


def test_build_user_profile_real_region_and_caregiver():
    profile = adapter.build_user_profile(
        sido_label="강원특별자치도",
        sigungu_label="속초시",
        age_raw="80",
        disability_answer="잘 모르겠어요",
        low_income_answer="잘 모르겠어요",
        lives_alone_answer="잘 모르겠어요",
        mobility_answer="잘 모르겠어요",
        meal_prep_answer="잘 모르겠어요",
        recent_discharge_answer="잘 모르겠어요",
        desired_support_selected_labels=[],
        respondent_label=adapter.RESPONDENT_CAREGIVER,
    )
    assert profile.sido == "강원특별자치도"
    assert profile.sigungu == "속초시"
    assert profile.respondent_type == "caregiver"


def test_load_region_options_reads_real_csv_and_matches_service_sido_values():
    options = adapter.load_region_options()
    assert "강원특별자치도" in options
    assert "속초시" in options["강원특별자치도"]
    # every sido list must be non-empty and de-duplicated
    for sido, sigungu_list in options.items():
        assert len(sigungu_list) == len(set(sigungu_list))
        assert len(sigungu_list) > 0


def test_load_region_options_missing_file_raises_region_data_error(tmp_path):
    missing = tmp_path / "does_not_exist.csv"
    with pytest.raises(adapter.RegionDataError):
        adapter.load_region_options(missing)


def test_load_region_options_malformed_file_raises_region_data_error(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("wrong,columns\n1,2\n", encoding="utf-8")
    with pytest.raises(adapter.RegionDataError):
        adapter.load_region_options(bad)


def test_scarce_support_warning_only_when_every_choice_is_scarce(all_services):
    only_scarce = frozenset({DesiredSupport.NUTRITION_COUNSELING})
    mixed = frozenset({DesiredSupport.NUTRITION_COUNSELING, DesiredSupport.MEAL_SUPPORT})

    assert adapter.scarce_support_warning(only_scarce, all_services) is not None
    assert adapter.scarce_support_warning(mixed, all_services) is None


def test_scarce_support_warning_none_for_unsure_or_common_choice(all_services):
    assert adapter.scarce_support_warning(frozenset({DesiredSupport.UNSURE}), all_services) is None
    assert (
        adapter.scarce_support_warning(frozenset({DesiredSupport.MEAL_SUPPORT}), all_services)
        is None
    )


def test_sparse_input_notice_triggers_when_region_missing():
    profile = adapter.build_user_profile(
        sido_label=None,
        sigungu_label=None,
        age_raw="75",
        disability_answer="예",
        low_income_answer="예",
        lives_alone_answer="예",
        mobility_answer="예",
        meal_prep_answer="예",
        recent_discharge_answer="예",
        desired_support_selected_labels=["식사/도시락/반찬 지원"],
    )
    assert adapter.sparse_input_notice(profile) is not None


def test_service_type_tag_label_known_and_unknown_tags():
    assert adapter.service_type_tag_label("meal_support") == "식사/도시락/반찬 지원"
    assert adapter.service_type_tag_label("not_a_real_tag") == "not_a_real_tag"


def test_verification_and_nutritionist_labels_never_expose_raw_unknown_as_blank():
    assert "A" in adapter.verification_level_label("A")
    assert "B" in adapter.verification_level_label("B")
    assert adapter.verification_level_label("") == "확인 안 됨"
    assert adapter.nutritionist_involvement_label("direct") != "direct"
    assert adapter.nutritionist_involvement_label("") == "정보 없음"


def test_sparse_input_notice_silent_for_rich_input():
    profile = adapter.build_user_profile(
        sido_label="강원특별자치도",
        sigungu_label="속초시",
        age_raw="75",
        disability_answer="예",
        low_income_answer="예",
        lives_alone_answer="예",
        mobility_answer="예",
        meal_prep_answer="예",
        recent_discharge_answer="아니오",
        desired_support_selected_labels=["식사/도시락/반찬 지원"],
    )
    assert adapter.sparse_input_notice(profile) is None
