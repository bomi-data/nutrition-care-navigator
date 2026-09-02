"""Local FAISS-backed vector store for RAGDocuments, with save/load so the
85-service corpus is embedded once and reused across process runs.

Vector store choice (docs/rag_retrieval_v1_report.md §7): FAISS
(``IndexFlatIP`` -- exact, brute-force inner-product search). At this scale
(a few hundred documents) an approximate index buys nothing and only adds
risk; ``IndexFlatIP`` is exact and, combined with L2-normalized embeddings
(``embeddings.Embedder`` already normalizes), inner product == cosine
similarity.

Every query in this project must be restricted to a specific set of
service_ids chosen beforehand by the recommender (docs/rag_retrieval_v1_report
.md §8-9) -- this store never exposes a "search the whole 85-service corpus"
path to a caller that hasn't already narrowed to specific service_ids, so
another service's document can never leak into a result set by construction,
not just by post-hoc filtering.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import numpy as np

from .models import RAGDocument

DEFAULT_VECTORSTORE_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "vectorstore"
)

_INDEX_FILENAME = "index.faiss"
_DOCS_FILENAME = "documents.jsonl"
_META_FILENAME = "meta.json"


class VectorStoreError(Exception):
    """Raised when the on-disk vector store is missing or malformed."""


class VectorStore:
    def __init__(self, index, documents: List[RAGDocument], model_name: str, dimension: int):
        self._index = index
        self._documents = documents
        self.model_name = model_name
        self.dimension = dimension

    # -- build -----------------------------------------------------------

    @classmethod
    def build(cls, documents: Sequence[RAGDocument], vectors: np.ndarray, model_name: str) -> "VectorStore":
        import faiss

        vectors = np.asarray(vectors, dtype="float32")
        if len(documents) != vectors.shape[0]:
            raise ValueError("documents and vectors must have the same length")

        dimension = vectors.shape[1]
        index = faiss.IndexFlatIP(dimension)
        index.add(vectors)
        return cls(index=index, documents=list(documents), model_name=model_name, dimension=dimension)

    # -- persistence -------------------------------------------------------

    def save(self, dir_path: Path = DEFAULT_VECTORSTORE_DIR) -> None:
        import faiss

        dir_path = Path(dir_path)
        dir_path.mkdir(parents=True, exist_ok=True)

        # faiss.write_index() opens the path with its own C++ fopen(), which
        # cannot handle non-ASCII (e.g. Korean) characters anywhere in the
        # path on Windows ("Illegal byte sequence"). Serialize to bytes in
        # memory instead and write those bytes through Python's own file
        # I/O, which does handle Unicode paths correctly on Windows.
        raw = faiss.serialize_index(self._index)
        with open(dir_path / _INDEX_FILENAME, "wb") as f:
            f.write(raw.tobytes())

        with open(dir_path / _DOCS_FILENAME, "w", encoding="utf-8") as f:
            for doc in self._documents:
                f.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")

        with open(dir_path / _META_FILENAME, "w", encoding="utf-8") as f:
            json.dump(
                {"model_name": self.model_name, "dimension": self.dimension, "doc_count": len(self._documents)},
                f,
                ensure_ascii=False,
                indent=2,
            )

    @classmethod
    def load(cls, dir_path: Path = DEFAULT_VECTORSTORE_DIR) -> "VectorStore":
        import faiss

        dir_path = Path(dir_path)
        index_path = dir_path / _INDEX_FILENAME
        docs_path = dir_path / _DOCS_FILENAME
        meta_path = dir_path / _META_FILENAME
        for p in (index_path, docs_path, meta_path):
            if not p.exists():
                raise VectorStoreError(f"Vector store file missing: {p}. Run the build script first.")

        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)

        documents: List[RAGDocument] = []
        with open(docs_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                documents.append(RAGDocument(**json.loads(line)))

        # Mirror of the save() workaround: read raw bytes via Python I/O
        # (Unicode-path safe) and deserialize in memory, instead of
        # faiss.read_index() which fails on non-ASCII paths on Windows.
        with open(index_path, "rb") as f:
            raw = np.frombuffer(f.read(), dtype="uint8")
        index = faiss.deserialize_index(raw)
        if index.ntotal != len(documents):
            raise VectorStoreError(
                f"Vector store is inconsistent: {index.ntotal} vectors vs {len(documents)} documents."
            )

        return cls(index=index, documents=documents, model_name=meta["model_name"], dimension=meta["dimension"])

    # -- lookup ------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._documents)

    def all_service_ids(self) -> set:
        return {d.service_id for d in self._documents}

    def documents_for_service_ids(self, service_ids: Iterable[str]) -> List[Tuple[int, RAGDocument]]:
        """Row-index + document pairs restricted to the given service_ids.

        This is the single choke point that guarantees cross-service
        isolation: everything downstream (search) only ever sees vectors
        reconstructed from these indices.
        """
        wanted = set(service_ids)
        return [(i, d) for i, d in enumerate(self._documents) if d.service_id in wanted]

    def search_within(
        self,
        query_vector: np.ndarray,
        candidate_rows: Sequence[int],
        top_k: int,
        section_filter: Optional[Sequence[str]] = None,
    ) -> List[Tuple[RAGDocument, float]]:
        """Cosine-similarity search restricted to ``candidate_rows`` (row
        indices into this store), optionally further restricted to one or
        more sections. Vectors are reconstructed directly from the FAISS
        index -- no vector outside ``candidate_rows`` is ever read or scored.
        """
        if not candidate_rows:
            return []

        rows = list(candidate_rows)
        if section_filter is not None:
            allowed = set(section_filter)
            rows = [r for r in rows if self._documents[r].section in allowed]
        if not rows:
            return []

        vectors = np.asarray([self._index.reconstruct(int(r)) for r in rows], dtype="float32")
        query_vector = np.asarray(query_vector, dtype="float32")
        scores = vectors @ query_vector

        order = np.argsort(-scores)[: max(0, top_k)]
        return [(self._documents[rows[i]], float(scores[i])) for i in order]
