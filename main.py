"""Console entrypoint for the org-mem MCP server.

The implementation design lives in `docs/design-logs/001-org-memory-mcp.md`.
This file should stay as a tiny runtime bridge into `org_mem.server`.
"""

from org_mem.server import run_stdio_server


def main():
    """Run the stdio MCP server."""
    # TODO: Delegate to run_stdio_server() after server construction and stdio
    # transport are implemented.
    raise NotImplementedError("TODO: implement org-mem entrypoint")


if __name__ == "__main__":
    main()
