"""Rule-based recommendation engine v1.

See docs/recommendation_rules_spec.md for the specification this package
implements, and docs/recommendation_engine_v1_report.md for the
implementation report. No LLM, RAG, or external API calls happen anywhere
in this package -- every match_score / match_level / explanation is produced
by deterministic Python rules (recommendation_rules_spec.md §12, rule 6).
"""

from .models import (
    AgeConditionType,
    ConditionCheck,
    DesiredSupport,
    MatchLevel,
    MatchStatus,
    RecommendationResult,
    RegionScope,
    ServiceRecord,
    TriState,
    UserProfile,
)
from .loader import load_services
from .recommender import recommend

__all__ = [
    "AgeConditionType",
    "ConditionCheck",
    "DesiredSupport",
    "MatchLevel",
    "MatchStatus",
    "RecommendationResult",
    "RegionScope",
    "ServiceRecord",
    "TriState",
    "UserProfile",
    "load_services",
    "recommend",
]
