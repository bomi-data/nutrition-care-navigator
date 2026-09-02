"""Pure condition-comparison functions.

This module contains no filtering/scoring policy -- it only answers "given
this service condition and this user answer, what is the comparison result
and why". filters.py decides which results become hard exclusions;
scorer.py decides which results become score points. Keeping the comparison
logic itself free of that policy is what makes the 3x3 UNKNOWN matrix in
docs/recommendation_rules_spec.md §5 reusable for both HARD and SOFT fields.
"""

from __future__ import annotations

from typing import Optional

from .models import (
    AgeConditionType,
    ConditionCheck,
    MatchStatus,
    RegionScope,
    ServiceRecord,
    TriState,
    UserProfile,
)


# ---------------------------------------------------------------------------
# Generic 3x3 TRUE/FALSE/UNKNOWN matrix (rules_spec.md §5)
# ---------------------------------------------------------------------------


def evaluate_tristate(
    field: str,
    service_value: TriState,
    user_value: TriState,
    *,
    field_label_ko: str,
) -> ConditionCheck:
    """Compare one tri-state service condition against one user answer.

    Never returns MISMATCH for an UNKNOWN service condition, and never
    treats a user UNKNOWN answer as FALSE -- see the matrix table in
    rules_spec.md §5. ``score_signal`` follows the SOFT scoring column of
    that same table: +1 only on a genuine TRUE/TRUE match, -1 only on a
    genuine TRUE/FALSE mismatch, 0 everywhere else (rows where the service
    does not require the condition are treated as neutral for *scoring*,
    even though they still count as a gate PASS).
    """
    if service_value is TriState.TRUE:
        if user_value is TriState.TRUE:
            return ConditionCheck(
                field=field,
                status=MatchStatus.MATCH,
                reason=f"{field_label_ko} 조건에 해당하는 것으로 보여요.",
                confirmation_needed=False,
                score_signal=+1,
            )
        if user_value is TriState.FALSE:
            return ConditionCheck(
                field=field,
                status=MatchStatus.MISMATCH,
                reason=f"{field_label_ko} 조건이 맞지 않는 것으로 보여요.",
                confirmation_needed=False,
                score_signal=-1,
            )
        # user UNKNOWN
        return ConditionCheck(
            field=field,
            status=MatchStatus.UNKNOWN,
            reason=f"{field_label_ko} 조건은 이 서비스에서 요구하지만, 입력하신 정보로는 확인되지 않아요.",
            confirmation_needed=True,
            score_signal=0,
        )

    if service_value is TriState.FALSE:
        # Service does not require this condition -- gate always passes,
        # regardless of the user's answer. Neutral for scoring (rules_spec
        # §9: eligibility gates are not double-counted as ranking score).
        return ConditionCheck(
            field=field,
            status=MatchStatus.MATCH,
            reason=f"{field_label_ko} 조건은 이 서비스와 상관없어요.",
            confirmation_needed=False,
            score_signal=0,
        )

    # service_value is UNKNOWN: the service simply never states this
    # condition. Never MISMATCH, never asks for confirmation (there is
    # nothing concrete to confirm since the service itself is silent).
    return ConditionCheck(
        field=field,
        status=MatchStatus.UNKNOWN,
        reason=f"이 서비스는 {field_label_ko} 조건을 별도로 명시하지 않았어요.",
        confirmation_needed=False,
        score_signal=0,
    )


# ---------------------------------------------------------------------------
# Region (rules_spec.md §6)
# ---------------------------------------------------------------------------


def _sigungu_base(name: Optional[str]) -> Optional[str]:
    """Strip a "구" sub-district suffix, e.g. "화성시 동탄구" -> "화성시".

    v1.2 fix (recommendation_engine_v1_2_validation.md §region): region_codes
    .csv (the Streamlit dropdown's source) lists 39 sub-district entries for
    8+ major cities (화성시 동탄구/만세구/..., 전주시 덕진구/완산구, 수원시
    ...구, etc.), but every one of the 71 SIGUNGU-scope rows in the actual
    welfare-service CSV uses only the parent city/county name -- confirmed by
    checking the full dataset (0 rows contain a space in `sigungu`). A user
    selecting a sub-district therefore always fails the exact-string
    comparison below even when a real, eligible city-wide service exists,
    purely because of this granularity mismatch between the two datasets --
    not because the service is genuinely restricted to a different city.
    Comparing base city names closes that gap without weakening the gate for
    any row that actually differs by city/county (the common case).
    """
    if not name:
        return name
    return name.split(" ", 1)[0]


