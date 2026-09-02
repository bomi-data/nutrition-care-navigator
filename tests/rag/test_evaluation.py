"""Retrieval quality evaluation against the 30-query ground truth set
(docs/rag_retrieval_v1_report.md §13-16). Thresholds are intentionally
looser than "must be perfect" -- v1 is judged against whether it's good
enough to hand to an LLM generation step next, not against a tuned bar.
"""

from rag.retriever import retrieve

from .eval_queries import AMBIGUOUS_QUERIES, EVAL_QUERIES, evaluate


def test_evaluation_metrics_meet_v1_bar(rag_store, rag_embedder):
    metrics = evaluate(rag_store, rag_embedder, retrieve, top_k=3)

    assert metrics["n_queries"] == 30
    assert metrics["contamination"] == 0
    # v1 bar, not a tuned target -- see report §12/§16 for the actual
    # measured numbers and what's still weak.
    assert metrics["hit_at_1"] >= 0.5
    assert metrics["hit_at_3"] >= 0.8


def test_every_eval_query_returns_at_least_one_result(rag_store, rag_embedder):
    for eq in EVAL_QUERIES:
        results = retrieve(rag_store, rag_embedder, eq.query, [eq.service_id], top_k=3)
        assert results, f"no results for {eq.service_id} / {eq.query!r}"


def test_ambiguous_queries_do_not_crash_and_return_something(rag_store, rag_embedder):
    for service_id, query in AMBIGUOUS_QUERIES:
        results = retrieve(rag_store, rag_embedder, query, [service_id], top_k=3)
        # No assertion on *which* sections come back -- instructions §18:
        # for ambiguous queries we only record what was retrieved, we never
        # assert or imply an eligibility conclusion from it.
        assert all(r.service_id == service_id for r in results)
