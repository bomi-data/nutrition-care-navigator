"""Build the RAG vector store from
data/processed/welfare_services_recommendation_ready.csv and save it to
data/vectorstore/ so later runs can load() instead of re-embedding.

Usage:
    python -m rag.build_index
"""

from __future__ import annotations

import time
from collections import Counter

from recommender.loader import load_services

from .document_builder import build_documents, count_excluded_sections
from .embeddings import Embedder
from .vectorstore import DEFAULT_VECTORSTORE_DIR, VectorStore


def main() -> None:
    t0 = time.time()
    services = load_services()

    documents = build_documents(services)
    excluded = count_excluded_sections(services)

    embedder = Embedder()
    vectors = embedder.embed_documents([d.content for d in documents])

    store = VectorStore.build(documents, vectors, model_name=embedder.model_name)
    build_seconds = time.time() - t0

    store.save(DEFAULT_VECTORSTORE_DIR)

    section_counts = Counter(d.section for d in documents)

    print(f"services: {len(services)}")
    print(f"documents: {len(documents)}")
    for section, count in sorted(section_counts.items()):
        print(f"  {section}: {count}")
    print(f"excluded empty sections: {excluded}")
    print(f"embedding dimension: {embedder.dimension()}")
    print(f"build time: {build_seconds:.2f}s")
    print(f"saved to: {DEFAULT_VECTORSTORE_DIR}")


if __name__ == "__main__":
    main()
