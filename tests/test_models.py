"""Tests for model types, envelopes, and vocabulary constraints."""

from __future__ import annotations

from org_mem.models import (
    ErrorDetail,
    Evidence,
    LinkRelation,
    MemoryDraft,
    MemoryStatus,
    MemoryType,
    ReviewedRevision,
    ToolResponse,
)


def test_memory_type_vocabulary_matches_design_log() -> None:
    assert {item.value for item in MemoryType} == {
        "overview",
        "architecture",
        "decision",
        "invariant",
        "convention",
        "problem",
        "handoff",
        "outcome",
    }


def test_link_relation_vocabulary_matches_design_log() -> None:
    assert {item.value for item in LinkRelation} == {
        "supports",
        "supersedes",
        "contradicts",
        "depends_on",
        "related_to",
        "derived_from",
        "fixes",
        "mentions",
    }


def test_memory_draft_captures_write_input(valid_body, evidence) -> None:
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Preserve heap location during dereference use",
        body=valid_body,
        evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
        tags=["effspec", "semantics"],
        created_by="agent",
    )

    assert draft.project_id == "effspec-a91c3f"
    assert draft.memory_type is MemoryType.DECISION
    assert draft.status is MemoryStatus.ACTIVE
    assert draft.revision == 1


def test_tool_response_success_shape_is_machine_readable() -> None:
    response = ToolResponse.ok(
        memory_id="0197a8d4-52dc-71ec-a1cb-0f93eb217b38",
        project_id="effspec-a91c3f",
        revision=4,
        path="projects/effspec-a91c3f/decisions/example.org",
        indexed=False,
        index_generation=12,
    )

    assert response.to_dict() == {
        "ok": True,
        "memory_id": "0197a8d4-52dc-71ec-a1cb-0f93eb217b38",
        "project_id": "effspec-a91c3f",
        "revision": 4,
        "path": "projects/effspec-a91c3f/decisions/example.org",
        "indexed": False,
        "index_generation": 12,
    }


def test_tool_response_error_shape_is_repairable() -> None:
    response = ToolResponse.error(
        ErrorDetail(
            code="missing_required_section",
            message="Memory body is missing a required Org section.",
            field="body.sections",
            hint="Add a top-level '* Sources' section.",
        )
    )

    assert response.to_dict() == {
        "ok": False,
        "error": {
            "code": "missing_required_section",
            "message": "Memory body is missing a required Org section.",
            "field": "body.sections",
            "hint": "Add a top-level '* Sources' section.",
        },
    }


def test_reviewed_revision_records_memory_version() -> None:
    reviewed = ReviewedRevision(
        memory_id="0197a8d4-52dc-71ec-a1cb-0f93eb217b38",
        revision=3,
    )

    assert reviewed.memory_id == "0197a8d4-52dc-71ec-a1cb-0f93eb217b38"
    assert reviewed.revision == 3
