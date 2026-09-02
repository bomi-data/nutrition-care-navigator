from rag.retriever import infer_section_hint, retrieve, retrieve_for_service


def test_infer_section_hint_application_queries():
    assert "application" in infer_section_hint("어떻게 신청하나요?")
    assert "application" in infer_section_hint("신청 방법이 궁금해요")


def test_infer_section_hint_support_queries():
    assert "support" in infer_section_hint("어떤 지원을 받을 수 있나요?")
    assert "support" in infer_section_hint("얼마나 자주 식사를 제공하나요?")


def test_infer_section_hint_criteria_queries():
    assert "criteria" in infer_section_hint("저소득 조건이 있나요?")


def test_infer_section_hint_target_or_criteria_queries():
    hint = infer_section_hint("누가 이용할 수 있나요?")
    assert "target" in hint or "criteria" in hint


def test_infer_section_hint_returns_none_for_unmatched_query():
    assert infer_section_hint("이거 괜찮나요?") is None


def test_retrieve_for_service_only_returns_that_service(rag_store, rag_embedder):
    results = retrieve_for_service(rag_store, rag_embedder, "WLF00003248", "신청 조건이 무엇인가요?")
    assert results
    assert all(r.service_id == "WLF00003248" for r in results)


def test_retrieve_multiple_service_ids_only_returns_those_services(rag_store, rag_embedder):
    ids = ["WLF00003248", "WLF00000098"]
    results = retrieve(rag_store, rag_embedder, "어떤 지원을 받을 수 있나요?", ids, top_k=5)
    assert results
    assert all(r.service_id in ids for r in results)


def test_retrieve_empty_query_returns_empty(rag_store, rag_embedder):
    assert retrieve(rag_store, rag_embedder, "", ["WLF00003248"]) == []
    assert retrieve(rag_store, rag_embedder, "   ", ["WLF00003248"]) == []


def test_retrieve_unknown_service_id_returns_empty(rag_store, rag_embedder):
    assert retrieve(rag_store, rag_embedder, "누가 이용할 수 있나요?", ["WLF_DOES_NOT_EXIST"]) == []


def test_retrieve_empty_service_ids_returns_empty(rag_store, rag_embedder):
    assert retrieve(rag_store, rag_embedder, "누가 이용할 수 있나요?", []) == []


def test_retrieve_for_service_with_null_application_field_does_not_crash(rag_store, rag_embedder):
    # WLF00003518's application_original == "[]" -> no application document
    # exists for it. An application-shaped question must still return
    # something useful (fallback to other sections), not crash or return
    # a phantom application result.
    results = retrieve_for_service(rag_store, rag_embedder, "WLF00003518", "어떻게 신청하나요?")
    assert results
    assert all(r.service_id == "WLF00003518" for r in results)
    assert all(r.section != "application" for r in results)


def test_retrieve_respects_top_k(rag_store, rag_embedder):
    results = retrieve_for_service(rag_store, rag_embedder, "WLF00005770", "어떤 지원을 받을 수 있나요?", top_k=2)
    assert len(results) <= 2


def test_result_schema_has_required_fields(rag_store, rag_embedder):
    results = retrieve_for_service(rag_store, rag_embedder, "WLF00003248", "신청 조건이 무엇인가요?")
    assert results
    r = results[0]
    assert r.service_id
    assert r.service_name
    assert r.section
    assert r.content
    assert isinstance(r.score, float)
    assert isinstance(r.metadata, dict)
    d = r.as_dict()
    for key in ("service_id", "service_name", "section", "content", "score", "metadata"):
        assert key in d