def evaluate_region(user: UserProfile, service: ServiceRecord) -> ConditionCheck:
    scope = service.region_scope

    if scope is RegionScope.NATIONAL:
        return ConditionCheck(
            field="region",
            status=MatchStatus.MATCH,
            reason="전국 대상 서비스로 지역 제한이 없어요.",
            confirmation_needed=False,
            score_signal=0,
        )

    if scope is RegionScope.UNKNOWN:
        # Defensive branch: not present in the current 85 rows, but never
        # auto-exclude on missing/garbled region_scope metadata.
        return ConditionCheck(
            field="region",
            status=MatchStatus.UNKNOWN,
            reason="이 서비스의 지역 적용 범위 정보가 불명확해 확인이 필요해요.",
            confirmation_needed=True,
            score_signal=0,
        )

    if user.sido is None:
        return ConditionCheck(
            field="region",
            status=MatchStatus.UNKNOWN,
            reason="거주 시/도 정보가 없어 지역 조건을 확인할 수 없어요.",
            confirmation_needed=True,
            score_signal=0,
        )

    if scope is RegionScope.SIDO:
        if service.sido == user.sido:
            return ConditionCheck(
                field="region",
                status=MatchStatus.MATCH,
                reason="거주 시/도가 일치해요.",
                confirmation_needed=False,
                score_signal=0,
            )
        return ConditionCheck(
            field="region",
            status=MatchStatus.MISMATCH,
            reason="거주 시/도가 이 서비스의 대상 지역과 달라요.",
            confirmation_needed=False,
            score_signal=0,
        )

    # scope is SIGUNGU
    if service.sigungu is None:
        # Defensive fallback -- readiness doc confirms 0 such rows today,
        # but if it ever happens, degrade to SIDO-level comparison rather
        # than crashing or wrongly excluding.
        if service.sido == user.sido:
            return ConditionCheck(
                field="region",
                status=MatchStatus.MATCH,
                reason="거주 시/도가 일치해요(시군구 정보 없음, 광역 단위로 확인).",
                confirmation_needed=False,
                score_signal=0,
            )
        return ConditionCheck(
            field="region",
            status=MatchStatus.MISMATCH,
            reason="거주 시/도가 이 서비스의 대상 지역과 달라요.",
            confirmation_needed=False,
            score_signal=0,
        )

    if service.sido != user.sido:
        return ConditionCheck(
            field="region",
            status=MatchStatus.MISMATCH,
            reason="거주 시/도가 이 서비스의 대상 지역과 달라요.",
            confirmation_needed=False,
            score_signal=0,
        )

    if user.sigungu is None:
        return ConditionCheck(
            field="region",
            status=MatchStatus.UNKNOWN,
            reason="이 서비스는 시군구 단위 사업이라 정확한 확인을 위해 거주 시군구 정보가 필요해요.",
            confirmation_needed=True,
            score_signal=0,
        )

    if service.sigungu == user.sigungu:
        return ConditionCheck(
            field="region",
            status=MatchStatus.MATCH,
            reason="거주 시군구까지 정확히 일치해요.",
            confirmation_needed=False,
            score_signal=+1,  # used by scorer.py as the region-precision signal
        )

    if _sigungu_base(service.sigungu) == _sigungu_base(user.sigungu):
        # Same base city/county, different sub-district granularity only
        # (e.g. service="화성시", user="화성시 동탄구") -- see _sigungu_base.
        return ConditionCheck(
            field="region",
            status=MatchStatus.MATCH,
            reason="거주 시군구까지 일치해요(같은 시/군 내 세부 구 단위 차이).",
            confirmation_needed=False,
            score_signal=+1,
        )

    return ConditionCheck(
        field="region",
        status=MatchStatus.MISMATCH,
        reason="거주 시군구가 이 서비스의 대상 지역과 달라요.",
        confirmation_needed=False,
        score_signal=0,
    )


# ---------------------------------------------------------------------------
# Age (rules_spec.md §7)
# ---------------------------------------------------------------------------


