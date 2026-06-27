"""Embedding provider interfaces and hybrid retrieval helpers.

This module is milestone 2. It must keep provider-specific code isolated from
storage, FTS indexing, and MCP response handling.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from org_mem.models import RankedMemoryId


class EmbeddingProvider(ABC):
    """Abstract text embedding provider."""

    @abstractmethod
    def embed_text(self, text: str) -> list[float]:
        """Embed one text string into a dense vector."""
        # TODO: Normalize text, call the configured provider, validate vector
        # dimensions, and return JSON-serializable floats.
        raise NotImplementedError("TODO: implement embedding provider contract")


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local default embedding provider."""

    def __init__(self, model: str) -> None:
        """Create a local embedding provider for one model name."""
        # TODO: Load or configure the local embedding model lazily so startup
        # stays cheap for FTS-only workflows.
        raise NotImplementedError("TODO: implement local embedding provider initialization")

    def embed_text(self, text: str) -> list[float]:
        """Embed text with the configured local model."""
        # TODO: Run local inference and return a stable dense vector.
        raise NotImplementedError("TODO: implement local embedding generation")


class OpenAICompatibleEmbeddingProvider(EmbeddingProvider):
    """OpenAI-compatible remote embedding provider."""

    def __init__(self, base_url: str, api_key: str | None, model: str) -> None:
        """Create an OpenAI-compatible embedding provider."""
        # TODO: Validate api_key/base_url/model, prepare an HTTP client, and
        # keep secrets out of repr/logging.
        raise NotImplementedError("TODO: implement OpenAI-compatible provider initialization")

    def embed_text(self, text: str) -> list[float]:
        """Embed text through an OpenAI-compatible API."""
        # TODO: Send a embeddings request, handle provider errors, and return
        # provider vectors as plain floats.
        raise NotImplementedError("TODO: implement remote embedding request")


class HybridSearchRanker:
    """Fuse lexical and vector rankings for hybrid search."""

    def fuse(self, lexical_ids: list[str], vector_ids: list[str], limit: int) -> list[RankedMemoryId]:
        """Fuse two ranked ID lists with Reciprocal Rank Fusion."""
        # TODO: Apply RRF with a fixed k parameter, merge duplicate IDs, sort by
        # fused score descending, and truncate to limit.
        raise NotImplementedError("TODO: implement Reciprocal Rank Fusion")
