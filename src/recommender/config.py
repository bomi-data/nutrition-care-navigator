"""Centralized, named configuration for the v1 rule-based recommender.

IMPORTANT: These are v1 heuristic values, not final tuned weights and not a
competition-submission-ready configuration (see
docs/recommendation_rules_spec.md §9). They exist here -- in one place -- so
future tuning never requires hunting through the matching/scoring code for
magic numbers.

All SOFT score components are expressed as a maximum contribution ("how many
points this component can add"). The final match_score is a 0-100
normalization of achieved-points / applicable-max-points for that specific
user (see scorer.py). Components are only "applicable" based on what the
*user* asked for (e.g. the nutrition bonus only applies if the user selected
nutrition_counseling) -- never based on how much data a *service* happens to
have, which is the anti-gaming rule from rules_spec.md §14.
"""

from __future__ import annotations

DEFAULT_WEIGHTS = {
    # Dominant driver: how much of what the user asked for this service covers.
    "service_type_match_max": 50.0,
    # Soft "life situation" match -- eligibility-adjacent but explicitly NOT
    # treated as a hard gate (rules_spec.md §4: no FALSE value exists in the
    # data for these two fields, and the TRUE judgments were themselves
    # partly interpretive -- see recommendation_data_readiness.md §7).
    "single_household_max": 10.0,
    "mobility_max": 10.0,
    # Small bonus for an exact sigungu-level match on top of the region gate.
    "region_precision_max": 10.0,
    # Data-quality tie-breaker only -- never a primary driver.
    "verification_level_max": 5.0,
    # Only active when the user actually asked for nutrition counseling.
    "nutrition_bonus_max": 10.0,
    # Only active when the user asked for discharge follow-up care.
    "discharge_bonus_max": 5.0,
    # v1.2 addition (recommendation_engine_v1_2_validation.md §meal_prep):
    # meal_preparation_difficulty was a required UserProfile input with zero
    # code path anywhere in matcher/filters/scorer -- a confirmed logic gap,
    # not a deliberate v1 decision (rules_spec.md §2 lists it as an input
    # but its §4/§9 classification tables never mention it). Same shape and
    # same magnitude as single_household_max/mobility_max: another
    # "생활조건 필요도" signal, active only when the user explicitly says
    # TRUE (never on FALSE/UNKNOWN), scored against the 100%-covered
    # service_type field rather than the sparse meal_support_flag column.
    "meal_preparation_bonus_max": 10.0,
}

# Minimum normalized (0-100) score, on top of open_count == 0 and a direct
# service_type intersection, required to grant HIGH_MATCH instead of
# POSSIBLE_MATCH (rules_spec.md §10: "점수가 높더라도... 상위" is relative;
# this fixed threshold is the v1 stand-in for that relative comparison).
HIGH_MATCH_SCORE_THRESHOLD = 55.0

# verification_level -> points out of verification_level_max
VERIFICATION_LEVEL_POINTS = {
    "A": 1.0,   # full credit
    "B": 0.0,   # v1: no credit, but never a penalty either
}
