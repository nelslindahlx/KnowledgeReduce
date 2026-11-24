"""Unit tests for HashingEmbeddingProvider, TfidfSVDProvider, and SentenceTransformerProvider."""

from __future__ import annotations

import builtins
import sys
from types import ModuleType
from typing import Any

import numpy as np
import pytest

from knowledgereduce.models import ExtractionError
from knowledgereduce.resolve import (
    HashingEmbeddingProvider,
    SentenceTransformerProvider,
    TfidfSVDProvider,
)


def test_hashing_embedding_provider_stateless_and_normalized() -> None:
    provider = HashingEmbeddingProvider(n_features=64)
    assert provider.is_stateless is True
    assert provider.model_id == "hashing-v1-64"

    empty = provider.embed([])
    assert empty.shape == (0, 0)

    vecs = provider.embed(
        [
            "Civic Honors promotes community engagement.",
            "DuckDB stores columnar Parquet layers.",
            "   ",
        ]
    )
    assert vecs.shape == (3, 64)
    assert vecs.dtype == np.float32
    norms = np.linalg.norm(vecs[:2], axis=1)
    assert np.allclose(norms, 1.0, atol=1e-5)
    assert not np.isnan(vecs).any()


def test_tfidf_svd_provider_svd_and_fallback_branches() -> None:
    provider = TfidfSVDProvider(n_components=2)
    assert provider.is_stateless is False
    assert provider.model_id == "tfidf-svd"
    assert provider.embed([]).shape == (0, 0)

    # Trigger TruncatedSVD compression branch (>2 samples and >n_components features)
    dense = provider.embed(
        [
            "Civic Honors community student leadership",
            "DuckDB Parquet columnar storage engine",
            "NetworkX MultiDiGraph graph analytics",
            "PreserveDispute conflict resolution strategy",
        ]
    )
    assert dense.shape == (4, 2)
    assert np.allclose(np.linalg.norm(dense, axis=1), 1.0, atol=1e-5)

    # Punctuation/empty-vocab input triggers char_wb fallback
    fallback = provider.embed(["???", "!!!"])
    assert fallback.shape[0] == 2
    assert not np.isnan(fallback).any()


def test_sentence_transformer_provider_missing_and_mocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SentenceTransformerProvider(model_name="fake-mini", batch_size=8)
    assert provider.is_stateless is True
    assert provider.model_id == "sentence-transformers:fake-mini"
    assert provider.embed([]).shape == (0, 0)

    real_import = builtins.__import__

    def _blocked_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "sentence_transformers":
            raise ImportError("mock missing sentence_transformers")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _blocked_import)
    monkeypatch.delitem(sys.modules, "sentence_transformers", raising=False)
    with pytest.raises(ExtractionError, match="sentence-transformers"):
        provider.embed(["hello world"])

    monkeypatch.setattr(builtins, "__import__", real_import)

    class _FakeSTModel:
        init_count = 0

        def __init__(self, model_name: str) -> None:
            _FakeSTModel.init_count += 1
            self.model_name = model_name

        def encode(
            self,
            texts: list[str],
            *,
            normalize_embeddings: bool,
            batch_size: int,
            show_progress_bar: bool,
        ) -> np.ndarray[Any, Any]:
            assert normalize_embeddings is True
            assert batch_size == 8
            assert show_progress_bar is False
            return np.array([[3.0, 4.0] for _ in texts], dtype=np.float32)

    fake_mod = ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = _FakeSTModel  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_mod)

    cached_provider = SentenceTransformerProvider(model_name="fake-mini", batch_size=8)
    out1 = cached_provider.embed(["Civic Honors", "KnowledgeReduce"])
    out2 = cached_provider.embed(["Third claim"])
    assert _FakeSTModel.init_count == 1
    assert np.allclose(out1, np.array([[0.6, 0.8], [0.6, 0.8]], dtype=np.float32))
    assert np.allclose(out2, np.array([[0.6, 0.8]], dtype=np.float32))
