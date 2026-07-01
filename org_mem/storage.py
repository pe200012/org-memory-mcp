"""Canonical Org file storage operations.

This module owns safe writes, reads, updates, archives, typed links, project
overview writes, revision checks, and path containment under the memory root.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from dataclasses import replace as dc_replace
from pathlib import Path
from typing import Any

from org_mem.config import Config
from org_mem.locking import FileLock, atomic_write_text, state_lock_path
from org_mem.models import LinkRelation, MemoryDraft, MemoryRecord, MemoryType, coerce_evidence_items
from org_mem.org_file import parse_memory, serialize_memory, validate_memory_draft


class RevisionConflict(RuntimeError):
    """Raised when `expected_revision` differs from the stored revision."""


def _type_dir(memory_type: MemoryType) -> str:
    return {
        MemoryType.OVERVIEW: "overview",
        MemoryType.ARCHITECTURE: "architecture",
        MemoryType.DECISION: "decisions",
        MemoryType.INVARIANT: "invariants",
        MemoryType.CONVENTION: "conventions",
        MemoryType.PROBLEM: "problems",
        MemoryType.HANDOFF: "handoffs",
        MemoryType.OUTCOME: "outcomes",
    }[memory_type]


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]


class MemoryStorage:
    """File-backed storage for canonical Org memory records."""

    def __init__(self, config: Config) -> None:
        self._root = config.memory_root
        self._lock_path = state_lock_path(config)
        # Rebuilt lazily by an rglob scan when a memory ID is first requested.
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
        with FileLock(self._lock_path):
            validate_memory_draft(draft)
            memory_id = str(uuid.uuid4())
            type_dir = self._root / "projects" / draft.project_id / _type_dir(draft.memory_type)
            type_dir.mkdir(parents=True, exist_ok=True)
            short_id = memory_id.replace("-", "")[:8]
            path = type_dir / f"{date.today().isoformat()}-{_slug(draft.title)}-{short_id}.org"
            org_text = serialize_memory(draft).replace(":ID:       ", f":ID:       {memory_id}", 1)
            atomic_write_text(path, org_text)
            self._id_map[memory_id] = path
            return dc_replace(parse_memory(org_text), path=path, memory_id=memory_id)

    def read_memory(self, memory_id: str) -> MemoryRecord:
        """Read one memory by Org ID."""
        with FileLock(self._lock_path):
            path = self._locate(memory_id)
            return dc_replace(parse_memory(path.read_text(encoding="utf-8")), path=path)

    def _rewrite(self, path: Path, text: str, new_revision: int) -> MemoryRecord:
        text = re.sub(r":REVISION:\s+\d+", f":REVISION:        {new_revision}", text)
        text = re.sub(r":UPDATED:\s+.*", f":UPDATED:         {_updated_timestamp()}", text)
        atomic_write_text(path, text)
        return dc_replace(parse_memory(text), path=path)

    def update_memory(
        self,
        memory_id: str,
        expected_revision: int,
        title: str | None = None,
        body: str | None = None,
        evidence: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> MemoryRecord:
        """Update an existing memory with optimistic concurrency."""
        with FileLock(self._lock_path):
            path = self._locate(memory_id)
            text = path.read_text(encoding="utf-8")
            record = parse_memory(text)
            if record.revision != expected_revision:
                raise RevisionConflict(f"expected {expected_revision}, got {record.revision}")
            if title is not None:
                text = re.sub(r"#\+title:.*", f"#+title: {title}", text)
            if body is not None:
                text = _replace_body(text, body)
            if tags is not None:
                tags_part = ":" + ":".join(["agent-memory", *tags, record.memory_type.value]) + ":"
                text = re.sub(r"#\+filetags:.*", f"#+filetags: {tags_part}", text)
            if evidence is not None:
                items = coerce_evidence_items(evidence)
                text = _replace_section(
                    text, "Sources", "\n".join(f"- {e.kind} :: {e.value}" for e in items)
                )
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
        with FileLock(self._lock_path):
            target_path = self._locate(target_id)
            target_text = target_path.read_text(encoding="utf-8")
            target_record = parse_memory(target_text)

            source_path = self._locate(source_id)
            source_text = source_path.read_text(encoding="utf-8")
            source_record = parse_memory(source_text)
            if expected_revision is not None and source_record.revision != expected_revision:
                raise RevisionConflict(f"expected {expected_revision}, got {source_record.revision}")

            link = f"[[id:{target_id}][{relation.value}: {target_record.title}]]"
            line = f"- {link} :: {note}" if note else f"- {link}"
            source_text = source_text.replace("* Related memories", f"* Related memories\n\n{line}", 1)

            # A supersedes edge makes the target no longer current: flip its
            # status so default search/list hide it. history is still readable.
            if relation is LinkRelation.SUPERSEDES and target_record.status.value == "active":
                superseded = re.sub(r":STATUS:\s+\w+", ":STATUS:          superseded", target_text)
                self._rewrite(target_path, superseded, target_record.revision + 1)

            return self._rewrite(source_path, source_text, source_record.revision + 1)

    def unlink_memory(
        self,
        source_id: str,
        target_id: str,
        relation: LinkRelation,
        expected_revision: int | None = None,
    ) -> MemoryRecord:
        """Remove a typed link from source to target. Does not reactivate targets."""
        with FileLock(self._lock_path):
            source_path = self._locate(source_id)
            source_text = source_path.read_text(encoding="utf-8")
            source_record = parse_memory(source_text)
            if expected_revision is not None and source_record.revision != expected_revision:
                raise RevisionConflict(f"expected {expected_revision}, got {source_record.revision}")

            marker = f"[[id:{target_id}][{relation.value}:"
            lines = source_text.splitlines()
            kept = [ln for ln in lines if marker not in ln]
            if len(kept) == len(lines):
                raise FileNotFoundError(
                    f"link {relation.value} -> {target_id} not found on {source_id}"
                )
            return self._rewrite(source_path, "\n".join(kept), source_record.revision + 1)

    def archive_memory(
        self,
        memory_id: str,
        expected_revision: int,
        reason: str | None = None,
    ) -> MemoryRecord:
        """Archive a memory while keeping the Org file."""
        with FileLock(self._lock_path):
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
        with FileLock(self._lock_path):
            project_dir = self._root / "projects" / project_id
            project_dir.mkdir(parents=True, exist_ok=True)
            path = project_dir / "project.org"

            revision = 1
            existing: MemoryRecord | None = None
            if path.exists():
                existing = parse_memory(path.read_text(encoding="utf-8"))
                if expected_revision is not None and existing.revision != expected_revision:
                    raise RevisionConflict(f"expected {expected_revision}, got {existing.revision}")
                revision = existing.revision + 1

            memory_id = existing.memory_id if existing is not None else str(uuid.uuid4())
            created = existing.created if existing is not None else _updated_timestamp()
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
                f":CREATED:         {created}",
                f":UPDATED:         {_updated_timestamp()}",
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
            atomic_write_text(path, org_text)
            self._id_map[memory_id] = path
            return dc_replace(parse_memory(org_text), path=path, memory_id=memory_id)


def _updated_timestamp() -> str:
    from datetime import datetime

    return datetime.now().astimezone().strftime("[%Y-%m-%d %a %H:%M]")


def _replace_body(org_text: str, body: str) -> str:
    lines = org_text.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("* "):
            return "\n".join(lines[:idx] + [body.rstrip()]) + "\n"
    return org_text.rstrip() + "\n\n" + body.rstrip() + "\n"


def _replace_section(org_text: str, section: str, content: str) -> str:
    body_start = org_text.find(f"* {section}")
    if body_start == -1:
        return org_text.rstrip() + f"\n\n* {section}\n\n{content.rstrip()}\n"
    lines = org_text.splitlines()
    start = None
    for idx, line in enumerate(lines):
        if line == f"* {section}":
            start = idx
            break
    if start is None:
        return org_text
    end = len(lines)
    for idx in range(start + 1, len(lines)):
        if lines[idx].startswith("* "):
            end = idx
            break
    replacement = [f"* {section}", "", content.rstrip()]
    return "\n".join(lines[:start] + replacement + lines[end:]) + "\n"
