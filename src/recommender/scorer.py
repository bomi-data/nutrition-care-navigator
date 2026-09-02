"""SOFT SCORE computation (rules_spec.md §8, §9).

Eligibility gates (region / age / disability / low_income) are never
double-counted here -- they were already resolved as PASS/EXCLUDE in
filters.py. Only preference/relevance dimensions are scored:

    * service_type <-> desired_support overlap (dominant weight)
    * single_household / mobility soft match (TRUE/TRUE bonus only)
    * sigungu-precision bonus on top of an already-passed region gate
    * verification_level (minor tie-breaker)
    * nutrition / discharge bonuses, active only when the user actually
      asked for them -- never based on how much data a service happens
      to carry (that would reward sparse data, see rules_spec.md §14).

The 0-100 normalization uses a fixed "applicable max" that depends only on
the *user's* choices, not on the service, so a data-poor service can never
reach a higher ceiling than a data-rich one just by having fewer
comparable fields (see docs/recommendation_engine_v1_report.md).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from .config import DEFAULT_WEIGHTS, VERIFICATION_LEVEL_POINTS
from .matcher import evaluate_tristate
from .models import ConditionCheck, DesiredSupport, MatchStatus, ServiceRecord, TriState, UserProfile
from .models import SERVICE_TYPE_TAGS


@dataclass
class ScoreBreakdown:
    achieved: float
    max_possible: float
    normalized_score: float
    single_household_check: ConditionCheck
    mobility_check: ConditionCheck
    service_type_intersection: frozenset  # EXACT tag matches only
    service_type_related: frozenset  # RELATED (partial-credit) tag matches -- see docs/recommendation_ranking_final_tuning_report.md §5
    components: dict  # name -> (achieved, max) for explanation/debugging

    def soft_checks(self) -> List[ConditionCheck]:
        return [self.single_household_check, self.mobility_check]


# Semantic-adjacency pairs for desired_support <-> service_type matching
# (docs/recommendation_ranking_final_tuning_report.md §5). An EXACT tag
# match (desired tag literally in service.service_type) keeps full credit --
# unchanged v1 behavior. A RELATED match earns partial credit instead of the
# previous hard 0: "home_visit"/"discharge_support" are forms of the same
# at-home/community-care family as "community_care" (the instructions'
# own §4 explicitly groups "재가/방문 돌봄" with community_care-type
# services), and "food_cost_support" is food-related but not identical to
# "meal_support". Two disjoint clusters -- a tag never "leaks" credit into
# the other cluster. NEUTRAL (no listed relation, e.g. an empty
# service_type) still earns 0, same as before.
RELATED_SERVICE_TYPE_TAGS = {
    "meal_support": {"food_cost_support"},
    "food_cost_support": {"meal_support"},
    "community_care": {"home_visit", "discharge_support"},
    "home_visit": {"community_care", "discharge_support"},
    "discharge_support": {"community_care", "home_visit"},
}
# Half credit vs. an exact tag match -- a defensible, symmetric midpoint
# that keeps desired_support's max contribution unchanged (still capped at
# weights["service_type_match_max"], same as v1) while letting a
# related-but-not-identical service score above a truly unrelated one.
RELATED_MATCH_CREDIT = 0.5

# nutrition_relevance values that count as "food/nutrition-adjacent" for a
# meal_support request even when the service carries no meal_support/
# food_cost_support tag (e.g. a community_care service whose package
# includes 영양지원 -- see ENR-CHEONAN-02, nutrition_relevance=SUPPORTIVE_NUTRITION).
_MEAL_RELATED_NUTRITION_RELEVANCE = {"DIRECT_NUTRITION", "SUPPORTIVE_NUTRITION"}


def _service_type_component(user: UserProfile, service: ServiceRecord, weights: dict):
    desired = user.effective_desired_support()
    # only the tags that actually have a service_type counterpart matter;
    # nutrition_counseling has none in this dataset (rules_spec.md §0/§8)
    desired_tags = {d.value for d in desired if d.value in SERVICE_TYPE_TAGS}
    if not desired_tags:
        return 0.0, 0.0, frozenset(), frozenset()

    exact = frozenset(desired_tags) & service.service_type
    related = set()
    for tag in desired_tags - exact:
        if RELATED_SERVICE_TYPE_TAGS.get(tag, set()) & service.service_type:
            related.add(tag)
        elif tag == "meal_support" and service.nutrition_relevance in _MEAL_RELATED_NUTRITION_RELEVANCE:
            related.add(tag)
    related = frozenset(related)

    credit = len(exact) + len(related) * RELATED_MATCH_CREDIT
    ratio = credit / len(desired_tags)
    max_points = weights["service_type_match_max"]
    return ratio * max_points, max_points, exact, related


def _region_precision_component(region_check: ConditionCheck, weights: dict):
    max_points = weights["region_precision_max"]
    achieved = max_points if region_check.score_signal > 0 else 0.0
    return achieved, max_points


def _verification_component(service: ServiceRecord, weights: dict):
    max_points = weights["verification_level_max"]
    frac = VERIFICATION_LEVEL_POINTS.get(service.verification_level, 0.0)
    return frac * max_points, max_points


def _nutrition_component(user: UserProfile, service: ServiceRecord, weights: dict):
    if DesiredSupport.NUTRITION_COUNSELING not in user.effective_desired_support():
        return 0.0, 0.0
    max_points = weights["nutrition_bonus_max"]
    if service.nutritionist_involvement == "direct":
        return max_points, max_points
    if service.nutrition_relevance == "DIRECT_NUTRITION":
        return max_points * 0.5, max_points
    return 0.0, max_points


def _meal_preparation_component(user: UserProfile, service: ServiceRecord, weights: dict):
    """v1.2 addition -- see config.py's meal_preparation_bonus_max docstring.

    Active only when the user explicitly says meal preparation is difficult
    (never on FALSE/UNKNOWN, matching the nutrition/discharge bonus
    pattern's anti-gaming rule: max_possible depends only on the user's
    answer, not on the service). Checked against service_type membership
    (100% coverage) rather than meal_support_flag (36.5% coverage,
    rules_spec.md §0.1) since design doc §4 already established service_type
    as sufficient on its own for this signal.
    """
    if user.meal_preparation_difficulty is not TriState.TRUE:
        return 0.0, 0.0
    max_points = weights["meal_preparation_bonus_max"]
    if "meal_support" in service.service_type:
        return max_points, max_points
    return 0.0, max_points


def _discharge_component(user: UserProfile, service: ServiceRecord, weights: dict):
    wants_discharge = (
        DesiredSupport.DISCHARGE_SUPPORT in user.effective_desired_support()
        or user.recent_discharge.value == "true"
    )
    if not wants_discharge:
        return 0.0, 0.0
    max_points = weights["discharge_bonus_max"]
    if "discharge_support" in service.service_type:
        return max_points, max_points
    return 0.0, max_points


def compute_score(
    user: UserProfile,
    service: ServiceRecord,
    region_check: ConditionCheck,
    weights: dict = DEFAULT_WEIGHTS,
) -> ScoreBreakdown:
    single_household_check = evaluate_tristate(
        "single_household_required",
        service.single_household_required,
        user.lives_alone,
        field_label_ko="독거",
    )
    mobility_check = evaluate_tristate(
        "homebound_or_mobility_condition",
        service.homebound_or_mobility_condition,
        user.mobility_difficulty,
        field_label_ko="거동불편",
    )

    components = {}

    st_achieved, st_max, exact_intersection, related_intersection = _service_type_component(user, service, weights)
    components["service_type_match"] = (st_achieved, st_max)

    sh_max = weights["single_household_max"]
    sh_achieved = max(0.0, single_household_check.score_signal) * sh_max
    components["single_household"] = (sh_achieved, sh_max)

    mob_max = weights["mobility_max"]
    mob_achieved = max(0.0, mobility_check.score_signal) * mob_max
    components["mobility"] = (mob_achieved, mob_max)

    rp_achieved, rp_max = _region_precision_component(region_check, weights)
    components["region_precision"] = (rp_achieved, rp_max)

    ver_achieved, ver_max = _verification_component(service, weights)
    components["verification_level"] = (ver_achieved, ver_max)

    nut_achieved, nut_max = _nutrition_component(user, service, weights)
    components["nutrition_bonus"] = (nut_achieved, nut_max)

    dis_achieved, dis_max = _discharge_component(user, service, weights)
    components["discharge_bonus"] = (dis_achieved, dis_max)

    mp_achieved, mp_max = _meal_preparation_component(user, service, weights)
    components["meal_preparation_bonus"] = (mp_achieved, mp_max)

    # single_household / mobility MISMATCH is a soft penalty, applied after
    # the positive-only component above so a mismatch can pull the raw
    # achieved total below what "0 credit" would give, without touching the
    # (user-only-dependent) max_possible denominator.
    penalty = 0.0
    if single_household_check.score_signal < 0:
        penalty += sh_max
    if mobility_check.score_signal < 0:
        penalty += mob_max

    achieved = sum(a for a, _ in components.values()) - penalty
    max_possible = sum(m for _, m in components.values())

    if max_possible <= 0:
        normalized = 0.0
    else:
        normalized = 100.0 * achieved / max_possible
        normalized = max(0.0, min(100.0, normalized))

    return ScoreBreakdown(
        achieved=achieved,
        max_possible=max_possible,
        normalized_score=round(normalized, 2),
        single_household_check=single_household_check,
        mobility_check=mobility_check,
        service_type_intersection=exact_intersection,
        service_type_related=related_intersection,
        components=components,
    )
