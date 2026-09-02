"""HARD FILTER orchestration (rules_spec.md §4, §7).

Only four dimensions may exclude a service outright, and only when both
sides carry a concrete value that genuinely conflicts:

    region (any region_scope)
    age    (only when age_condition_type is SIMPLE_MIN / SIMPLE_RANGE)
    disability_required
    low_income_required

UNKNOWN never excludes. single_household_required and
homebound_or_mobility_condition never exclude either -- they are SOFT
fields handled entirely in scorer.py (rules_spec.md §4 explains why: no
FALSE value exists for them anywhere in the dataset, and the TRUE
judgments were partly interpretive).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from .matcher import evaluate_age, evaluate_region, evaluate_special_eligibility, evaluate_tristate
from .models import ConditionCheck, MatchStatus, ServiceRecord, UserProfile


@dataclass
class HardFilterResult:
    passed: bool
    region_check: ConditionCheck
    age_check: ConditionCheck
    disability_check: ConditionCheck
    low_income_check: ConditionCheck
    special_eligibility_check: ConditionCheck
    exclusion_reason: str = ""

    def gate_checks(self) -> List[ConditionCheck]:
        return [
            self.region_check,
            self.age_check,
            self.disability_check,
            self.low_income_check,
            self.special_eligibility_check,
        ]

    def open_count(self) -> int:
        """Number of HARD-gate dimensions where the service states a
        requirement but the user's answer is UNKNOWN (rules_spec.md §10).
        """
        return sum(1 for c in self.gate_checks() if c.confirmation_needed)


def apply_hard_filters(user: UserProfile, service: ServiceRecord) -> HardFilterResult:
    region_check = evaluate_region(user, service)
    age_check = evaluate_age(user, service)
    disability_check = evaluate_tristate(
        "disability_required",
        service.disability_required,
        user.has_disability,
        field_label_ko="장애",
    )
    low_income_check = evaluate_tristate(
        "low_income_required",
        service.low_income_required,
        user.low_income_status,
        field_label_ko="저소득",
    )
    special_eligibility_check = evaluate_special_eligibility(service)

    reasons = []
    if region_check.status is MatchStatus.MISMATCH:
        reasons.append(region_check.reason)
    if age_check.status is MatchStatus.MISMATCH:
        reasons.append(age_check.reason)
    if disability_check.status is MatchStatus.MISMATCH:
        reasons.append(disability_check.reason)
    if low_income_check.status is MatchStatus.MISMATCH:
        reasons.append(low_income_check.reason)
    # special_eligibility_check can never be MISMATCH by construction (see
    # evaluate_special_eligibility) -- never contributes to hard exclusion.

    passed = len(reasons) == 0

    return HardFilterResult(
        passed=passed,
        region_check=region_check,
        age_check=age_check,
        disability_check=disability_check,
        low_income_check=low_income_check,
        special_eligibility_check=special_eligibility_check,
        exclusion_reason=" / ".join(reasons),
    )
