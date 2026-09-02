"""Typed data structures for the rule-based recommendation engine.

Everything here mirrors the vocabulary in ``docs/recommendation_rules_spec.md``
and the actual column values found in
``data/processed/welfare_services_recommendation_ready.csv``. Enum values are
kept as the exact lower-case strings already used in the CSV (``"true"``,
``"false"``, ``"unknown"``, ``"SIGUNGU"``, ...) so records can be parsed
without a translation table.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TriState(str, Enum):
    """The 3-state value used throughout the CSV and the user profile.

    UNKNOWN must never be treated as FALSE (rules_spec.md §5).
    """

    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"

    @classmethod
    def from_raw(cls, value: Optional[str]) -> "TriState":
        """Parse a raw CSV/user string into a TriState, defaulting to UNKNOWN.

        Anything empty, missing, or not recognised is UNKNOWN rather than
        FALSE -- an empty cell in this dataset means "not stated", not "no".
        """
        if value is None:
            return cls.UNKNOWN
        v = value.strip().lower()
        if v == "true":
            return cls.TRUE
        if v == "false":
            return cls.FALSE
        return cls.UNKNOWN


class MatchStatus(str, Enum):
    """Result of comparing one condition between a service and a user."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    UNKNOWN = "UNKNOWN"


class MatchLevel(str, Enum):
    """Possibility-based recommendation tiers (rules_spec.md §10).

    Deliberately excludes any wording implying confirmed eligibility.
    """

    HIGH_MATCH = "HIGH_MATCH"
    POSSIBLE_MATCH = "POSSIBLE_MATCH"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


class RegionScope(str, Enum):
    """Values of the CSV ``region_scope`` column (rules_spec.md §6)."""

    NATIONAL = "NATIONAL"
    SIDO = "SIDO"
    SIGUNGU = "SIGUNGU"
    UNKNOWN = "UNKNOWN"  # defensive value, not present in the current 85 rows

    @classmethod
    def from_raw(cls, value: Optional[str]) -> "RegionScope":
        if not value:
            return cls.UNKNOWN
        v = value.strip().upper()
        if v in (cls.NATIONAL.value, cls.SIDO.value, cls.SIGUNGU.value):
            return cls(v)
        return cls.UNKNOWN


class AgeConditionType(str, Enum):
    """Values of the CSV ``age_condition_type`` column (rules_spec.md §7)."""

    SIMPLE_MIN = "SIMPLE_MIN"
    SIMPLE_RANGE = "SIMPLE_RANGE"  # defined for the future; 0 rows use it today
    COMPOUND = "COMPOUND"
    NONE = "NONE"

    @classmethod
    def from_raw(cls, value: Optional[str]) -> "AgeConditionType":
        if not value:
            return cls.NONE
        v = value.strip().upper()
        for member in cls:
            if v == member.value:
                return member
        return cls.NONE


class DesiredSupport(str, Enum):
    """Options the user can pick for "what kind of help do you need".

    Values line up with the actual ``service_type`` tags found in the CSV
    (``meal_support`` / ``food_cost_support`` / ``community_care`` /
    ``home_visit`` / ``discharge_support``). ``nutrition_counseling`` has NO
    matching ``service_type`` tag in the current 85 rows -- see
    rules_spec.md §0/§8 -- it is matched only via ``nutritionist_involvement``
    / ``nutrition_relevance`` as a much weaker, conditional signal.
    """

    MEAL_SUPPORT = "meal_support"
    FOOD_COST_SUPPORT = "food_cost_support"
    NUTRITION_COUNSELING = "nutrition_counseling"
    HOME_VISIT = "home_visit"
    COMMUNITY_CARE = "community_care"
    DISCHARGE_SUPPORT = "discharge_support"
    UNSURE = "unsure"


# service_type tags that actually exist in service_type column values
SERVICE_TYPE_TAGS = {
    "meal_support",
    "food_cost_support",
    "community_care",
    "home_visit",
    "discharge_support",
}


# ---------------------------------------------------------------------------
# User input
# ---------------------------------------------------------------------------


@dataclass
class UserProfile:
    """User/caregiver input, matching recommendation_rules_spec.md §2."""

    sido: Optional[str] = None
    sigungu: Optional[str] = None
    age: Optional[int] = None

    has_disability: TriState = TriState.UNKNOWN
    low_income_status: TriState = TriState.UNKNOWN
    lives_alone: TriState = TriState.UNKNOWN
    mobility_difficulty: TriState = TriState.UNKNOWN
    meal_preparation_difficulty: TriState = TriState.UNKNOWN
    recent_discharge: TriState = TriState.UNKNOWN

    # 영양·식생활 상황 정보 (UI 질문 보강, "영양·식생활 상황 확인" 작업).
    # 85건 production 서비스 데이터에는 이 세 항목에 직접 대응하는 공식
    # 자격조건/서비스 특성 컬럼이 없다 -- 그래서 filters.py/scorer.py 어디서도
    # 참조하지 않는다 (rules_spec.md §14 anti-gaming rule과 동일한 원칙:
    # 근거 없는 필드를 추천점수에 반영하지 않는다). 사용자 상황 정보로만
    # 저장하고, 결과 화면 요약과 향후 영양상담 서비스 연결 확장에만 쓴다.
    frequent_meal_skipping: TriState = TriState.UNKNOWN
    grocery_shopping_difficulty: TriState = TriState.UNKNOWN
    needs_diet_management: TriState = TriState.UNKNOWN

    desired_support: frozenset = field(default_factory=frozenset)

    # Not used in matching at all -- tone/phrasing only (design doc §2).
    respondent_type: str = "self"

    def __post_init__(self) -> None:
        if self.sido is not None:
            self.sido = self.sido.strip() or None
        if self.sigungu is not None:
            self.sigungu = self.sigungu.strip() or None
        # normalize desired_support to a frozenset of DesiredSupport
        normalized = set()
        for item in self.desired_support:
            if isinstance(item, DesiredSupport):
                normalized.add(item)
            else:
                normalized.add(DesiredSupport(str(item)))
        self.desired_support = frozenset(normalized)

    def effective_desired_support(self) -> frozenset:
        """desired_support with UNSURE treated as "no specific preference".

        Per rules_spec.md §8: selecting "잘 모르겠음" (unsure) means "show
        everything, no scoring boost", so it never counts as a concrete
        preference even if selected alongside other options.
        """
        if not self.desired_support or DesiredSupport.UNSURE in self.desired_support:
            return frozenset()
        return self.desired_support


