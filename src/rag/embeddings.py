"""Local multilingual embedding model wrapper.

Model choice (docs/rag_retrieval_v1_report.md §6 has the full comparison):
``intfloat/multilingual-e5-small`` -- a local sentence-transformers model,
no API key, no per-call cost. Chosen specifically because it is trained for
*asymmetric* retrieval (short question vs. longer passage), which is exactly
this project's shape (section-aware query -> official-source passage),
unlike general-purpose STS models. It requires the "query: " / "passage: "
prefix convention from its model card -- ``embed_query``/``embed_documents``
apply that automatically so callers never have to remember it.
"""

from __future__ import annotations

from typing import List, Sequence

import numpy as np

DEFAULT_MODEL_NAME = "intfloat/multilingual-e5-small"
EMBEDDING_DIM = 384


class Embedder:
    """Thin wrapper around a sentence-transformers model with e5's
    query/passage prefix convention baked in."""

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME):
        # Imported lazily so importing src.rag doesn't require torch/
        # sentence-transformers unless embedding is actually used (e.g. pure
        # document_builder tests stay fast and dependency-light).
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def embed_documents(self, texts: Sequence[str]) -> np.ndarray:
        prefixed = [f"passage: {t}" for t in texts]
        return np.asarray(
            self._model.encode(prefixed, normalize_embeddings=True, show_progress_bar=False)
        )

    def embed_query(self, text: str) -> np.ndarray:
        vec = self._model.encode(
            [f"query: {text}"], normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vec[0])

    def dimension(self) -> int:
        return self._model.get_embedding_dimension()
