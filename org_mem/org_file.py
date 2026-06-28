"""Org memory parsing, serialization, and validation."""

from __future__ import annotations

from pathlib import Path

import orgparse

from org_mem.models import MemoryDraft, MemoryRecord, MemoryStatus, MemoryType

_BASE_SECTIONS = ["Content", "Sources", "Related memories"]

_TYPE_EXTRA_SECTIONS: dict[MemoryType, list[str]] = {
    MemoryType.DECISION: ["Context", "Decision", "Rationale", "Consequences"],
    MemoryType.PROBLEM: ["Context", "Symptoms", "Root cause", "Resolution"],
    MemoryType.HANDOFF: ["Context", "Current state", "Next steps", "Contacts"],
    MemoryType.OUTCOME: ["Context", "Goals", "Result", "Lessons learned"],
}


def required_sections_for_type(memory_type: MemoryType) -> list[str]:
    return _BASE_SECTIONS + _TYPE_EXTRA_SECTIONS.get(memory_type, [])


def serialize_memory(draft: MemoryDraft) -> str:
    tag_str = ":agent-memory:" + ":".join(draft.tags) + ":" + draft.memory_type.value + ":"
    parts = [
        ":PROPERTIES:",
        ":ID:       ",
        f":PROJECT_ID:      {draft.project_id}",
        f":MEMORY_TYPE:     {draft.memory_type.value}",
        f":CREATED_BY:      {draft.created_by}",
        f":STATUS:          {draft.status.value}",
        f":REVISION:        {draft.revision}",
        ":END:",
        f"#+title: {draft.title}",
        f"#+filetags: {tag_str}",
        "",
        draft.body,
    ]
    return "\n".join(parts)


def parse_memory(org_text: str) -> MemoryRecord:
    doc = orgparse.loads(org_text)
    props = doc.properties
    body = "".join(f"* {c.heading}\n{c.body}" for c in doc.children)
    return MemoryRecord(
        memory_id=props.get("ID", ""),
        project_id=props.get("PROJECT_ID", ""),
        memory_type=MemoryType(props.get("MEMORY_TYPE", "overview")),
        title=doc.get_file_property("title") or "",
        body=body,
        path=Path("."),
        status=MemoryStatus(props.get("STATUS", "active")),
        revision=int(props.get("REVISION", "1")),
    )


def validate_memory_draft(draft: MemoryDraft) -> None:
    for section in _BASE_SECTIONS:
        if f"* {section}" not in draft.body:
            raise ValueError(f"missing_required_section: {section}")

    if draft.created_by == "agent" and not draft.evidence:
        raise ValueError("missing_required_evidence")
