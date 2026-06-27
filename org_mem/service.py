"""Application service layer for org-mem use cases.

This module coordinates config, registry, storage, index freshness, validation
envelopes, and review workflows. MCP server code should call this layer.
"""

from __future__ import annotations

from typing import Any

from org_mem.config import Config
from org_mem.index import MemoryIndex
from org_mem.models import LinkRelation, MemoryDraft
from org_mem.registry import ProjectRegistry
from org_mem.storage import MemoryStorage


class MemoryService:
    """High-level application API backing MCP tools."""

    def __init__(self, config: Config) -> None:
        """Create service dependencies for one config."""
        # TODO: Construct ProjectRegistry, MemoryStorage, and MemoryIndex with
        # shared config; keep dependencies injectable later for tests.
        raise NotImplementedError("TODO: implement service initialization")

    def memory_project(self, root_path: str, name_hint: str | None = None) -> dict[str, Any]:
        """Activate or create a project memory tree."""
        # TODO: Call ProjectRegistry.activate_project and serialize ProjectInfo
        # into a uniform success/error envelope.
        raise NotImplementedError("TODO: implement memory_project service method")

    def memory_write(self, draft: MemoryDraft) -> dict[str, Any]:
        """Write a memory and enqueue async reindex."""
        # TODO: Validate/write through storage, enqueue project rebuild, and
        # return ok envelope with indexed=false and generation metadata.
        raise NotImplementedError("TODO: implement memory_write service method")

    def memory_read(self, memory_id: str, include_links: bool = True) -> dict[str, Any]:
        """Read a memory by ID or path-like identifier."""
        # TODO: Read from canonical storage and serialize full body plus links
        # when requested.
        raise NotImplementedError("TODO: implement memory_read service method")

    def memory_list(
        self,
        project_id: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        sort: str = "updated_desc",
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List memories deterministically."""
        # TODO: Delegate to MemoryIndex.list_memories and wrap page/cursor in
        # an ok envelope.
        raise NotImplementedError("TODO: implement memory_list service method")

    def memory_search(
        self,
        project_id: str,
        query: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        include_body: bool = False,
        include_links: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search memories after blocking for fresh derived indexes."""
        # TODO: Build SearchQuery, call MemoryIndex.search, and serialize
        # compact ranked results with optional full bodies/links.
        raise NotImplementedError("TODO: implement memory_search service method")

    def memory_update(
        self,
        memory_id: str,
        expected_revision: int,
        title: str | None = None,
        body: str | None = None,
        evidence: list[dict[str, str]] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update a memory with optimistic concurrency."""
        # TODO: Delegate to storage, translate RevisionConflict into structured
        # error envelope, enqueue reindex on success.
        raise NotImplementedError("TODO: implement memory_update service method")

    def memory_link(
        self,
        source_id: str,
        target_id: str,
        relation: LinkRelation,
        note: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create a typed link between two memories."""
        # TODO: Validate target existence, write source update, enqueue reindex,
        # and return the new source revision.
        raise NotImplementedError("TODO: implement memory_link service method")

    def memory_archive(self, memory_id: str, expected_revision: int, reason: str | None = None) -> dict[str, Any]:
        """Archive a memory while preserving its Org file."""
        # TODO: Call storage archive, enqueue reindex, and return revision/path
        # metadata in the standard envelope.
        raise NotImplementedError("TODO: implement memory_archive service method")

    def memory_review(
        self,
        project_id: str,
        overview_body: str,
        reviewed_revisions: list[dict[str, Any]],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Write project.org from caller-provided overview synthesis."""
        # TODO: Validate reviewed revisions, write project overview through
        # storage, enqueue reindex, and return overview record metadata.
        raise NotImplementedError("TODO: implement memory_review service method")
