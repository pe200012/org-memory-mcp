"""Canonical Org file storage operations.

This module owns safe writes, reads, updates, archives, typed links, project
overview writes, revision checks, and path containment under the memory root.
"""

from __future__ import annotations

from typing import Any

from org_mem.config import Config
from org_mem.models import LinkRelation, MemoryDraft, MemoryRecord


class RevisionConflict(RuntimeError):
    """Raised when `expected_revision` differs from the stored revision."""


class MemoryStorage:
    """File-backed storage for canonical Org memory records."""

    def __init__(self, config: Config) -> None:
        """Create storage bound to one resolved config."""
        # TODO: Store config, prepare memory root paths, and load lightweight
        # ID-to-path lookup helpers without touching SQLite.
        raise NotImplementedError("TODO: implement memory storage initialization")

    def write_memory(self, draft: MemoryDraft) -> MemoryRecord:
        """Validate and write a new Org memory file."""
        # TODO: Validate draft, generate UUID and readable filename, serialize
        # Org, write atomically, and return the parsed MemoryRecord.
        raise NotImplementedError("TODO: implement canonical memory write")

    def read_memory(self, memory_id: str) -> MemoryRecord:
        """Read one memory by Org ID."""
        # TODO: Locate memory_id by scanning canonical files or using a local
        # ID map, parse Org, and return the MemoryRecord.
        raise NotImplementedError("TODO: implement memory read by ID")

    def update_memory(
        self,
        memory_id: str,
        expected_revision: int,
        title: str | None = None,
        body: str | None = None,
        evidence: list[dict[str, str]] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        """Update an existing memory with optimistic concurrency."""
        # TODO: Read current record, compare expected_revision, merge provided
        # fields, increment REVISION, update UPDATED, validate, and rewrite.
        raise NotImplementedError("TODO: implement revision-aware memory update")

    def link_memory(
        self,
        source_id: str,
        target_id: str,
        relation: LinkRelation,
        note: str | None = None,
        expected_revision: int | None = None,
    ) -> MemoryRecord:
        """Create a typed Org ID link from one memory to another."""
        # TODO: Validate both IDs, enforce closed relation vocabulary, add link
        # under Related memories, and increment the source revision.
        raise NotImplementedError("TODO: implement typed memory link update")

    def archive_memory(
        self,
        memory_id: str,
        expected_revision: int,
        reason: str | None = None,
    ) -> MemoryRecord:
        """Archive a memory while keeping the Org file."""
        # TODO: Set STATUS=archived, append/archive reason metadata, update
        # timestamps, increment revision, and preserve the file path.
        raise NotImplementedError("TODO: implement archive-only lifecycle update")

    def write_project_overview(
        self,
        project_id: str,
        overview_body: str,
        reviewed_revisions: list[dict[str, Any]],
        expected_revision: int | None = None,
    ) -> MemoryRecord:
        """Write `project.org` from caller-provided review synthesis."""
        # TODO: Validate reviewed IDs/revisions, write project.org with review
        # metadata, enforce expected_revision if the overview exists.
        raise NotImplementedError("TODO: implement project overview review write")
