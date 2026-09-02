import numpy as np

from rag.vectorstore import VectorStore, VectorStoreError


def test_store_length_matches_document_count(rag_store, rag_documents):
    assert len(rag_store) == len(rag_documents)


def test_documents_for_service_ids_returns_only_that_service(rag_store):
    rows = rag_store.documents_for_service_ids(["WLF00003248"])
    assert rows  # WLF00003248 has documents
    assert all(doc.service_id == "WLF00003248" for _, doc in rows)


def test_documents_for_service_ids_unknown_id_returns_empty(rag_store):
    assert rag_store.documents_for_service_ids(["WLF_DOES_NOT_EXIST"]) == []


def test_search_within_empty_candidates_returns_empty(rag_store, rag_embedder):
    qvec = rag_embedder.embed_query("누가 이용할 수 있나요?")
    assert rag_store.search_within(qvec, [], top_k=3) == []


def test_search_within_respects_section_filter(rag_store, rag_embedder):
    rows = rag_store.documents_for_service_ids(["WLF00003248"])
    row_indices = [r for r, _ in rows]
    qvec = rag_embedder.embed_query("신청 방법")
    results = rag_store.search_within(qvec, row_indices, top_k=5, section_filter=("support",))
    assert results
    assert all(doc.section == "support" for doc, _ in results)


def test_save_and_load_roundtrip_preserves_search_results(rag_store, rag_embedder, tmp_path):
    save_dir = tmp_path / "vectorstore"
    rag_store.save(save_dir)

    loaded = VectorStore.load(save_dir)
    assert len(loaded) == len(rag_store)
    assert loaded.model_name == rag_store.model_name
    assert loaded.dimension == rag_store.dimension

    qvec = rag_embedder.embed_query("어떻게 신청하나요?")
    rows = loaded.documents_for_service_ids(["WLF00002028"])
    row_indices = [r for r, _ in rows]

    original_rows = rag_store.documents_for_service_ids(["WLF00002028"])
    original_indices = [r for r, _ in original_rows]

    loaded_results = loaded.search_within(qvec, row_indices, top_k=3)
    original_results = rag_store.search_within(qvec, original_indices, top_k=3)

    assert [d.doc_id for d, _ in loaded_results] == [d.doc_id for d, _ in original_results]
    for (d1, s1), (d2, s2) in zip(loaded_results, original_results):
        assert np.isclose(s1, s2, atol=1e-5)


def test_load_missing_directory_raises(tmp_path):
    missing = tmp_path / "does_not_exist"
    try:
        VectorStore.load(missing)
        assert False, "expected VectorStoreError"
    except VectorStoreError:
        pass
