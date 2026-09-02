"""Top-level orchestration: normalize -> gate -> score -> grade -> explain -> rank.

Public entry point: ``recommend(user_profile, services=None, top_k=5)``.
"""

from __future__ import annotations

from typing import List, Optional

from .config import DEFAULT_WEIGHTS, HIGH_MATCH_SCORE_THRESHOLD
from .filters import HardFilterResult, apply_hard_filters
from .loader import load_services
from .matcher import is_age_compound_uncertain, region_needs_sigungu_confirmation
from .models import (
    ConditionCheck,
    MatchLevel,
    MatchStatus,
    RecommendationResult,
    ServiceRecord,
    UserProfile,
)
from .scorer import ScoreBreakdown, compute_score

# Field name -> Korean label, used only for building explanation sentences.
_FIELD_LABEL = {
    "region": "거주 지역",
    "age": "연령",
    "disability_required": "장애",
    "low_income_required": "저소득",
    "single_household_required": "독거",
    "homebound_or_mobility_condition": "거동불편",
}


def _determine_match_level(
    user: UserProfile,
    service: ServiceRecord,
    hard: HardFilterResult,
    score: ScoreBreakdown,
) -> MatchLevel:
    """rules_spec.md §10 -- not a plain score cutoff.

    Order of precedence (each is a forced downgrade, checked before falling
    back to the open_count / score based decision):
      1. desired_support is empty or "unsure" -> always NEEDS_CONFIRMATION
      2. COMPOUND age condition below its representative threshold and thus
         genuinely uncertain -> NEEDS_CONFIRMATION
      3. SIGUNGU-scope service where sido matches but sigungu is unknown
         -> NEEDS_CONFIRMATION (cannot even confirm local applicability)
      4. open_count (# of "service requires it, user unknown" HARD-gate
         dimensions) >= 2 -> NEEDS_CONFIRMATION
      5. no overlap at all between what the user asked for and this
         service's service_type -> NEEDS_CONFIRMATION. Passing every
         eligibility gate does not make a service "worth checking out" for
         a stated need it simply does not offer (rules_spec.md §9: gates
         and preference must not be conflated; §10's table already
         requires a desired_support intersection for POSSIBLE_MATCH -- this
         was previously only enforced for the HIGH_MATCH promotion, which
         let 0%-relevant services surface as POSSIBLE_MATCH purely because
         nothing more relevant survived the region gate. Fixed after the
         2026-08-23 real-user-case review, see
         docs/recommendation_engine_real_case_validation.md).
      6. open_count == 1 -> POSSIBLE_MATCH
      7. open_count == 0, an EXACT service_type match exists, and score
         above the v1 threshold -> HIGH_MATCH
      8. otherwise -> POSSIBLE_MATCH

    v1.3 addition (docs/recommendation_ranking_final_tuning_report.md §5):
    rule 5 now also passes when only a RELATED (not exact) service_type
    match exists -- e.g. a community_care service for a home_visit request
    -- instead of forcing NEEDS_CONFIRMATION on every non-exact match. Rule
    7 still requires an EXACT match for HIGH_MATCH: a related-but-not-exact
    service can rise to POSSIBLE_MATCH but never claims full confidence.
    """
    if not user.effective_desired_support():
        return MatchLevel.NEEDS_CONFIRMATION

    if is_age_compound_uncertain(user, service):
        return MatchLevel.NEEDS_CONFIRMATION

    if region_needs_sigungu_confirmation(user, service):
        return MatchLevel.NEEDS_CONFIRMATION

    open_count = hard.open_count()
    if open_count >= 2:
        return MatchLevel.NEEDS_CONFIRMATION

    if not score.service_type_intersection and not score.service_type_related:
        return MatchLevel.NEEDS_CONFIRMATION

    if open_count == 1:
        return MatchLevel.POSSIBLE_MATCH

    if (
        score.service_type_intersection
        and score.normalized_score >= HIGH_MATCH_SCORE_THRESHOLD
    ):
        return MatchLevel.HIGH_MATCH
    return MatchLevel.POSSIBLE_MATCH