# ---------------------------------------------------------------------------
# Service record (one CSV row, typed)
# ---------------------------------------------------------------------------


@dataclass
class ServiceRecord:
    """One row of welfare_services_recommendation_ready.csv, typed."""

    service_id: str
    service_name: str
    source_api: str

    sido: Optional[str]
    sigungu: Optional[str]
    region_scope: RegionScope

    min_age: Optional[int]
    max_age: Optional[int]
    age_condition_type: AgeConditionType
    age_condition_note: str

    disability_required: TriState
    low_income_required: TriState
    single_household_required: TriState
    homebound_or_mobility_condition: TriState

    service_type: frozenset  # set of raw tag strings, e.g. {"meal_support"}
    service_type_primary: str

    nutritionist_involvement: str
    nutrition_relevance: str
    verification_level: str

    contact: str
    application_original: str
    target_original: str
    criteria_original: str
    support_original: str
    eligibility_summary: str
    support_summary: str
    data_quality_note: str

    # v1.2 addition (recommendation_engine_v1_2_validation.md §7-8): whether
    # this service's real eligibility gate is an institutionally-certified
    # special-population status (e.g. 국가유공자/보훈 registration, a formal
    # 장기요양등급 판정) that none of the other structured HARD-gate fields
    # represent. Verified by direct reading of target_original/
    # criteria_original for all 85 rows -- only 2 rows are TRUE (see the
    # report's special eligibility audit); every other row is UNKNOWN
    # (blank cell), never FALSE, since the audit did not exhaustively rule
    # out every row.
    special_eligibility_required: TriState
    special_eligibility_note: str

    def region_label(self) -> dict:
        return {
            "sido": self.sido,
            "sigungu": self.sigungu,
            "region_scope": self.region_scope.value,
        }


# ---------------------------------------------------------------------------
# Per-condition comparison outcome
# ---------------------------------------------------------------------------


@dataclass
class ConditionCheck:
    """One condition comparison result, always carrying a human reason.

    ``confirmation_needed`` is True only for the specific matrix cell where
    the service states a requirement but the user's answer is UNKNOWN
    (rules_spec.md §5, row 3) -- the one case where there is something
    concrete for the user to go check.
    """

    field: str
    status: MatchStatus
    reason: str
    confirmation_needed: bool = False
    score_signal: int = 0  # -1 / 0 / +1, used only by SOFT-class fields

    def as_dict(self) -> dict:
        return {
            "field": self.field,
            "status": self.status.value,
            "reason": self.reason,
            "confirmation_needed": self.confirmation_needed,
        }


# ---------------------------------------------------------------------------
# Final recommendation result
# ---------------------------------------------------------------------------


@dataclass
class RecommendationResult:
    service_id: str
    service_name: str
    region: dict
    service_type: list

    match_score: float
    match_level: MatchLevel

    matched_conditions: list
    unknown_conditions: list
    exclusion_warnings: list
    confirmation_needed: list
    recommendation_reasons: list

    verification_level: str
    nutritionist_involvement: str

    # Used only for deterministic tie-breaking (recommender._sort_key) --
    # True when the region check matched down to an exact sigungu, not just
    # a broader SIDO/NATIONAL pass.
    region_exact_match: bool = False

    # Optional reference/info-only fields (rules_spec.md §11)
    support_summary: str = ""
    eligibility_summary: str = ""
    application_method: str = ""
    contact: str = ""
    target_original: str = ""
    criteria_original: str = ""

    def as_dict(self) -> dict:
        return {
            "service_id": self.service_id,
            "service_name": self.service_name,
            "region": self.region,
            "service_type": self.service_type,
            "match_score": self.match_score,
            "match_level": self.match_level.value,
            "matched_conditions": self.matched_conditions,
            "unknown_conditions": self.unknown_conditions,
            "exclusion_warnings": self.exclusion_warnings,
            "confirmation_needed": self.confirmation_needed,
            "recommendation_reasons": self.recommendation_reasons,
            "verification_level": self.verification_level,
            "nutritionist_involvement": self.nutritionist_involvement,
            "support_summary": self.support_summary,
            "eligibility_summary": self.eligibility_summary,
            "application_method": self.application_method,
            "contact": self.contact,
            "target_original": self.target_original,
            "criteria_original": self.criteria_original,
        }
