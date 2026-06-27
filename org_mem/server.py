"""FastMCP server construction for org-mem.

This module owns MCP tool registration and stdio runtime wiring. Business
logic stays in `org_mem.service.MemoryService`.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from org_mem.config import Config, load_config


def create_server(config: Config | None = None) -> FastMCP:
    """Create a FastMCP server with all v1 memory tools registered."""
    # TODO: Instantiate FastMCP("org-mem"), create MemoryService(config), and
    # register memory_project/write/read/list/search/update/link/archive/review.
    raise NotImplementedError("TODO: implement FastMCP tool registration")


def registered_tool_names(server: FastMCP) -> list[str]:
    """Return registered tool names for thin MCP wiring tests."""
    # TODO: Inspect FastMCP's registered tool manager and return stable names
    # without exposing SDK internals to tests.
    raise NotImplementedError("TODO: implement FastMCP tool introspection helper")


def run_stdio_server(config: Config | None = None) -> None:
    """Run the org-mem server over stdio."""
    # TODO: Build the server with create_server(config or load_config()) and
    # run it in stdio mode while keeping stdout reserved for JSON-RPC.
    raise NotImplementedError("TODO: implement stdio MCP runtime")


def build_server_from_environment() -> FastMCP:
    """Build a server using config file and environment overrides."""
    # TODO: Call load_config(), then create_server(config), for MCP client
    # command entries such as `uv run org-mem`.
    raise NotImplementedError("TODO: implement environment-backed server construction")


def call_tool_for_test(server: FastMCP, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a registered tool synchronously in tests."""
    # TODO: Provide a narrow test helper over FastMCP internals or update tests
    # to use the SDK's supported in-process tool-call API.
    raise NotImplementedError("TODO: implement test-only tool call helper")