def _build_explanations(
    hard: HardFilterResult,
    score: ScoreBreakdown,
    service: ServiceRecord,
    user: UserProfile,
) -> tuple:
    matched_conditions: List[str] = []
    unknown_conditions: List[str] = []
    exclusion_warnings: List[str] = []
    confirmation_needed: List[str] = []

    all_checks: List[ConditionCheck] = hard.gate_checks() + score.soft_checks()

    for check in all_checks:
        if check.status is MatchStatus.MATCH:
            matched_conditions.append(check.reason)
        elif check.status is MatchStatus.UNKNOWN:
            unknown_conditions.append(check.reason)
            if check.confirmation_needed:
                confirmation_needed.append(check.reason)
        elif check.status is MatchStatus.MISMATCH:
            # Only single_household / mobility can reach here without
            # already having been hard-excluded (region/age/disability/
            # low_income MISMATCH means this service was never scored).
            exclusion_warnings.append(check.reason)

    if score.service_type_intersection:
        matched_conditions.append(
            "원하시는 도움("
            + ", ".join(sorted(score.service_type_intersection))
            + ")과 이 서비스의 제공 내용이 일치해요."
        )
    if score.service_type_related:
        matched_conditions.append(
            "원하시는 도움("
            + ", ".join(sorted(score.service_type_related))
            + ")과 완전히 같지는 않지만 관련이 있는 지원을 제공해요."
        )

    desired = user.effective_desired_support()
    if desired and not score.service_type_intersection and not score.service_type_related:
        wanted = ", ".join(sorted(d.value for d in desired))
        exclusion_warnings.append(
            f"이 서비스는 원하시는 도움 유형({wanted})과 직접 관련되지는 않아요. "
            "다만 참고할 수 있는 관련 지원일 수 있어 함께 안내해 드려요."
        )

    if service.age_condition_type.value == "COMPOUND" and service.age_condition_note:
        exclusion_warnings.append(f"연령 조건이 복합적이에요: {service.age_condition_note}")

    if service.data_quality_note:
        exclusion_warnings.append(f"데이터 참고사항: {service.data_quality_note}")

    exclusion_warnings.append(
        "이 안내는 참고용이며, 실제 자격 여부는 거주지 읍/면/동 주민센터 또는 문의처를 통해 "
        "확인해야 해요."
    )

    recommendation_reasons = list(matched_conditions)

    return matched_conditions, unknown_conditions, exclusion_warnings, confirmation_needed, recommendation_reasons


def _sort_key(result: RecommendationResult):
    # Deterministic, documented tie-break order (rules_spec.md §12 /
    # instructions §12): score desc, verification_level desc (A before B),
    # region precision desc (exact sigungu match before broader match),
    # service_id asc.
    verification_rank = 0 if result.verification_level == "A" else 1
    region_precision_rank = 0 if result.region_exact_match else 1
    return (-result.match_score, verification_rank, region_precision_rank, result.service_id)


def evaluate_service(user: UserProfile, service: ServiceRecord) -> Optional[RecommendationResult]:
    """Evaluate one service against one user. Returns None if hard-excluded."""
    hard = apply_hard_filters(user, service)
    if not hard.passed:
        return None

    score = compute_score(user, service, hard.region_check, DEFAULT_WEIGHTS)
    level = _determine_match_level(user, service, hard, score)
    matched, unknown, warnings, confirm, reasons = _build_explanations(hard, score, service, user)

    return RecommendationResult(
        service_id=service.service_id,
        service_name=service.service_name,
        region=service.region_label(),
        service_type=sorted(service.service_type),
        match_score=score.normalized_score,
        match_level=level,
        matched_conditions=matched,
        unknown_conditions=unknown,
        exclusion_warnings=warnings,
        confirmation_needed=confirm,
        recommendation_reasons=reasons,
        verification_level=service.verification_level,
        nutritionist_involvement=service.nutritionist_involvement,
        region_exact_match=hard.region_check.score_signal > 0,
        support_summary=service.support_summary,
        eligibility_summary=service.eligibility_summary,
        application_method=service.application_original,
        contact=service.contact,
        target_original=service.target_original,
        criteria_original=service.criteria_original,
    )


def recommend(
    user_profile: UserProfile,
    services: Optional[List[ServiceRecord]] = None,
    top_k: int = 5,
) -> List[RecommendationResult]:
    """Run the full pipeline and return up to top_k ranked results.

    Pipeline (rules_spec.md §3):
      1. normalize user input           -- UserProfile.__post_init__
      2. region comparison + 3. hard filters (age/disability/low_income)
                                         -- filters.apply_hard_filters
      4-6. soft scoring                 -- scorer.compute_score
      7. UNKNOWN handling               -- baked into matcher/filters/scorer
      8. final score                    -- scorer.compute_score
      9. match_level                    -- _determine_match_level
      10. explanations                  -- _build_explanations
      (sort + top_k here)
    """
    if services is None:
        services = load_services()

    results = []
    for service in services:
        result = evaluate_service(user_profile, service)
        if result is not None:
            results.append(result)

    results.sort(key=_sort_key)
    return results[: max(0, top_k)]
