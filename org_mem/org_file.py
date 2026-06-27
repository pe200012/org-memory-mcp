"""Org memory parsing, serialization, and validation.

This module converts between in-memory models and canonical Org text. It owns
property drawer handling, section checks, evidence rules, and Org link parsing.
"""

from __future__ import annotations

from org_mem.models import MemoryDraft, MemoryRecord, MemoryType


def serialize_memory(draft: MemoryDraft) -> str:
    """Serialize a memory draft into canonical Org text."""
    # TODO: Generate an Org property drawer, title, filetags, required sections,
    # evidence metadata, and typed id links while preserving user body content.
    raise NotImplementedError("TODO: implement Org memory serialization")


def parse_memory(org_text: str) -> MemoryRecord:
    """Parse canonical Org text into a memory record."""
    # TODO: Parse property drawer fields, #+title, #+filetags, body sections,
    # evidence entries, and Org id links into MemoryRecord.
    raise NotImplementedError("TODO: implement Org memory parsing")


def validate_memory_draft(draft: MemoryDraft) -> None:
    """Validate a memory draft against schema and evidence rules."""
    # TODO: Check required metadata, closed vocabularies, required sections,
    # evidence requirements, duplicate links, and path-safe fields.
    raise NotImplementedError("TODO: implement memory draft validation")


def required_sections_for_type(memory_type: MemoryType) -> list[str]:
    """Return baseline and conventional section names for a memory type."""
    # TODO: Return Content/Sources/Related memories for all types and append
    # type-specific conventional sections for decision/problem/handoff/outcome.
    raise NotImplementedError("TODO: implement required section lookup")