def evaluate_age(user: UserProfile, service: ServiceRecord) -> ConditionCheck:
    """Never returns MISMATCH for a COMPOUND condition -- by construction,
    only SIMPLE_MIN / SIMPLE_RANGE can trigger a hard exclusion in
    filters.py, because MISMATCH is only produced here for those two types.
    """
    if service.age_condition_type is AgeConditionType.NONE or service.min_age is None:
        return ConditionCheck(
            field="age",
            status=MatchStatus.UNKNOWN,
            reason="이 서비스는 연령 조건을 명시하지 않았어요.",
            confirmation_needed=False,
            score_signal=0,
        )

    if user.age is None:
        return ConditionCheck(
            field="age",
            status=MatchStatus.UNKNOWN,
            reason="연령 정보가 없어 확인이 필요해요.",
            confirmation_needed=True,
            score_signal=0,
        )

    if service.age_condition_type is AgeConditionType.COMPOUND:
        if user.age >= service.min_age:
            return ConditionCheck(
                field="age",
                status=MatchStatus.MATCH,
                reason=(
                    f"입력하신 연령이 이 서비스의 기본 연령 기준(만 {service.min_age}세)을 충족해요. "
                    "단, 이 서비스는 복합 연령조건을 갖고 있어요: "
                    f"{service.age_condition_note or '원문 확인 필요'}"
                ),
                confirmation_needed=False,
                score_signal=0,
            )
        return ConditionCheck(
            field="age",
            status=MatchStatus.UNKNOWN,
            reason=(
                "이 서비스는 연령이 복합적으로 정해져 있어(예: 특정 질환이 있으면 낮은 연령도 해당) "
                f"단순 나이만으로는 판단할 수 없어요: {service.age_condition_note or '원문 확인 필요'}"
            ),
            confirmation_needed=True,
            score_signal=0,
        )

    # SIMPLE_MIN or SIMPLE_RANGE
    if user.age < service.min_age:
        return ConditionCheck(
            field="age",
            status=MatchStatus.MISMATCH,
            reason=f"이 서비스는 만 {service.min_age}세 이상을 대상으로 해요.",
            confirmation_needed=False,
            score_signal=0,
        )
    if service.max_age is not None and user.age > service.max_age:
        return ConditionCheck(
            field="age",
            status=MatchStatus.MISMATCH,
            reason=f"이 서비스는 만 {service.min_age}~{service.max_age}세를 대상으로 해요.",
            confirmation_needed=False,
            score_signal=0,
        )
    return ConditionCheck(
        field="age",
        status=MatchStatus.MATCH,
        reason=f"연령 조건(만 {service.min_age}세 이상)을 충족해요.",
        confirmation_needed=False,
        score_signal=0,
    )


# ---------------------------------------------------------------------------
# Special eligibility (recommendation_engine_v1_2_validation.md §7-8)
# ---------------------------------------------------------------------------


def evaluate_special_eligibility(service: ServiceRecord) -> ConditionCheck:
    """Whether this service requires an institutionally-certified special-
    population status (국가유공자 registration, a formal 장기요양등급
    판정, etc.) that no other HARD-gate field represents.

    There is deliberately no ``user`` parameter: UserProfile has no
    corresponding question (nothing to ask yet -- v1.2 report §7 option 4),
    so the "user side" of this comparison is permanently absent rather than
    UNKNOWN-because-unanswered. The status is therefore always UNKNOWN --
    never MATCH (nothing confirms the user actually holds that status) and
    never MISMATCH (never hard-excluded; UNKNOWN != FALSE applies here too).
    Its only effect is ``confirmation_needed=True`` when the service itself
    requires it, which counts toward ``HardFilterResult.open_count()`` and
    is what keeps such a service from reaching HIGH_MATCH by default.
    """
    if service.special_eligibility_required is not TriState.TRUE:
        return ConditionCheck(
            field="special_eligibility_required",
            status=MatchStatus.UNKNOWN,
            reason="이 서비스는 특수 자격요건을 별도로 명시하지 않았어요.",
            confirmation_needed=False,
            score_signal=0,
        )

    detail = f" ({service.special_eligibility_note})" if service.special_eligibility_note else ""
    return ConditionCheck(
        field="special_eligibility_required",
        status=MatchStatus.UNKNOWN,
        reason=(
            f"이 서비스는 별도의 특수 자격요건이 필요해요{detail}. "
            "입력하신 정보만으로는 확인되지 않아 담당 기관 확인이 필요해요."
        ),
        confirmation_needed=True,
        score_signal=0,
    )


def is_age_compound_uncertain(user: UserProfile, service: ServiceRecord) -> bool:
    """True only for the COMPOUND + below-threshold case (rules_spec.md §10:
    forces NEEDS_CONFIRMATION regardless of open_count / score)."""
    return (
        service.age_condition_type is AgeConditionType.COMPOUND
        and service.min_age is not None
        and user.age is not None
        and user.age < service.min_age
    )


def region_needs_sigungu_confirmation(user: UserProfile, service: ServiceRecord) -> bool:
    """True for the specific SIGUNGU-scope + missing-user-sigungu case that
    rules_spec.md §10 calls out as its own forced NEEDS_CONFIRMATION trigger.
    """
    return (
        service.region_scope is RegionScope.SIGUNGU
        and service.sigungu is not None
        and user.sido is not None
        and service.sido == user.sido
        and user.sigungu is None
    )
