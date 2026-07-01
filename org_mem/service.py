"""Application service layer for org-mem use cases.

This module coordinates config, registry, storage, index freshness, validation
envelopes, and review workflows. MCP server code should call this layer.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from org_mem.config import Config
from org_mem.hints import SCHEMA_TEXT, SCHEMA_URI
from org_mem.index import IndexRebuildError, MemoryIndex
from org_mem.models import (
    EVIDENCE_REQUIREMENTS_HINT,
    ErrorDetail,
    LinkRelation,
    MemoryDraft,
    MemoryStatus,
    MemoryType,
    SearchQuery,
    ToolResponse,
)
from org_mem.registry import ProjectRegistry
from org_mem.storage import MemoryStorage, RevisionConflict

_MEMORY_TYPE_HINT = "Use one of: " + ", ".join(item.value for item in MemoryType) + "."
_STATUS_HINT = "Use one of: " + ", ".join(item.value for item in MemoryStatus) + "."
_LINK_RELATION_HINT = "Use one of: " + ", ".join(item.value for item in LinkRelation) + "."
_SORT_HINT = "Use updated_desc or updated_asc."
_LIMIT_HINT = "Use a positive integer limit."
_CURSOR_HINT = "Use the next_cursor value returned by memory_list."
_NOT_FOUND_HINT = "Use memory_search or memory_list to find a current memory_id."
_REVISION_HINT = "Call memory_read(memory_id) and pass its current revision as expected_revision."
_INDEX_HINT = "Fix the Org file named in the message, then retry the search."
_REVIEWED_REVISIONS_HINT = "Each reviewed_revisions item must be an object with memory_id and revision."
_BODY_SECTIONS_HINT = "Add the required top-level Org sections for the memory type."


def _error(code: str, message: str, field: str | None = None, hint: str | None = None) -> dict[str, Any]:
    """Build a repairable endpoint error envelope."""
    return ToolResponse.error(ErrorDetail(code=code, message=message, field=field, hint=hint)).to_dict()


def _not_found_error(exc: FileNotFoundError) -> dict[str, Any]:
    """Map missing memory IDs to a caller-actionable error."""
    return _error("not_found", str(exc), field="memory_id", hint=_NOT_FOUND_HINT)


def _revision_conflict_error(exc: RevisionConflict) -> dict[str, Any]:
    """Map stale expected revisions to the optimistic-locking repair path."""
    return _error("revision_conflict", str(exc), field="expected_revision", hint=_REVISION_HINT)


def _index_rebuild_error(exc: IndexRebuildError) -> dict[str, Any]:
    """Map malformed canonical Org files to a search repair path."""
    return _error("index_rebuild_failed", str(exc), field="index", hint=_INDEX_HINT)


def _storage_value_error(exc: ValueError) -> dict[str, Any]:
    """Map storage validation errors to field-specific repair hints."""
    message = str(exc)
    code = message.split(":", 1)[0]
    if code == "missing_required_evidence":
        return _error(code, message, field="evidence", hint=EVIDENCE_REQUIREMENTS_HINT)
    if code == "missing_required_section":
        return _error(code, message, field="body", hint=_BODY_SECTIONS_HINT)
    if code == "invalid_evidence":
        return _error(code, message, field="evidence", hint=EVIDENCE_REQUIREMENTS_HINT)
    return _error("invalid_memory_file", message, field="memory_id", hint="Read or fix the named Org memory file.")


def _invalid_memory_type_error(value: str) -> dict[str, Any]:
    """Return a repairable error for unsupported memory type filters."""
    return _error(
        "invalid_memory_type",
        f"invalid_memory_type: {value!r}",
        field="memory_type",
        hint=_MEMORY_TYPE_HINT,
    )


def _validate_memory_type_filter(memory_type: str | None) -> dict[str, Any] | None:
    if memory_type is None:
        return None
    try:
        MemoryType(memory_type)
    except ValueError:
        return _invalid_memory_type_error(memory_type)
    return None


def _validate_status_filter(status: str) -> dict[str, Any] | None:
    try:
        MemoryStatus(status)
    except ValueError:
        return _error(
            "invalid_status",
            f"invalid_status: {status!r}",
            field="status",
            hint=_STATUS_HINT,
        )
    return None


def _validate_limit(limit: int) -> dict[str, Any] | None:
    if limit <= 0:
        return _error("invalid_limit", f"invalid_limit: {limit!r}", field="limit", hint=_LIMIT_HINT)
    return None


def _validate_list_args(
    memory_type: str | None,
    status: str,
    sort: str,
    limit: int,
    cursor: str | None,
) -> dict[str, Any] | None:
    if error := _validate_memory_type_filter(memory_type):
        return error
    if error := _validate_status_filter(status):
        return error
    if error := _validate_limit(limit):
        return error
    if sort not in {"updated_desc", "updated_asc"}:
        return _error("invalid_sort", f"invalid_sort: {sort!r}", field="sort", hint=_SORT_HINT)
    if cursor is not None:
        try:
            int(cursor)
        except ValueError:
            return _error("invalid_cursor", f"invalid_cursor: {cursor!r}", field="cursor", hint=_CURSOR_HINT)
    return None


def _validate_search_args(memory_type: str | None, status: str, limit: int) -> dict[str, Any] | None:
    if error := _validate_memory_type_filter(memory_type):
        return error
    if error := _validate_status_filter(status):
        return error
    if error := _validate_limit(limit):
        return error
    return None


def _validate_reviewed_revisions(reviewed_revisions: list[dict[str, Any]]) -> dict[str, Any] | None:
    for index, item in enumerate(reviewed_revisions):
        label = f"reviewed_revisions[{index}]"
        if not isinstance(item, dict):
            return _error(
                "invalid_reviewed_revisions",
                f"invalid_reviewed_revisions: {label} must be an object",
                field="reviewed_revisions",
                hint=_REVIEWED_REVISIONS_HINT,
            )
        for key in ("memory_id", "revision"):
            if key not in item:
                return _error(
                    "invalid_reviewed_revisions",
                    f"invalid_reviewed_revisions: {label} missing required field: {key}",
                    field="reviewed_revisions",
                    hint=_REVIEWED_REVISIONS_HINT,
                )
        if not isinstance(item["memory_id"], str):
            return _error(
                "invalid_reviewed_revisions",
                f"invalid_reviewed_revisions: {label} field 'memory_id' must be a string",
                field="reviewed_revisions",
                hint=_REVIEWED_REVISIONS_HINT,
            )
        if not isinstance(item["revision"], int):
            return _error(
                "invalid_reviewed_revisions",
                f"invalid_reviewed_revisions: {label} field 'revision' must be an integer",
                field="reviewed_revisions",
                hint=_REVIEWED_REVISIONS_HINT,
            )
    return None


class MemoryService:
    """High-level application API backing MCP tools."""

    def __init__(self, config: Config) -> None:
        self.registry = ProjectRegistry(config)
        self.storage = MemoryStorage(config)
        self.index = MemoryIndex(config)

    def memory_project(self, root_path: str, name_hint: str | None = None) -> dict[str, Any]:
        """Activate or create a project memory tree."""
        try:
            info = self.registry.activate_project(Path(root_path), name_hint)
        except (OSError, ValueError) as exc:
            return _error("invalid_root_path", str(exc), field="root_path", hint="Pass a repository root path.")
        overview_path = info.project_dir / "project.org"
        project_overview = overview_path.read_text(encoding="utf-8") if overview_path.exists() else ""
        return ToolResponse.ok(
            project_id=info.project_id,
            root_path=str(info.root_path),
            project_dir=str(info.project_dir),
            project_overview=project_overview,
            schema_uri=SCHEMA_URI,
            schema_text=SCHEMA_TEXT,
        ).to_dict()

    def memory_write(self, draft: MemoryDraft) -> dict[str, Any]:
        """Write a memory and enqueue async reindex."""
        try:
            record = self.storage.write_memory(draft)
        except ValueError as exc:
            return _storage_value_error(exc)
        except OSError as exc:
            return _error("storage_error", str(exc), field="memory_root", hint="Check memory_root permissions.")
        self.index.enqueue_rebuild(draft.project_id)
        return ToolResponse.ok(
            memory_id=record.memory_id,
            path=str(record.path),
            revision=record.revision,
            indexed=False,
        ).to_dict()

    def memory_read(self, memory_id: str, include_links: bool = True) -> dict[str, Any]:
        """Read a memory by ID or path-like identifier."""
        try:
            record = self.storage.read_memory(memory_id)
        except FileNotFoundError as exc:
            return _not_found_error(exc)
        except ValueError as exc:
            return _storage_value_error(exc)
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
        if error := _validate_list_args(memory_type, status, sort, limit, cursor):
            return error
        try:
            page = self.index.list_memories(project_id, memory_type, status, tags, sort, limit, cursor)
        except ValueError as exc:
            return _error("invalid_cursor", str(exc), field="cursor", hint=_CURSOR_HINT)
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
        if error := _validate_search_args(memory_type, status, limit):
            return error
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
        try:
            results = self.index.search(sq)
        except IndexRebuildError as exc:
            return _index_rebuild_error(exc)
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
        if error := _validate_search_args(memory_type, status, limit):
            return error
        try:
            results = self.index.search_global(
                query,
                memory_type,
                status,
                tags,
                include_body,
                include_links,
                limit,
            )
        except IndexRebuildError as exc:
            return _index_rebuild_error(exc)
        return ToolResponse.ok(
            results=[dataclasses.asdict(r) for r in results]
        ).to_dict()

    def memory_update(
        self,
        memory_id: str,
        expected_revision: int,
        title: str | None = None,
        body: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update a memory with optimistic concurrency."""
        try:
            record = self.storage.update_memory(memory_id, expected_revision, title, body, evidence, tags)
        except RevisionConflict as exc:
            return _revision_conflict_error(exc)
        except FileNotFoundError as exc:
            return _not_found_error(exc)
        except ValueError as exc:
            return _storage_value_error(exc)
        except OSError as exc:
            return _error("storage_error", str(exc), field="memory_root", hint="Check memory_root permissions.")
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
        if not isinstance(relation, LinkRelation):
            return _error(
                "invalid_link_relation",
                f"invalid_link_relation: {relation!r}",
                field="relation",
                hint=_LINK_RELATION_HINT,
            )
        try:
            record = self.storage.link_memory(source_id, target_id, relation, note, expected_revision)
        except RevisionConflict as exc:
            return _revision_conflict_error(exc)
        except FileNotFoundError as exc:
            return _not_found_error(exc)
        self.index.enqueue_rebuild(record.project_id)
        return ToolResponse.ok(memory_id=record.memory_id, revision=record.revision).to_dict()

    def memory_archive(
        self,
        memory_id: str,
        expected_revision: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Archive a memory while preserving its Org file."""
        try:
            record = self.storage.archive_memory(memory_id, expected_revision, reason)
        except RevisionConflict as exc:
            return _revision_conflict_error(exc)
        except FileNotFoundError as exc:
            return _not_found_error(exc)
        except ValueError as exc:
            return _storage_value_error(exc)
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
        if error := _validate_reviewed_revisions(reviewed_revisions):
            return error
        try:
            record = self.storage.write_project_overview(
                project_id, overview_body, reviewed_revisions, expected_revision
            )
        except RevisionConflict as exc:
            return _revision_conflict_error(exc)
        except ValueError as exc:
            return _storage_value_error(exc)
        except OSError as exc:
            return _error("storage_error", str(exc), field="memory_root", hint="Check memory_root permissions.")
        self.index.enqueue_rebuild(project_id)
        return ToolResponse.ok(
            memory_id=record.memory_id,
            revision=record.revision,
            path=str(record.path),
        ).to_dict()
