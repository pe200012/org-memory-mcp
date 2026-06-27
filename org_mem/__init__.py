"""Org-backed MCP memory server package.

The package exposes a layered implementation surface for the design in
`docs/design-logs/001-org-memory-mcp.md`: config, models, Org file parsing,
registry, storage, indexing, embeddings, service orchestration, and FastMCP
server registration.
"""

from org_mem.config import Config, load_config
from org_mem.service import MemoryService

__all__ = ["Config", "MemoryService", "load_config"]
