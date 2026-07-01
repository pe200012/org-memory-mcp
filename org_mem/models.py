"""Shared domain models for org-mem.

This module contains vocabulary enums, value objects, and response envelopes.
It should contain no file-system, SQLite, embedding-provider, or MCP code.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryType(str, Enum):
    """Closed memory type vocabulary."""

    OVERVIEW = "overview"
    ARCHITECTURE = "architecture"
    DECISION = "decision"
    INVARIANT = "invariant"
    CONVENTION = "convention"
    PROBLEM = "problem"
    HANDOFF = "handoff"
    OUTCOME = "outcome"


class MemoryStatus(str, Enum):
    """Lifecycle state for one memory file."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class LinkRelation(str, Enum):
    """Closed typed-link relation vocabulary."""

    SUPPORTS = "supports"
    SUPERSEDES = "supersedes"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"
    DERIVED_FROM = "derived_from"
    FIXES = "fixes"
    MENTIONS = "mentions"


EVIDENCE_REQUIREMENTS_HINT = (
    "Each evidence item must be an object with exactly the string keys 'kind' and 'value'."
)


@dataclass(frozen=True, slots=True)
class Evidence:
    """Source evidence for an agent-written memory."""

    kind: str
    value: str

    def __post_init__(self) -> None:
        _require_evidence_string("kind", self.kind, "evidence item")
        _require_evidence_string("value", self.value, "evidence item")


_EVIDENCE_KEYS = {"kind", "value"}


def coerce_evidence(item: Evidence | dict[str, Any], index: int | None = None) -> Evidence:
    """Validate one JSON evidence object and return the internal value object."""
    label = f"evidence[{index}]" if index is not None else "evidence item"
    if isinstance(item, Evidence):
        _require_evidence_string("kind", item.kind, label)
        _require_evidence_string("value", item.value, label)
        return item
    if not isinstance(item, dict):
        raise ValueError(f"invalid_evidence: {label} must be an object with kind and value")

    missing = [key for key in ("kind", "value") if key not in item]
    if missing:
        raise ValueError(f"invalid_evidence: {label} missing required field: {missing[0]}")

    extra = sorted(set(item) - _EVIDENCE_KEYS)
    if extra:
        raise ValueError(f"invalid_evidence: {label} has unsupported field(s): {', '.join(extra)}")

    kind = item["kind"]
    value = item["value"]
    _require_evidence_string("kind", kind, label)
    _require_evidence_string("value", value, label)
    return Evidence(kind=kind, value=value)


def coerce_evidence_items(evidence: list[Evidence | dict[str, Any]]) -> list[Evidence]:
    """Validate all evidence objects and keep precise item indexes in errors."""
    return [coerce_evidence(item, index) for index, item in enumerate(evidence)]


def evidence_source_text(item: Evidence | dict[str, Any]) -> str:
    """Render one evidence object as a stable Org Sources entry."""
    evidence = coerce_evidence(item)
    return evidence.value


def _require_evidence_string(field: str, value: Any, label: str) -> None:
    if not isinstance(value, str):
        raise ValueError(f"invalid_evidence: {label} field '{field}' must be a string")


@dataclass(frozen=True, slots=True)
class MemoryLink:
    """Typed edge between two Org memory IDs."""

    source_id: str
    target_id: str
    relation: LinkRelation
    note: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryDraft:
    """Input model for creating a memory."""

    project_id: str
    memory_type: MemoryType
    title: str
    body: str
    evidence: list[Evidence]
    tags: list[str] = field(default_factory=list)
    created_by: str = "agent"
    status: MemoryStatus = MemoryStatus.ACTIVE
    revision: int = 1
    links: list[MemoryLink] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    """Parsed or persisted memory record."""

    memory_id: str
    project_id: str
    memory_type: MemoryType
    title: str
    body: str
    path: Path
    status: MemoryStatus = MemoryStatus.ACTIVE
    revision: int = 1
    tags: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    links: list[MemoryLink] = field(default_factory=list)
    created: str | None = None
    updated: str | None = None


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """Resolved project identity and root mapping."""

    project_id: str
    root_path: Path
    name_hint: str | None
    project_dir: Path


@dataclass(frozen=True, slots=True)
class ReviewedRevision:
    """Memory ID and revision consumed by a project overview review."""

    memory_id: str
    revision: int


@dataclass(frozen=True, slots=True)
class ErrorDetail:
    """Structured error payload returned inside tool envelopes."""

    code: str
    message: str
    field: str | None = None
    hint: str | None = None


@dataclass(frozen=True, slots=True)
class ToolResponse:
    """Uniform tool response envelope."""

    ok_value: bool
    payload: dict[str, Any] = field(default_factory=dict)
    error_detail: ErrorDetail | None = None

    @classmethod
    def ok(cls, **payload: Any) -> "ToolResponse":
        """Create a successful response envelope."""
        return cls(ok_value=True, payload=payload)

    @classmethod
    def error(cls, error: ErrorDetail) -> "ToolResponse":
        """Create a failed response envelope with repair details."""
        return cls(ok_value=False, error_detail=error)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the envelope to a JSON-compatible dictionary."""
        if self.ok_value:
            return {"ok": True, **self.payload}
        detail = self.error_detail
        return {
            "ok": False,
            "error": {
                "code": detail.code,
                "message": detail.message,
                "field": detail.field,
                "hint": detail.hint,
            },
        }


@dataclass(frozen=True, slots=True)
class SearchQuery:
    """Search request after metadata filters are applied."""

    project_id: str
    query: str
    memory_type: str | None = None
    status: str = "active"
    tags: list[str] = field(default_factory=list)
    include_body: bool = False
    include_links: bool = False
    limit: int = 20


@dataclass(frozen=True, slots=True)
class SearchResult:
    """Ranked compact search result."""

    memory_id: str
    project_id: str
    title: str
    memory_type: MemoryType
    status: MemoryStatus
    revision: int
    score: float
    matched_fields: list[str]
    snippet: str
    path: str


@dataclass(frozen=True, slots=True)
class ListPage:
    """Cursor-paginated deterministic list result."""

    items: list[MemoryRecord]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class IndexRebuildResult:
    """Result of rebuilding one project's derived index."""

    project_id: str
    index_generation: int


@dataclass(frozen=True, slots=True)
class RankedMemoryId:
    """Memory ID with fused retrieval score."""

    memory_id: str
    score: float
