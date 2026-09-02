"""Ground-truth retrieval evaluation set (docs/rag_retrieval_v1_report.md §13-16).

Not a test module itself (no test_ prefix) -- imported by
test_evaluation.py and by scripts/print_rag_eval.py to compute the same
Hit@1 / Hit@3 / MRR numbers reported in the doc.

Every (service_id, query, expected_sections) tuple below was written by
reading the *actual* target_original/criteria_original/support_original/
application_original text for that service_id in
data/processed/welfare_services_recommendation_ready.csv -- not invented.
Where a service's own text plausibly answers the question from either of
two sections (e.g. "누가 이용할 수 있나요?" is answered by both target_original
and criteria_original in this corpus -- both describe eligibility, just at
different granularity), expected_sections lists both and a hit against
either counts.

10 services, 4 real service_type tags represented (meal_support,
food_cost_support, community_care, home_visit), 3 questions each = 30
queries (instructions §15's minimum).

Three of the ten services have application_original == "[]" (no real
application-method text at all) -- no application-type (D) question is
used for those, so every expected_sections value below is grounded in text
that actually exists.
"""

from __future__ import annotations

from typing import List, NamedTuple, Sequence


class EvalQuery(NamedTuple):
    service_id: str
    service_name: str
    query: str
    expected_sections: Sequence[str]  # hit if top-ranked section is any of these


EVAL_QUERIES: List[EvalQuery] = [
    # WLF00003518 -- 사랑이음 밥차 운영 (meal_support, application="[]")
    EvalQuery("WLF00003518", "사랑이음 밥차 운영", "누가 이용할 수 있나요?", ("target", "criteria")),
    EvalQuery("WLF00003518", "사랑이음 밥차 운영", "저소득 조건이 있나요?", ("criteria", "target")),
    EvalQuery("WLF00003518", "사랑이음 밥차 운영", "어떤 지원을 받을 수 있나요?", ("support",)),
    # WLF00000383 -- 경로식당 무료급식사업 (meal_support, application="[]")
    EvalQuery("WLF00000383", "경로식당 무료급식사업", "누가 이용할 수 있나요?", ("target", "criteria")),
    EvalQuery("WLF00000383", "경로식당 무료급식사업", "얼마나 자주 식사를 제공하나요?", ("support",)),
    EvalQuery("WLF00000383", "경로식당 무료급식사업", "신청 조건이 무엇인가요?", ("criteria",)),
    # WLF00002028 -- 저소득 재가노인 식사배달 (meal_support)
    EvalQuery("WLF00002028", "저소득 재가노인 식사배달", "거동이 불편해야 하나요?", ("target", "criteria")),
    EvalQuery("WLF00002028", "저소득 재가노인 식사배달", "어떻게 신청하나요?", ("application",)),
    EvalQuery("WLF00002028", "저소득 재가노인 식사배달", "얼마나 자주 식사를 제공하나요?", ("support",)),
    # WLF00003036 -- 노인 효도권 지원 (food_cost_support, application="[]")
    EvalQuery("WLF00003036", "노인 효도권 지원", "누가 이용할 수 있나요?", ("target", "criteria")),
    EvalQuery("WLF00003036", "노인 효도권 지원", "어떤 지원을 받을 수 있나요?", ("support",)),
    EvalQuery("WLF00003036", "노인 효도권 지원", "신청 조건이 무엇인가요?", ("criteria", "target")),
    # WLF00000664 -- 노인맞춤돌봄지원 강화 사업 (community_care)
    EvalQuery("WLF00000664", "노인맞춤돌봄지원 강화 사업", "누가 이용할 수 있나요?", ("target", "criteria")),
    EvalQuery("WLF00000664", "노인맞춤돌봄지원 강화 사업", "어떤 지원을 받을 수 있나요?", ("support",)),
    EvalQuery("WLF00000664", "노인맞춤돌봄지원 강화 사업", "어떻게 신청하나요?", ("application",)),
    # WLF00005770 -- 대전형 지역사회통합돌봄 (community_care / home_visit)
    EvalQuery("WLF00005770", "대전형 지역사회통합돌봄", "거동이 불편해야 하나요?", ("criteria", "target")),
    EvalQuery("WLF00005770", "대전형 지역사회통합돌봄", "어떤 지원을 받을 수 있나요?", ("support",)),
    EvalQuery("WLF00005770", "대전형 지역사회통합돌봄", "어떻게 신청하나요?", ("application",)),
    # WLF00005308 -- 춘천형 노인통합돌봄사업 (community_care / home_visit)
    EvalQuery("WLF00005308", "춘천형 노인통합돌봄사업", "누가 이용할 수 있나요?", ("target", "criteria")),
    EvalQuery("WLF00005308", "춘천형 노인통합돌봄사업", "신청 조건이 무엇인가요?", ("criteria",)),
    EvalQuery("WLF00005308", "춘천형 노인통합돌봄사업", "어떻게 신청하나요?", ("application",)),
    # WLF00000098 -- 국가유공자재가복지지원 (home_visit)
    EvalQuery("WLF00000098", "국가유공자재가복지지원", "저소득 조건이 있나요?", ("criteria",)),
    EvalQuery("WLF00000098", "국가유공자재가복지지원", "어떤 지원을 받을 수 있나요?", ("support",)),
    EvalQuery("WLF00000098", "국가유공자재가복지지원", "어떻게 신청하나요?", ("application",)),
    # WLF00003248 -- 재가급여 (home_visit)
    EvalQuery("WLF00003248", "재가급여", "신청 조건이 무엇인가요?", ("criteria",)),
    EvalQuery("WLF00003248", "재가급여", "어떤 지원을 받을 수 있나요?", ("support",)),
    EvalQuery("WLF00003248", "재가급여", "누가 이용할 수 있나요?", ("target", "criteria")),
    # WLF00001509 -- 재가복지 서비스 (meal_support + home_visit tags)
    EvalQuery("WLF00001509", "재가복지 서비스", "거동이 불편해야 하나요?", ("target", "criteria")),
    EvalQuery("WLF00001509", "재가복지 서비스", "어떤 지원을 받을 수 있나요?", ("support",)),
    EvalQuery("WLF00001509", "재가복지 서비스", "어떻게 신청하나요?", ("application",)),
]

