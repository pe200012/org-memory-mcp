"""Tests for Org memory parsing, serialization, and validation."""

from __future__ import annotations

import pytest

from org_mem.models import Evidence, MemoryDraft, MemoryType
from org_mem.org_file import (
    parse_memory,
    required_sections_for_type,
    serialize_memory,
    validate_memory_draft,
)


def test_serialize_memory_writes_properties_title_tags_and_body(valid_body, evidence) -> None:
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Preserve heap location during dereference use",
        body=valid_body,
        evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
        tags=["effspec", "semantics"],
        created_by="agent",
    )

    org_text = serialize_memory(draft)

    assert ":PROJECT_ID:      effspec-a91c3f" in org_text
    assert ":MEMORY_TYPE:     decision" in org_text
    assert "#+title: Preserve heap location during dereference use" in org_text
    assert "#+filetags: :agent-memory:effspec:semantics:decision:" in org_text
    assert "* Content" in org_text
    assert "* Sources" in org_text
    assert "* Related memories" in org_text


def test_parse_memory_round_trips_serialized_memory(valid_body, evidence) -> None:
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Preserve heap location during dereference use",
        body=valid_body,
        evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
        tags=["effspec", "semantics"],
        created_by="agent",
    )

    parsed = parse_memory(serialize_memory(draft))

    assert parsed.project_id == draft.project_id
    assert parsed.memory_type == draft.memory_type
    assert parsed.title == draft.title
    assert parsed.revision == 1
    assert parsed.status.value == "active"


def test_validate_rejects_missing_required_section(valid_body, evidence) -> None:
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Missing sources",
        body=valid_body.replace("* Sources\n", ""),
        evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
        created_by="agent",
    )

    with pytest.raises(ValueError, match="missing_required_section"):
        validate_memory_draft(draft)


def test_validate_rejects_missing_agent_evidence(valid_body) -> None:
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Missing evidence",
        body=valid_body,
        evidence=[],
        created_by="agent",
    )

    with pytest.raises(ValueError, match="missing_required_evidence"):
        validate_memory_draft(draft)


def test_validate_allows_user_memory_without_evidence(valid_body) -> None:
    draft = MemoryDraft(
        project_id="global",
        memory_type=MemoryType.CONVENTION,
        title="User preference",
        body=valid_body,
        evidence=[],
        created_by="user",
    )

    validate_memory_draft(draft)


def test_decision_type_has_conventional_sections() -> None:
    assert required_sections_for_type(MemoryType.DECISION) == [
        "Content",
        "Sources",
        "Related memories",
        "Context",
        "Decision",
        "Rationale",
        "Consequences",
    ]
