"""Tests for milestone 2 embedding and hybrid-search contracts."""

from __future__ import annotations

import pytest

from org_mem.embeddings import (
    EmbeddingProvider,
    HybridSearchRanker,
    LocalEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
)


def test_embedding_provider_interface_returns_vector() -> None:
    provider: EmbeddingProvider = LocalEmbeddingProvider(model="local-test")

    vector = provider.embed_text("heap preservation decision")

    assert isinstance(vector, list)
    assert vector
    assert all(isinstance(value, float) for value in vector)


def test_openai_compatible_provider_requires_api_key() -> None:
    with pytest.raises(ValueError, match="api_key"):
        OpenAICompatibleEmbeddingProvider(base_url="https://api.example.test/v1", api_key=None, model="text-embedding")


def test_hybrid_ranker_uses_reciprocal_rank_fusion() -> None:
    ranker = HybridSearchRanker()

    ranked = ranker.fuse(
        lexical_ids=["a", "b", "c"],
        vector_ids=["c", "a", "d"],
        limit=3,
    )

    assert [item.memory_id for item in ranked] == ["a", "c", "b"]
    assert ranked[0].score > ranked[-1].score
