from rag.document_builder import CHUNK_SIZE, build_documents, count_excluded_sections
from rag.models import ALL_SECTIONS


def test_builds_one_document_per_nonempty_section(rag_services, rag_documents):
    # target/criteria/support are 100% non-empty in the real CSV -> one per
    # service. Was 85 before the Cheonan enrichment merge
    # (docs/cheonan_official_enrichment_report.md); both new rows also have
    # non-empty target/criteria/support, so the count grew to 87.
    by_section = {}
    for d in rag_documents:
        by_section.setdefault(d.section, set()).add(d.service_id)

    assert len(by_section["target"]) == 87
    assert len(by_section["criteria"]) == 87
    assert len(by_section["support"]) == 87
    # application_original has real "[]" placeholders -> fewer than the total.
    assert len(by_section["application"]) < 87


def test_excluded_section_count_matches_known_placeholder_count(rag_services):
    # 25 rows have application_original == "[]" exactly (measured directly
    # against the CSV -- see docs/rag_retrieval_v1_report.md §3).
    assert count_excluded_sections(rag_services) == 25


def test_every_document_has_required_metadata(rag_documents):
    for d in rag_documents:
        meta = d.metadata()
        for key in ("service_id", "service_name", "section", "service_type_primary", "verification_level", "source_type"):
            assert meta[key] is not None
            assert meta[key] != ""
        assert meta["section"] in ALL_SECTIONS


def test_doc_ids_are_unique(rag_documents):
    ids = [d.doc_id for d in rag_documents]
    assert len(ids) == len(set(ids))


def test_no_empty_or_placeholder_content(rag_documents):
    for d in rag_documents:
        assert d.content.strip() not in ("", "[]")


def test_long_section_is_split_into_multiple_chunks(rag_documents):
    # WLF00005102 support_original is 1286 chars in the real CSV -- the
    # longest field in the corpus -- and must be sub-chunked, not embedded
    # as one giant blob.
    chunks = [d for d in rag_documents if d.service_id == "WLF00005102" and d.section == "support"]
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.content) <= CHUNK_SIZE * 1.5
        assert c.chunk_count == len(chunks)


def test_short_section_is_not_split(rag_documents):
    # target_original for WLF00002523 is a 4-character string ("저소득층") --
    # far under the chunk threshold, must stay a single chunk.
    chunks = [d for d in rag_documents if d.service_id == "WLF00002523" and d.section == "target"]
    assert len(chunks) == 1
    assert chunks[0].content == "저소득층"


def test_service_with_null_application_produces_no_application_document(rag_documents):
    # WLF00003518's application_original is exactly "[]" in the real CSV.
    app_docs = [d for d in rag_documents if d.service_id == "WLF00003518" and d.section == "application"]
    assert app_docs == []
    # but its other sections must still exist.
    other_docs = [d for d in rag_documents if d.service_id == "WLF00003518" and d.section != "application"]
    assert len(other_docs) >= 3
