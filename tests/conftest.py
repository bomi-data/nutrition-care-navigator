import pytest

from recommender import load_services
from recommender.models import DesiredSupport, ServiceRecord, TriState, UserProfile


@pytest.fixture(scope="session")
def all_services():
    """All 85 rows from the real recommendation-ready CSV, loaded once."""
    return load_services()


# ---------------------------------------------------------------------------
# RAG fixtures -- shared session-scoped so the (slow: model load + embed)
# vector store is only built once for the whole test run, whether the test
# lives under tests/rag/ or elsewhere (e.g. tests/test_streamlit_rag_adapter.py).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def rag_services(all_services):
    return all_services


@pytest.fixture(scope="session")
def rag_documents(rag_services):
    from rag.document_builder import build_documents

    return build_documents(rag_services)


@pytest.fixture(scope="session")
def rag_embedder():
    """One real (local, no API key) embedding model instance, shared across
    the whole test session -- loading it is the expensive part."""
    from rag.embeddings import Embedder

    return Embedder()


@pytest.fixture(scope="session")
def rag_store(rag_documents, rag_embedder):
    from rag.vectorstore import VectorStore

    vectors = rag_embedder.embed_documents([d.content for d in rag_documents])
    return VectorStore.build(rag_documents, vectors, model_name=rag_embedder.model_name)


def make_service(**overrides) -> ServiceRecord:
    """Build a minimal synthetic ServiceRecord for isolated unit tests.

    Only fields relevant to a given test need to be overridden; everything
    else defaults to a "no conditions stated" service so tests aren't
    coupled to unrelated defaults changing.
    """
    from recommender.models import AgeConditionType, RegionScope

    defaults = dict(
        service_id="TEST0001",
        service_name="테스트 서비스",
        source_api="local",
        sido="강원특별자치도",
        sigungu="속초시",
        region_scope=RegionScope.SIGUNGU,
        min_age=None,
        max_age=None,
        age_condition_type=AgeConditionType.NONE,
        age_condition_note="",
        disability_required=TriState.UNKNOWN,
        low_income_required=TriState.UNKNOWN,
        single_household_required=TriState.UNKNOWN,
        homebound_or_mobility_condition=TriState.UNKNOWN,
        service_type=frozenset({"meal_support"}),
        service_type_primary="meal_support",
        nutritionist_involvement="not_specified",
        nutrition_relevance="",
        verification_level="A",
        contact="테스트 문의처",
        application_original="",
        target_original="",
        criteria_original="",
        support_original="",
        eligibility_summary="",
        support_summary="",
        data_quality_note="",
        special_eligibility_required=TriState.UNKNOWN,
        special_eligibility_note="",
    )
    defaults.update(overrides)
    return ServiceRecord(**defaults)


def make_user(**overrides) -> UserProfile:
    defaults = dict(
        sido="강원특별자치도",
        sigungu="속초시",
        age=75,
        has_disability=TriState.UNKNOWN,
        low_income_status=TriState.UNKNOWN,
        lives_alone=TriState.UNKNOWN,
        mobility_difficulty=TriState.UNKNOWN,
        meal_preparation_difficulty=TriState.UNKNOWN,
        recent_discharge=TriState.UNKNOWN,
        desired_support=frozenset({DesiredSupport.MEAL_SUPPORT}),
    )
    defaults.update(overrides)
    return UserProfile(**defaults)