assert len(EVAL_QUERIES) == 30

# Ambiguous queries (instructions §18): retrieval may still return something,
# but no expected section is asserted -- only "did it not crash, what came
# back" is recorded. Checked against a service with rich text on every
# section so a non-empty result set is possible either way.
AMBIGUOUS_QUERIES = [
    ("WLF00005770", "이거 괜찮나요?"),
    ("WLF00005770", "도움 받을 수 있어요?"),
]


def evaluate(store, embedder, retrieve_fn, top_k: int = 3) -> dict:
    """Run every EVAL_QUERIES entry through ``retrieve_fn`` and compute
    Hit@1 / Hit@3 / MRR plus the cross-service-contamination count.

    ``retrieve_fn(store, embedder, query, service_ids, top_k) -> List[RetrievalResult]``
    """
    hit_at_1 = 0
    hit_at_3 = 0
    reciprocal_ranks = []
    contamination = 0
    per_query = []

    for eq in EVAL_QUERIES:
        results = retrieve_fn(store, embedder, eq.query, [eq.service_id], top_k)
        sections = [r.section for r in results]

        contamination += sum(1 for r in results if r.service_id != eq.service_id)

        rank = None
        for i, sec in enumerate(sections, start=1):
            if sec in eq.expected_sections:
                rank = i
                break

        if rank == 1:
            hit_at_1 += 1
        if rank is not None and rank <= 3:
            hit_at_3 += 1
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)

        per_query.append(
            {
                "service_id": eq.service_id,
                "query": eq.query,
                "expected": eq.expected_sections,
                "returned_sections": sections,
                "rank": rank,
            }
        )

    n = len(EVAL_QUERIES)
    return {
        "n_queries": n,
        "hit_at_1": hit_at_1 / n,
        "hit_at_3": hit_at_3 / n,
        "mrr": sum(reciprocal_ranks) / n,
        "contamination": contamination,
        "per_query": per_query,
    }
