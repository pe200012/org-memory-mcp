"""Tests for FastMCP server construction and tool registration."""

from __future__ import annotations

from org_mem.config import Config
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
