# RAG fixtures (rag_services/rag_documents/rag_embedder/rag_store) live in
# the top-level tests/conftest.py so they're shared with tests outside
# tests/rag/ too (e.g. tests/test_streamlit_rag_adapter.py) without
# rebuilding the vector store a second time. Nothing to add here.
