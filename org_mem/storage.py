"""Canonical Org file storage operations.

This module owns safe writes, reads, updates, archives, typed links, project
overview writes, revision checks, and path containment under the memory root.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

from org_mem.config import Config
from org_mem.models import LinkRelation, MemoryDraft, MemoryRecord, MemoryType
from org_mem.org_file import parse_memory, serialize_memory, validate_memory_draft


class RevisionConflict(RuntimeError):
    """Raised when `expected_revision` differs from the stored revision."""


def _type_dir(memory_type: MemoryType) -> str:
    return memory_type.value + "s"


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


class MemoryStorage:
    """File-backed storage for canonical Org memory records."""

    def __init__(self, config: Config) -> None:
        self._root = config.memory_root
        # ponytail: in-process dict as id->path cache; rebuilt lazily by rglob scan
        self._id_map: dict[str, Path] = {}

    def _locate(self, memory_id: str) -> Path:
        if memory_id in self._id_map:
            return self._id_map[memory_id]
        for p in self._root.rglob("*.org"):
            if f":ID:       {memory_id}" in p.read_text(encoding="utf-8"):
                self._id_map[memory_id] = p
                return p
        raise FileNotFoundError(f"memory_id {memory_id!r} not found")

    def write_memory(self, draft: MemoryDraft) -> MemoryRecord:
        """Validate and write a new Org memory file."""
        validate_memory_draft(draft)
        memory_id = str(uuid.uuid4())
        type_dir = self._root / "projects" / draft.project_id / _type_dir(draft.memory_type)
        type_dir.mkdir(parents=True, exist_ok=True)
        path = type_dir / f"{_slug(draft.title)}.org"
        org_text = serialize_memory(draft).replace(":ID:       ", f":ID:       {memory_id}", 1)
        path.write_text(org_text, encoding="utf-8")
        self._id_map[memory_id] = path
        return dc_replace(parse_memory(org_text), path=path, memory_id=memory_id)

    def read_memory(self, memory_id: str) -> MemoryRecord:
        """Read one memory by Org ID."""
        path = self._locate(memory_id)
        return dc_replace(parse_memory(path.read_text(encoding="utf-8")), path=path)

    def _rewrite(self, path: Path, text: str, new_revision: int) -> MemoryRecord:
        text = re.sub(r":REVISION:\s+\d+", f":REVISION:        {new_revision}", text)
        path.write_text(text, encoding="utf-8")
        return dc_replace(parse_memory(text), path=path)

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
        path = self._locate(memory_id)
        text = path.read_text(encoding="utf-8")
        record = parse_memory(text)
        if record.revision != expected_revision:
            raise RevisionConflict(f"expected {expected_revision}, got {record.revision}")
        if title is not None:
            text = re.sub(r"#\+title:.*", f"#+title: {title}", text)
        return self._rewrite(path, text, record.revision + 1)

    def link_memory(
        self,
        source_id: str,
        target_id: str,
        relation: LinkRelation,
        note: str | None = None,
        expected_revision: int | None = None,
    ) -> MemoryRecord:
        """Create a typed Org ID link from one memory to another."""
        target_path = self._locate(target_id)
        target_record = parse_memory(target_path.read_text(encoding="utf-8"))

        source_path = self._locate(source_id)
        source_text = source_path.read_text(encoding="utf-8")
        source_record = parse_memory(source_text)
        if expected_revision is not None and source_record.revision != expected_revision:
            raise RevisionConflict(f"expected {expected_revision}, got {source_record.revision}")

        link = f"[[id:{target_id}][{relation.value}: {target_record.title}]]"
        source_text = source_text.replace("* Related memories", f"* Related memories\n\n- {link}", 1)
        return self._rewrite(source_path, source_text, source_record.revision + 1)

    def archive_memory(
        self,
        memory_id: str,
        expected_revision: int,
        reason: str | None = None,
    ) -> MemoryRecord:
        """Archive a memory while keeping the Org file."""
        path = self._locate(memory_id)
        text = path.read_text(encoding="utf-8")
        record = parse_memory(text)
        if record.revision != expected_revision:
            raise RevisionConflict(f"expected {expected_revision}, got {record.revision}")
        text = re.sub(r":STATUS:\s+\w+", ":STATUS:          archived", text)
        return self._rewrite(path, text, record.revision + 1)

    def write_project_overview(
        self,
        project_id: str,
        overview_body: str,
        reviewed_revisions: list[dict[str, Any]],
        expected_revision: int | None = None,
    ) -> MemoryRecord:
        """Write `project.org` from caller-provided review synthesis."""
        project_dir = self._root / "projects" / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        path = project_dir / "project.org"

        revision = 1
        if path.exists():
            existing = parse_memory(path.read_text(encoding="utf-8"))
            if expected_revision is not None and existing.revision != expected_revision:
                raise RevisionConflict(f"expected {expected_revision}, got {existing.revision}")
            revision = existing.revision + 1

        memory_id = str(uuid.uuid4())
        reviewed_lines = "\n".join(
            f"- {r['memory_id']} REVISION={r['revision']}" for r in reviewed_revisions
        )
        org_text = "\n".join([
            ":PROPERTIES:",
            f":ID:       {memory_id}",
            f":PROJECT_ID:      {project_id}",
            ":MEMORY_TYPE:     overview",
            ":CREATED_BY:      agent",
            ":STATUS:          active",
            f":REVISION:        {revision}",
            ":END:",
            f"#+title: Project overview — {project_id}",
            "#+filetags: :agent-memory:overview:",
            "",
            overview_body,
            "* Reviewed revisions",
            "",
            reviewed_lines,
        ])
        path.write_text(org_text, encoding="utf-8")
        self._id_map[memory_id] = path
        return dc_replace(parse_memory(org_text), path=path, memory_id=memory_id)
