"""Cross-service contamination tests (docs/rag_retrieval_v1_report.md §17).

Must always be zero: retrieving for service_id A must never return a
document belonging to service_id B, no matter how semantically similar the
two services are. This is enforced structurally (VectorStore.search_within
only ever scores vectors reconstructed from the caller-provided candidate
rows), but these tests check it empirically too.
"""

from rag.retriever import retrieve, retrieve_for_service

# Deliberately similar-content pairs -- both are 재가(home-visit) services
# for vulnerable elderly, so if section-vector similarity alone controlled
# results (instead of a hard service_id filter), these would be the pairs
# most likely to leak into each other.
ADVERSARIAL_PAIRS = [
    ("WLF00003248", "WLF00000098"),  # 재가급여 vs 국가유공자재가복지지원
    ("WLF00005770", "WLF00005308"),  # 대전형 통합돌봄 vs 춘천형 통합돌봄
    ("WLF00002028", "WLF00003803"),  # both "저소득 재가노인 식사배달"-named services
]

SHARED_QUERIES = [
    "누가 이용할 수 있나요?",
    "어떤 지원을 받을 수 있나요?",
    "신청 조건이 무엇인가요?",
    "어떻게 신청하나요?",
]


def test_no_contamination_for_adversarial_pairs(rag_store, rag_embedder):
    violations = []
    for service_a, service_b in ADVERSARIAL_PAIRS:
        for query in SHARED_QUERIES:
            results = retrieve_for_service(rag_store, rag_embedder, service_a, query, top_k=5)
            for r in results:
                if r.service_id != service_a:
                    violations.append((service_a, query, r.service_id))

    assert violations == [], f"cross-service contamination found: {violations}"


def test_no_contamination_when_multiple_service_ids_requested(rag_store, rag_embedder):
    # Requesting several service_ids at once is the normal top-K
    # recommendation case -- results must stay within that exact set.
    allowed = {"WLF00003248", "WLF00000098", "WLF00005770"}
    for query in SHARED_QUERIES:
        results = retrieve(rag_store, rag_embedder, query, list(allowed), top_k=10)
        for r in results:
            assert r.service_id in allowed


def test_all_thirty_eval_queries_zero_contamination(rag_store, rag_embedder):
    from .eval_queries import EVAL_QUERIES

    violations = 0
    for eq in EVAL_QUERIES:
        results = retrieve_for_service(rag_store, rag_embedder, eq.service_id, eq.query, top_k=3)
        violations += sum(1 for r in results if r.service_id != eq.service_id)

    assert violations == 0
