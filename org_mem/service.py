"""Application service layer for org-mem use cases.

This module coordinates config, registry, storage, index freshness, validation
envelopes, and review workflows. MCP server code should call this layer.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from org_mem.config import Config
from org_mem.index import MemoryIndex
from org_mem.models import ErrorDetail, LinkRelation, MemoryDraft, SearchQuery, ToolResponse
from org_mem.registry import ProjectRegistry
from org_mem.storage import MemoryStorage, RevisionConflict


class MemoryService:
    """High-level application API backing MCP tools."""

    def __init__(self, config: Config) -> None:
        self.registry = ProjectRegistry(config)
        self.storage = MemoryStorage(config)
        self.index = MemoryIndex(config)

    def memory_project(self, root_path: str, name_hint: str | None = None) -> dict[str, Any]:
        """Activate or create a project memory tree."""
        info = self.registry.activate_project(Path(root_path), name_hint)
        return ToolResponse.ok(
            project_id=info.project_id,
            root_path=str(info.root_path),
            project_dir=str(info.project_dir),
        ).to_dict()

    def memory_write(self, draft: MemoryDraft) -> dict[str, Any]:
        """Write a memory and enqueue async reindex."""
        try:
            record = self.storage.write_memory(draft)
        except ValueError as exc:
            code = str(exc).split(":")[0]
            return ToolResponse.error(ErrorDetail(code=code, message=str(exc))).to_dict()
        self.index.enqueue_rebuild(draft.project_id)
        return ToolResponse.ok(
            memory_id=record.memory_id,
            path=str(record.path),
            revision=record.revision,
            indexed=False,
        ).to_dict()

    def memory_read(self, memory_id: str, include_links: bool = True) -> dict[str, Any]:
        """Read a memory by ID or path-like identifier."""
        record = self.storage.read_memory(memory_id)
        payload: dict[str, Any] = {
            "memory_id": record.memory_id,
            "project_id": record.project_id,
            "memory_type": record.memory_type.value,
            "title": record.title,
            "body": record.body,
            "status": record.status.value,
            "revision": record.revision,
            "tags": record.tags,
            "path": str(record.path),
        }
        if include_links:
            payload["links"] = [dataclasses.asdict(lk) for lk in record.links]
        return ToolResponse.ok(**payload).to_dict()

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
        page = self.index.list_memories(project_id, memory_type, status, tags, sort, limit, cursor)
        items = [
            {
                "memory_id": r.memory_id,
                "title": r.title,
                "memory_type": r.memory_type.value,
                "status": r.status.value,
                "revision": r.revision,
                "tags": r.tags,
                "path": str(r.path),
            }
            for r in page.items
        ]
        return ToolResponse.ok(items=items, next_cursor=page.next_cursor).to_dict()

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
        sq = SearchQuery(
            project_id=project_id,
            query=query,
            memory_type=memory_type,
            status=status,
            tags=tags or [],
            include_body=include_body,
            include_links=include_links,
            limit=limit,
        )
        results = self.index.search(sq)
        return ToolResponse.ok(
            results=[dataclasses.asdict(r) for r in results]
        ).to_dict()

    def memory_global_search(
        self,
        query: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        include_body: bool = False,
        include_links: bool = False,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search memories across all projects after blocking for fresh indexes."""
        results = self.index.search_global(query, memory_type, status, tags, include_body, include_links, limit)
        return ToolResponse.ok(
            results=[dataclasses.asdict(r) for r in results]
        ).to_dict()

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
        try:
            record = self.storage.update_memory(memory_id, expected_revision, title, body, evidence, tags)
        except RevisionConflict as exc:
            return ToolResponse.error(ErrorDetail(code="revision_conflict", message=str(exc))).to_dict()
        self.index.enqueue_rebuild(record.project_id)
        return ToolResponse.ok(memory_id=record.memory_id, revision=record.revision).to_dict()

    def memory_link(
        self,
        source_id: str,
        target_id: str,
        relation: LinkRelation,
        note: str | None = None,
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Create a typed link between two memories."""
        try:
            record = self.storage.link_memory(source_id, target_id, relation, note, expected_revision)
        except (RevisionConflict, FileNotFoundError) as exc:
            code = "revision_conflict" if isinstance(exc, RevisionConflict) else "not_found"
            return ToolResponse.error(ErrorDetail(code=code, message=str(exc))).to_dict()
        self.index.enqueue_rebuild(record.project_id)
        return ToolResponse.ok(memory_id=record.memory_id, revision=record.revision).to_dict()

    def memory_archive(self, memory_id: str, expected_revision: int, reason: str | None = None) -> dict[str, Any]:
        """Archive a memory while preserving its Org file."""
        try:
            record = self.storage.archive_memory(memory_id, expected_revision, reason)
        except RevisionConflict as exc:
            return ToolResponse.error(ErrorDetail(code="revision_conflict", message=str(exc))).to_dict()
        self.index.enqueue_rebuild(record.project_id)
        return ToolResponse.ok(
            memory_id=record.memory_id,
            revision=record.revision,
            path=str(record.path),
        ).to_dict()

    def memory_review(
        self,
        project_id: str,
        overview_body: str,
        reviewed_revisions: list[dict[str, Any]],
        expected_revision: int | None = None,
    ) -> dict[str, Any]:
        """Write project.org from caller-provided overview synthesis."""
        try:
            record = self.storage.write_project_overview(
                project_id, overview_body, reviewed_revisions, expected_revision
            )
        except RevisionConflict as exc:
            return ToolResponse.error(ErrorDetail(code="revision_conflict", message=str(exc))).to_dict()
        self.index.enqueue_rebuild(project_id)
        return ToolResponse.ok(
            memory_id=record.memory_id,
            revision=record.revision,
            path=str(record.path),
        ).to_dict()
