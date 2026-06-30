"""Tests for FastMCP server construction and tool registration."""

from __future__ import annotations

import asyncio

from org_mem.config import Config
from org_mem.hints import SCHEMA_TEXT, SCHEMA_URI
from org_mem.server import create_server, registered_tool_names


def test_create_server_registers_v1_tools(memory_root, data_dir, config_path) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    assert server.name == "org-mem"
    assert set(registered_tool_names(server)) == {
        "memory_project",
        "memory_write",
        "memory_read",
        "memory_list",
        "memory_search",
        "memory_global_search",
        "memory_update",
        "memory_link",
        "memory_archive",
        "memory_review",
    }


def test_server_tool_response_uses_ok_envelope(memory_root, data_dir, config_path, valid_body) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = server.call_tool_sync(
        "memory_write",
        {
            "project_id": "effspec-a91c3f",
            "memory_type": "decision",
            "title": "Missing evidence",
            "body": valid_body,
            "evidence": [],
            "created_by": "agent",
        },
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "missing_required_evidence"


def test_server_project_activation_returns_schema_guidance(memory_root, data_dir, config_path, tmp_path) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    response = server.call_tool_sync(
        "memory_project",
        {
            "root_path": str(repo_root),
            "name_hint": "demo",
        },
    )

    assert response["ok"] is True
    assert response["schema_uri"] == SCHEMA_URI
    assert response["schema_text"] == SCHEMA_TEXT
    assert "Memory types:" in response["schema_text"]
    assert "Required Org sections:" in response["schema_text"]
    assert "Agent-written non-overview memories require evidence" in response["schema_text"]


def test_server_invalid_memory_type_uses_ok_error_envelope(memory_root, data_dir, config_path, valid_body) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = server.call_tool_sync(
        "memory_write",
        {
            "project_id": "effspec-a91c3f",
            "memory_type": "bogus",
            "title": "Bad type",
            "body": valid_body,
            "evidence": [],
            "created_by": "agent",
        },
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_memory_type"


def test_server_invalid_link_relation_uses_ok_error_envelope(memory_root, data_dir, config_path) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = server.call_tool_sync(
        "memory_link",
        {
            "source_id": "source",
            "target_id": "target",
            "relation": "bogus",
        },
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_link_relation"


def test_create_server_registers_resource_hints(memory_root, data_dir, config_path) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    resources = asyncio.run(server.list_resources())
    uris = {str(resource.uri) for resource in resources}

    assert {
        "org-mem://guide",
        "org-mem://schema",
        "org-mem://workflow",
    }.issubset(uris)


def test_resource_hints_describe_memory_tool_usage(memory_root, data_dir, config_path) -> None:
    server = create_server(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    guide = asyncio.run(server.read_resource("org-mem://guide"))[0].content
    schema = asyncio.run(server.read_resource("org-mem://schema"))[0].content
    workflow = asyncio.run(server.read_resource("org-mem://workflow"))[0].content

    assert "memory_project(root_path" in guide
    assert "memory_search" in guide
    assert "memory_global_search" in guide
    assert "memory_write" in guide
    assert "expected_revision" in schema
    assert "Content" in schema
    assert "Sources" in schema
    assert "memory_review" in workflow
    assert "reviewed_revisions" in workflow
