"""Pure translation functions between Streamlit widget values and the
recommender package's typed inputs (docs/recommendation_rules_spec.md §2).

No matching, filtering, or scoring logic lives here -- only string/label
<-> Enum conversion, input parsing, and small UI-only advisory messages
(e.g. "your input is sparse") that never feed back into the engine.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from recommender.models import (
    DesiredSupport,
    MatchLevel,
    SERVICE_TYPE_TAGS,
    ServiceRecord,
    TriState,
    UserProfile,
)

# ---------------------------------------------------------------------------
# Tri-state 예 / 아니오 / 잘 모르겠어요
# ---------------------------------------------------------------------------

ANSWER_YES = "예"
ANSWER_NO = "아니오"
ANSWER_UNKNOWN = "잘 모르겠어요"

TRISTATE_ANSWER_OPTIONS: List[str] = [ANSWER_YES, ANSWER_NO, ANSWER_UNKNOWN]
DEFAULT_TRISTATE_ANSWER = ANSWER_UNKNOWN  # never default to a committal answer

_ANSWER_TO_TRISTATE = {
    ANSWER_YES: TriState.TRUE,
    ANSWER_NO: TriState.FALSE,
    ANSWER_UNKNOWN: TriState.UNKNOWN,
}


def answer_to_tristate(answer: Optional[str]) -> TriState:
    """UI label -> TriState. Anything unrecognized safely defaults to
    UNKNOWN rather than guessing TRUE or FALSE."""
    return _ANSWER_TO_TRISTATE.get(answer, TriState.UNKNOWN)


# ---------------------------------------------------------------------------
# 원하는 도움 (desired_support)
# ---------------------------------------------------------------------------

# Order matches docs/recommendation_rules_spec.md §8's mapping table. Scarce
# options are NOT hidden (per instructions §6/§11) -- they stay selectable,
# and the UI separately warns the user that results may be thin.
DESIRED_SUPPORT_OPTIONS: List[Tuple[str, DesiredSupport]] = [
    ("식사/도시락/반찬 지원", DesiredSupport.MEAL_SUPPORT),
    ("식비/식재료 지원", DesiredSupport.FOOD_COST_SUPPORT),
    ("방문형 도움", DesiredSupport.HOME_VISIT),
    ("지역사회 통합돌봄", DesiredSupport.COMMUNITY_CARE),
    ("퇴원 후 지원", DesiredSupport.DISCHARGE_SUPPORT),
    ("영양상담", DesiredSupport.NUTRITION_COUNSELING),
    ("어떤 도움이 필요한지 모르겠어요", DesiredSupport.UNSURE),
]

# rules_spec.md §0/§8: these two have almost no matching service_type data
# in the current 85-row dataset (nutrition_counseling has 0 service_type
# tags at all; discharge_support has exactly 1 row).
DATA_SCARCE_SUPPORT = {DesiredSupport.NUTRITION_COUNSELING, DesiredSupport.DISCHARGE_SUPPORT}

_LABEL_BY_SUPPORT = {support: label for label, support in DESIRED_SUPPORT_OPTIONS}
_SUPPORT_BY_LABEL = {label: support for label, support in DESIRED_SUPPORT_OPTIONS}


def desired_support_labels() -> List[str]:
    return [label for label, _ in DESIRED_SUPPORT_OPTIONS]


def labels_to_desired_support(labels: Sequence[str]) -> frozenset:
    return frozenset(_SUPPORT_BY_LABEL[l] for l in labels if l in _SUPPORT_BY_LABEL)


def _support_service_count(support: DesiredSupport, services: Sequence[ServiceRecord]) -> int:
    if support.value in SERVICE_TYPE_TAGS:
        return sum(1 for s in services if support.value in s.service_type)
    if support is DesiredSupport.NUTRITION_COUNSELING:
        return sum(1 for s in services if s.nutritionist_involvement == "direct")
    return 0


def scarce_support_warning(
    desired: frozenset, services: Sequence[ServiceRecord]
) -> Optional[str]:
    """Returns a warning message only when EVERY concrete choice the user
    made is one of the data-scarce categories (instructions §11) -- if the
    user also picked a well-covered option, no blanket warning is shown.
    """
    effective = {d for d in desired if d is not DesiredSupport.UNSURE}
    if not effective:
        return None
    if not effective.issubset(DATA_SCARCE_SUPPORT):
        return None
    parts = []
    for support in effective:
        count = _support_service_count(support, services)
        parts.append(f"{_LABEL_BY_SUPPORT[support]}(현재 데이터 {count}건)")
    return (
        "선택하신 도움 유형(" + ", ".join(parts) + ")에 해당하는 공공서비스 데이터가 "
        "현재 충분하지 않아요. 조건에 맞는 결과가 거의 없거나 부족할 수 있어요."
    )


# ---------------------------------------------------------------------------
# Match level -> 사용자 문구 (확정적 표현 금지)
# ---------------------------------------------------------------------------

MATCH_LEVEL_LABELS: Dict[MatchLevel, str] = {
    MatchLevel.HIGH_MATCH: "관련성이 높은 서비스",
    MatchLevel.POSSIBLE_MATCH: "확인해볼 만한 서비스",
    MatchLevel.NEEDS_CONFIRMATION: "추가 조건 확인이 필요한 서비스",
}


def match_level_label(level: MatchLevel) -> str:
    return MATCH_LEVEL_LABELS.get(level, level.value)


def service_type_tag_label(tag: str) -> str:
    """Raw service_type tag (e.g. "meal_support") -> Korean display label,
    reusing the same wording as the desired_support options so the two
    line up visually for the user."""
    try:
        return _LABEL_BY_SUPPORT[DesiredSupport(tag)]
    except ValueError:
        return tag


# ---------------------------------------------------------------------------
# 표시 전용 문구 정리 (UI wording cleanup) -- recommender.py가 이미 만들어 둔
# 문장(recommendation_reasons/exclusion_warnings) 안에 그대로 섞여 나오는
# 내부 key(raw service_type 태그, CSV의 "_original" 필드명)를 화면에 보여줄
# 때만 자연스러운 한국어로 치환한다. recommender.py의 값/로직/데이터는 전혀
# 건드리지 않는다 -- 오직 이미 이 화면 다른 곳에서도 쓰고 있는 한글 라벨로
# 렌더링 시점에만 바꿔치기한다. 의미가 불분명한 다른 내부 key(예:
# eligibility_summary, 데이터 출처 provenance 메모의 영문 key=value 조각)는
# 임의로 번역하지 않고 그대로 둔다.
# ---------------------------------------------------------------------------

# CSV의 "_original" 필드명 -> 이 화면의 "자세히 보기" 섹션 제목("지원
# 대상"/"선정 기준"/"지원 내용"/"신청 방법")에 이미 쓰고 있는 한글 표현 + "원문".
# 새 의미를 만들지 않고 기존 UI 라벨을 그대로 재사용한 것이다.
_RAW_FIELD_NAME_DISPLAY_LABELS: Dict[str, str] = {
    "target_original": "지원 대상 원문",
    "criteria_original": "선정 기준 원문",
    "support_original": "지원 내용 원문",
    "application_original": "신청 방법 원문",
}

# service_type 태그 -> 한글 라벨. "④ 서비스 유형"/"원하는 도움"에서 이미 쓰는
# _LABEL_BY_SUPPORT를 그대로 재사용해 같은 태그가 화면 어디서나 동일하게
# 보이도록 한다.
_RAW_TOKEN_DISPLAY_LABELS: Dict[str, str] = {
    **{support.value: label for label, support in DESIRED_SUPPORT_OPTIONS},
    **_RAW_FIELD_NAME_DISPLAY_LABELS,
}

# 앞뒤가 영문/숫자/밑줄이 아닐 때만 매치 -- Python \b는 한글도 "단어 문자"로
# 취급해 "target_original과"처럼 한국어 조사가 바로 붙는 흔한 경우를 놓치므로
# ASCII word-char 기준의 lookaround를 직접 쓴다.
_RAW_TOKEN_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_])("
    + "|".join(re.escape(tok) for tok in sorted(_RAW_TOKEN_DISPLAY_LABELS, key=len, reverse=True))
    + r")(?![A-Za-z0-9_])"
)


def humanize_internal_tokens(text: str) -> str:
    """문장 속에 섞인 raw 내부 key만 한글 표시 라벨로 치환해 반환한다.

    recommendation_reasons/exclusion_warnings처럼 recommender.py가 이미
    완성해 둔 한국어 문장을 화면에 그대로 옮기기 직전에만 호출한다 -- 이
    함수는 recommender의 값이나 정렬 순서에 전혀 관여하지 않는, 순수한
    표시용 문자열 치환이다. 매핑에 없는 토큰은 그대로 둔다.
    """
    if not text:
        return text
    return _RAW_TOKEN_PATTERN.sub(lambda m: _RAW_TOKEN_DISPLAY_LABELS[m.group(0)], text)


VERIFICATION_LEVEL_LABELS: Dict[str, str] = {
    "A": "A (정보가 비교적 상세하게 확인됨)",
    "B": "B (일부 정보가 부족함)",
}


def verification_level_label(code: str) -> str:
    return VERIFICATION_LEVEL_LABELS.get(code, code or "확인 안 됨")


NUTRITIONIST_INVOLVEMENT_LABELS: Dict[str, str] = {
    "direct": "영양사가 직접 참여하는 것으로 확인돼요",
    "not_specified": "영양사 참여 여부가 원문에 명시되어 있지 않아요",
}


def nutritionist_involvement_label(code: str) -> str:
    return NUTRITIONIST_INVOLVEMENT_LABELS.get(code, code or "정보 없음")


# ---------------------------------------------------------------------------
# Region options (sido -> sigungu list), sourced only from
# data/processed/region_codes.csv -- never hardcoded.
# ---------------------------------------------------------------------------

DEFAULT_REGION_CODES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "processed" / "region_codes.csv"
)

NO_SIDO_SELECTED = "-- 시/도를 선택해주세요 --"
NO_SIGUNGU_SELECTED = "-- 해당 없음 / 잘 모르겠어요 --"


class RegionDataError(Exception):
    """Raised when region_codes.csv is missing or malformed."""


def load_region_options(path: Path = DEFAULT_REGION_CODES_PATH) -> Dict[str, List[str]]:
    """sido_name -> sorted list of sigungu_name, read from region_codes.csv.

    Raises RegionDataError (caught by the Streamlit app, never a raw
    traceback) if the file is missing or has no usable rows.
    """
    path = Path(path)
    if not path.exists():
        raise RegionDataError(f"지역 코드 파일을 찾을 수 없어요: {path}")

    options: Dict[str, List[str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "sido_name" not in reader.fieldnames or "sigungu_name" not in reader.fieldnames:
            raise RegionDataError(
                f"{path} 형식이 예상과 달라요 (sido_name/sigungu_name 컬럼 필요)."
            )
        for row in reader:
            sido = (row.get("sido_name") or "").strip()
            sigungu = (row.get("sigungu_name") or "").strip()
            if not sido or not sigungu:
                continue
            options.setdefault(sido, []).append(sigungu)

    if not options:
        raise RegionDataError(f"{path}에서 지역 목록을 읽지 못했어요.")

    for sido in options:
        options[sido] = sorted(set(options[sido]))
    return options


# ---------------------------------------------------------------------------
# Age parsing
# ---------------------------------------------------------------------------


def parse_age(raw: Optional[str]) -> Optional[int]:
    """Returns None for empty/invalid input rather than raising -- age is
    required by the design, but a bad value must degrade to "unknown", not
    crash the app (instructions §16)."""
    if raw is None:
        return None
    text = str(raw).strip()
    if text == "":
        return None
    try:
        value = int(text)
    except ValueError:
        return None
    if value < 0 or value > 130:
        return None
    return value


# ---------------------------------------------------------------------------
# Respondent type (tone-only, never used in matching -- design doc §2)
# ---------------------------------------------------------------------------

RESPONDENT_SELF = "본인"
RESPONDENT_CAREGIVER = "보호자/가족"
RESPONDENT_OPTIONS = [RESPONDENT_SELF, RESPONDENT_CAREGIVER]


# ---------------------------------------------------------------------------
# UserProfile assembly
# ---------------------------------------------------------------------------


def build_user_profile(
    *,
    sido_label: Optional[str],
    sigungu_label: Optional[str],
    age_raw: Optional[str],
    disability_answer: str,
    low_income_answer: str,
    lives_alone_answer: str,
    mobility_answer: str,
    meal_prep_answer: str,
    recent_discharge_answer: str,
    desired_support_selected_labels: Sequence[str],
    respondent_label: str = RESPONDENT_SELF,
    meal_skipping_answer: str = DEFAULT_TRISTATE_ANSWER,
    grocery_shopping_answer: str = DEFAULT_TRISTATE_ANSWER,
    diet_management_answer: str = DEFAULT_TRISTATE_ANSWER,
) -> UserProfile:
    sido = None if sido_label in (None, "", NO_SIDO_SELECTED) else sido_label
    sigungu = None if sigungu_label in (None, "", NO_SIGUNGU_SELECTED) else sigungu_label

    return UserProfile(
        sido=sido,
        sigungu=sigungu,
        age=parse_age(age_raw),
        has_disability=answer_to_tristate(disability_answer),
        low_income_status=answer_to_tristate(low_income_answer),
        lives_alone=answer_to_tristate(lives_alone_answer),
        mobility_difficulty=answer_to_tristate(mobility_answer),
        meal_preparation_difficulty=answer_to_tristate(meal_prep_answer),
        recent_discharge=answer_to_tristate(recent_discharge_answer),
        frequent_meal_skipping=answer_to_tristate(meal_skipping_answer),
        grocery_shopping_difficulty=answer_to_tristate(grocery_shopping_answer),
        needs_diet_management=answer_to_tristate(diet_management_answer),
        desired_support=labels_to_desired_support(desired_support_selected_labels),
        respondent_type="caregiver" if respondent_label == RESPONDENT_CAREGIVER else "self",
    )


# ---------------------------------------------------------------------------
# UI-only advisory messages (never change engine behavior or ranking)
# ---------------------------------------------------------------------------


def sparse_input_notice(user: UserProfile) -> Optional[str]:
    """instructions §12/§13: warn (not block) when input is too thin to be
    informative, and mention the NATIONAL-service tie-break artifact
    documented in recommendation_engine_v1_report.md §9/§11.
    """
    tri_fields = [
        user.has_disability,
        user.low_income_status,
        user.lives_alone,
        user.mobility_difficulty,
        user.meal_preparation_difficulty,
    ]
    unknown_count = sum(1 for f in tri_fields if f is TriState.UNKNOWN)
    is_unsure_support = not user.effective_desired_support()

    sparse = user.sido is None or unknown_count >= 4 or (unknown_count >= 3 and is_unsure_support)
    if not sparse:
        return None

    message = (
        "입력하신 정보가 적어 추천 정확도가 낮을 수 있어요. "
        "'추가 조건 확인이 필요한 서비스'가 많이 나올 수 있습니다."
    )
    if user.sido is None:
        message += " 거주 지역 정보가 없으면 전국 단위 서비스가 상위에 표시될 수 있어요."
    return message


# 영양·식생활 상황 요약 (결과 화면 참고용). ranking/match_level에는 전혀
# 영향을 주지 않는다 -- 사용자가 무엇을 입력했는지 그대로 다시 보여줄 뿐이다.
# "예"로 답한 항목만 나열한다("아니요"/"잘 모르겠어요"는 보여줄 특별한
# 상황이 없으므로 생략). 임상적 판단 문구("영양위험", "영양불량")는 쓰지 않는다.
_NUTRITION_SITUATION_LABELS: List[Tuple[str, str]] = [
    ("frequent_meal_skipping", "최근 식사를 자주 거름"),
    ("grocery_shopping_difficulty", "장보기가 어려움"),
    ("meal_preparation_difficulty", "직접 음식을 준비하기 어려움"),
    ("needs_diet_management", "질환 때문에 식사관리가 필요하다고 느낌"),
]


def nutrition_situation_summary(user: UserProfile) -> List[str]:
    """"예"로 답한 영양·식생활 상황 문구만 반환. 아무것도 없으면 빈 리스트."""
    return [
        label
        for field_name, label in _NUTRITION_SITUATION_LABELS
        if getattr(user, field_name) is TriState.TRUE
    ]


def nutrition_counseling_suggested(user: UserProfile) -> bool:
    """"영양상담도 함께 확인해보세요" 안내 카드를 보여줄지 여부만 결정한다.

    ``nutrition_situation_summary``와 정확히 같은 4개 항목(최근 식사를
    자주 거름 / 장보기 어려움 / 직접 음식 준비 어려움 / 질환으로 식사관리
    필요)을 신호로 쓴다 -- 그중 하나라도 "예"면 True. 영양상태를 진단하거나
    상담 필요 여부를 확정 판정하는 기능이 아니라 안내 노출 여부만 결정하는
    UI 전용 판단이며, 추천 ranking/match_level에는 전혀 관여하지 않는다.
    """
    return bool(nutrition_situation_summary(user))


def few_candidates_notice(result_count: int, top_k: int) -> Optional[str]:
    """instructions(v1.2) §14: when fewer than top_k results are shown,
    make clear this can be a normal reflection of limited service data for
    the user's exact region/conditions -- not a system error. Only fires
    when there's something to explain (1..top_k-1 results); 0 results and a
    full top_k each already read as self-explanatory.
    """
    if result_count <= 0 or result_count >= top_k:
        return None
    return (
        f"현재 입력 조건에서 확인 가능한 등록 서비스가 {result_count}건으로 많지 않아요. "
        "이는 시스템 오류가 아니라, 현재 확보된 공공서비스 데이터의 지역별 차이 때문일 수 "
        "있어요. 거주 시/군/구를 비우고 같은 시/도의 더 넓은 범위에서 다시 찾아보실 수도 있어요."
    )
