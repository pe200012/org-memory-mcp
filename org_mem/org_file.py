"""Org memory parsing, serialization, and validation."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from org_mem.models import Evidence, MemoryDraft, MemoryLink, MemoryRecord, MemoryStatus, MemoryType, LinkRelation

_BASE_SECTIONS = ["Content", "Sources", "Related memories"]

_TYPE_EXTRA_SECTIONS: dict[MemoryType, list[str]] = {
    MemoryType.DECISION: ["Context", "Decision", "Rationale", "Consequences"],
    MemoryType.PROBLEM: ["Symptoms", "Diagnosis", "Fix", "Prevention"],
    MemoryType.HANDOFF: ["Current state", "Verification", "Next steps"],
    MemoryType.OUTCOME: ["Change", "Evidence", "Follow-up"],
}


def required_sections_for_type(memory_type: MemoryType) -> list[str]:
    return _BASE_SECTIONS + _TYPE_EXTRA_SECTIONS.get(memory_type, [])


def serialize_memory(draft: MemoryDraft) -> str:
    now = _org_timestamp()
    tag_str = _filetags(draft.tags, draft.memory_type)
    parts = [
        ":PROPERTIES:",
        ":ID:       ",
        f":PROJECT_ID:      {draft.project_id}",
        f":MEMORY_TYPE:     {draft.memory_type.value}",
        f":CREATED_BY:      {draft.created_by}",
        f":STATUS:          {draft.status.value}",
        f":CREATED:         {now}",
        f":UPDATED:         {now}",
        f":REVISION:        {draft.revision}",
        ":END:",
        f"#+title: {draft.title}",
        f"#+filetags: {tag_str}",
        "",
        draft.body,
    ]
    return "\n".join(parts)


def serialize_record(record: MemoryRecord, created: str | None = None, updated: str | None = None) -> str:
    """Serialize an existing record while preserving its stable ID."""
    created_value = created or record.created or _org_timestamp()
    updated_value = updated or _org_timestamp()
    tag_str = _filetags(record.tags, record.memory_type)
    return "\n".join(
        [
            ":PROPERTIES:",
            f":ID:       {record.memory_id}",
            f":PROJECT_ID:      {record.project_id}",
            f":MEMORY_TYPE:     {record.memory_type.value}",
            ":CREATED_BY:      agent",
            f":STATUS:          {record.status.value}",
            f":CREATED:         {created_value}",
            f":UPDATED:         {updated_value}",
            f":REVISION:        {record.revision}",
            ":END:",
            f"#+title: {record.title}",
            f"#+filetags: {tag_str}",
            "",
            record.body.rstrip(),
            "",
        ]
    )


def parse_memory(org_text: str) -> MemoryRecord:
    props = _parse_properties(org_text)
    title = _parse_keyword(org_text, "title")
    tags = _parse_filetags(_parse_keyword(org_text, "filetags") or "", props.get("MEMORY_TYPE", "overview"))
    body = _parse_body(org_text)
    memory_id = props.get("ID", "").strip()
    evidence = _parse_sources(body)
    links = _parse_links(body, memory_id)
    return MemoryRecord(
        memory_id=memory_id,
        project_id=props.get("PROJECT_ID", "").strip(),
        memory_type=MemoryType(props.get("MEMORY_TYPE", "overview")),
        title=title or "",
        body=body,
        path=Path("."),
        status=MemoryStatus(props.get("STATUS", "active")),
        revision=int(props.get("REVISION", "1")),
        tags=tags,
        evidence=evidence,
        links=links,
        created=props.get("CREATED"),
        updated=props.get("UPDATED"),
    )


def validate_memory_draft(draft: MemoryDraft) -> None:
    for section in _BASE_SECTIONS:
        if f"* {section}" not in draft.body:
            raise ValueError(f"missing_required_section: {section}")

    if draft.created_by == "agent" and not draft.evidence:
        raise ValueError("missing_required_evidence")


def _org_timestamp() -> str:
    return datetime.now().astimezone().strftime("[%Y-%m-%d %a %H:%M]")


def _filetags(tags: list[str], memory_type: MemoryType) -> str:
    values = ["agent-memory"]
    for tag in tags:
        if tag not in values:
            values.append(tag)
    if memory_type.value not in values:
        values.append(memory_type.value)
    return ":" + ":".join(values) + ":"


def _parse_properties(org_text: str) -> dict[str, str]:
    match = re.search(r"^:PROPERTIES:\n(?P<body>.*?)^:END:\s*$", org_text, re.MULTILINE | re.DOTALL)
    if not match:
        return {}
    props: dict[str, str] = {}
    for line in match.group("body").splitlines():
        prop_match = re.match(r"^:([^:]+):\s*(.*)$", line)
        if prop_match:
            props[prop_match.group(1).strip()] = prop_match.group(2).strip()
    return props


def _parse_keyword(org_text: str, keyword: str) -> str | None:
    match = re.search(rf"^#\+{re.escape(keyword)}:\s*(.*)$", org_text, re.IGNORECASE | re.MULTILINE)
    return match.group(1).strip() if match else None


def _parse_filetags(filetags: str, memory_type: str) -> list[str]:
    values = [tag for tag in filetags.strip().split(":") if tag]
    return [tag for tag in values if tag != "agent-memory"]


def _parse_body(org_text: str) -> str:
    lines = org_text.splitlines()
    idx = 0
    in_properties = False
    for idx, line in enumerate(lines):
        if line == ":PROPERTIES:":
            in_properties = True
            continue
        if in_properties and line == ":END:":
            in_properties = False
            continue
        if in_properties:
            continue
        if line.lower().startswith("#+"):
            continue
        if line.startswith("* "):
            return "\n".join(lines[idx:]).rstrip() + "\n"
    return ""


def _section_lines(body: str, section: str) -> list[str]:
    pattern = rf"^\* {re.escape(section)}\s*$"
    lines = body.splitlines()
    start: int | None = None
    for idx, line in enumerate(lines):
        if re.match(pattern, line):
            start = idx + 1
            break
    if start is None:
        return []
    end = len(lines)
    for idx in range(start, len(lines)):
        if lines[idx].startswith("* "):
            end = idx
            break
    return lines[start:end]


def _parse_sources(body: str) -> list[Evidence]:
    evidence: list[Evidence] = []
    for line in _section_lines(body, "Sources"):
        stripped = line.strip()
        if stripped.startswith("- "):
            evidence.append(Evidence(kind="source", value=stripped[2:].strip()))
    return evidence


def _parse_links(body: str, source_id: str) -> list[MemoryLink]:
    links: list[MemoryLink] = []
    for line in _section_lines(body, "Related memories"):
        match = re.search(r"\[\[id:([^\]]+)\]\[([^:\]]+):", line)
        if match:
            try:
                links.append(
                    MemoryLink(
                        source_id=source_id,
                        target_id=match.group(1),
                        relation=LinkRelation(match.group(2)),
                    )
                )
            except ValueError:
                continue
    return links
