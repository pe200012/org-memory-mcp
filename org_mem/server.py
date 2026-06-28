"""FastMCP server construction for org-mem.

This module owns MCP tool registration and stdio runtime wiring. Business
logic stays in `org_mem.service.MemoryService`.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from org_mem.config import Config, load_config
from org_mem.models import Evidence, LinkRelation, MemoryDraft, MemoryType
from org_mem.service import MemoryService


class _OrgMemServer(FastMCP):
    """FastMCP subclass that adds a synchronous tool-call helper for tests."""

    def call_tool_sync(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        contents = asyncio.run(self.call_tool(name, arguments))
        return json.loads(contents[0].text)


def create_server(config: Config | None = None) -> FastMCP:
    """Create a FastMCP server with all v1 memory tools registered."""
    if config is None:
        config = load_config()

    server = _OrgMemServer("org-mem")
    svc = MemoryService(config)

    @server.tool()
    def memory_project(root_path: str, name_hint: str | None = None) -> dict:
        return svc.memory_project(root_path, name_hint)

    @server.tool()
    def memory_write(
        project_id: str,
        memory_type: str,
        title: str,
        body: str,
        evidence: list[dict],
        tags: list[str] | None = None,
        created_by: str = "agent",
    ) -> dict:
        draft = MemoryDraft(
            project_id=project_id,
            memory_type=MemoryType(memory_type),
            title=title,
            body=body,
            evidence=[Evidence(**e) for e in evidence],
            tags=tags or [],
            created_by=created_by,
        )
        return svc.memory_write(draft)

    @server.tool()
    def memory_read(memory_id: str, include_links: bool = True) -> dict:
        return svc.memory_read(memory_id, include_links)

    @server.tool()
    def memory_list(
        project_id: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        sort: str = "updated_desc",
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict:
        return svc.memory_list(project_id, memory_type, status, tags, sort, limit, cursor)

    @server.tool()
    def memory_search(
        project_id: str,
        query: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        include_body: bool = False,
        include_links: bool = False,
        limit: int = 20,
    ) -> dict:
        return svc.memory_search(project_id, query, memory_type, status, tags, include_body, include_links, limit)

    @server.tool()
    def memory_update(
        memory_id: str,
        expected_revision: int,
        title: str | None = None,
        body: str | None = None,
        evidence: list[dict] | None = None,
        tags: list[str] | None = None,
    ) -> dict:
        return svc.memory_update(memory_id, expected_revision, title, body, evidence, tags)

    @server.tool()
    def memory_link(
        source_id: str,
        target_id: str,
        relation: str,
        note: str | None = None,
        expected_revision: int | None = None,
    ) -> dict:
        return svc.memory_link(source_id, target_id, LinkRelation(relation), note, expected_revision)

    @server.tool()
    def memory_archive(
        memory_id: str,
        expected_revision: int,
        reason: str | None = None,
    ) -> dict:
        return svc.memory_archive(memory_id, expected_revision, reason)

    @server.tool()
    def memory_review(
        project_id: str,
        overview_body: str,
        reviewed_revisions: list[dict],
        expected_revision: int | None = None,
    ) -> dict:
        return svc.memory_review(project_id, overview_body, reviewed_revisions, expected_revision)

    return server


def registered_tool_names(server: FastMCP) -> list[str]:
    """Return registered tool names for thin MCP wiring tests."""
    return list(server._tool_manager._tools.keys())


def run_stdio_server(config: Config | None = None) -> None:
    """Run the org-mem server over stdio."""
    create_server(config or load_config()).run(transport="stdio")


def build_server_from_environment() -> FastMCP:
    """Build a server using config file and environment overrides."""
    return create_server(load_config())


def call_tool_for_test(server: FastMCP, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a registered tool synchronously in tests."""
    return server.call_tool_sync(tool_name, arguments)  # type: ignore[attr-defined]
