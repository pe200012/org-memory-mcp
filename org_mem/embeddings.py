"""Embedding provider interfaces and hybrid retrieval helpers.

This module is milestone 2. It must keep provider-specific code isolated from
storage, FTS indexing, and MCP response handling.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
from abc import ABC, abstractmethod

from org_mem.models import RankedMemoryId

_RRF_K = 60


class EmbeddingProvider(ABC):
    """Abstract text embedding provider."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed one text string into a dense vector."""


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local default embedding provider using a deterministic hash embedding."""

    _DIM = 128

    def __init__(self, model: str) -> None:
        self._model = model  # ponytail: model name stored for future lazy-load

    def embed_text(self, text: str) -> list[float]:
        raw = hashlib.sha256(text.strip().lower().encode()).digest()
        # Tile to _DIM bytes then map to [-1, 1]
        tiled = (raw * (self._DIM // len(raw) + 1))[: self._DIM]
        return [(b / 127.5) - 1.0 for b in tiled]


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible remote embedding provider."""

    def __init__(self, base_url: str, api_key: str | None, model: str) -> None:
        if api_key is None:
            raise ValueError("api_key is required for OpenAICompatibleEmbeddingProvider")
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key

    def __repr__(self) -> str:
        return f"OpenAICompatibleEmbeddingProvider(base_url={self._base_url!r}, model={self._model!r})"

    def embed_text(self, text: str) -> list[float]:
        payload = json.dumps({"input": text.strip(), "model": self._model}).encode()
        req = urllib.request.Request(
            f"{self._base_url}/embeddings",
            data=payload,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        return [float(v) for v in data["data"][0]["embedding"]]


class HybridSearchRanker:
    """Fuse lexical and vector rankings for hybrid search."""

    def fuse(self, lexical_ids: list[str], vector_ids: list[str], limit: int) -> list[RankedMemoryId]:
        """Fuse two ranked ID lists with Reciprocal Rank Fusion."""
        scores: dict[str, float] = {}
        for rank, mid in enumerate(lexical_ids, 1):
            scores[mid] = scores.get(mid, 0.0) + 1.0 / (_RRF_K + rank)
        for rank, mid in enumerate(vector_ids, 1):
            scores[mid] = scores.get(mid, 0.0) + 1.0 / (_RRF_K + rank)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [RankedMemoryId(memory_id=mid, score=score) for mid, score in ranked[:limit]]
