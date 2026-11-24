"""Batched embedding providers for semantic clustering and GraphRAG."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable

import numpy as np
from numpy.typing import NDArray
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer

from knowledgereduce.models import ExtractionError

FloatArray = NDArray[np.float32]


def _l2_normalize(matrix: NDArray[np.floating[Any]]) -> FloatArray:
    arr = np.asarray(matrix, dtype=np.float32)
    if arr.size == 0:
        return arr
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    return (arr / norms).astype(np.float32)


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for batched text embedding models."""

    def embed(self, texts: Sequence[str]) -> FloatArray:
        """Return an L2-normalized ``(N, D)`` float32 matrix for *texts*."""
        ...


class TfidfSVDProvider:
    """Offline scikit-learn TF-IDF + TruncatedSVD embedding provider."""

    def __init__(self, n_components: int = 128) -> None:
        self.n_components = n_components

    def embed(self, texts: Sequence[str]) -> FloatArray:
        """Compute L2-normalized dense embeddings for *texts* offline."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        cleaned = [t.strip() if t and t.strip() else "_" for t in texts]
        try:
            vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_features=8192)
            sparse = vec.fit_transform(cleaned)
        except ValueError:
            vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
            sparse = vec.fit_transform(cleaned)

        n_samples, n_features = sparse.shape
        if n_samples > 2 and n_features > self.n_components:
            k = min(self.n_components, n_samples - 1, n_features - 1)
            if k >= 2:
                svd = TruncatedSVD(n_components=k, random_state=42)
                dense = svd.fit_transform(sparse)
                return _l2_normalize(dense)
        return _l2_normalize(sparse.toarray())


class SentenceTransformerProvider:
    """Optional batched SentenceTransformer provider (requires ``[embeddings]`` extra)."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", batch_size: int = 64) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self._model: Any = None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ExtractionError(
                "sentence-transformers is not installed. "
                "Install it with `uv sync --extra embeddings`."
            ) from exc
        self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: Sequence[str]) -> FloatArray:
        """Compute L2-normalized sentence embeddings in a single batched pass."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        model = self._get_model()
        arr = model.encode(
            list(texts),
            normalize_embeddings=True,
            batch_size=self.batch_size,
            show_progress_bar=False,
        )
        return _l2_normalize(np.asarray(arr, dtype=np.float32))
