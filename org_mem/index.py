"""SQLite metadata, FTS, and async index freshness.

This module owns all derived cache state. Org files remain canonical, so every
index row must be rebuildable from storage.
"""

from __future__ import annotations

from org_mem.config import Config
from org_mem.models import IndexRebuildResult, ListPage, SearchQuery, SearchResult


class MemoryIndex:
    """Rebuildable SQLite metadata and FTS index."""

    def __init__(self, config: Config) -> None:
        """Create an index service bound to one config."""
        # TODO: Store config, open or lazily create index.sqlite3, initialize
        # generation tracking, and prepare one dirty-project queue.
        raise NotImplementedError("TODO: implement index service initialization")

    def rebuild_project(self, project_id: str) -> IndexRebuildResult:
        """Rebuild derived index rows for one project from Org files."""
        # TODO: Scan canonical Org files, parse metadata, replace project rows,
        # rebuild FTS content, and increment the project's index generation.
        raise NotImplementedError("TODO: implement project index rebuild")

    def enqueue_rebuild(self, project_id: str) -> None:
        """Mark one project dirty for background rebuild."""
        # TODO: Add project_id to a coalescing in-process queue consumed by the
        # background index worker.
        raise NotImplementedError("TODO: implement dirty-project enqueue")

    def pending_projects(self) -> list[str]:
        """Return dirty project IDs in deterministic order."""
        # TODO: Return queued project IDs for tests and operational inspection.
        raise NotImplementedError("TODO: implement pending project inspection")

    def wait_until_index_fresh(self, project_id: str) -> None:
        """Block until a project's queued rebuild finishes."""
        # TODO: Drain/rebuild the project if it is queued, then mark generation
        # fresh for subsequent search calls.
        raise NotImplementedError("TODO: implement search freshness wait")

    def is_fresh(self, project_id: str) -> bool:
        """Return whether a project has no pending rebuild work."""
        # TODO: Check dirty queue and in-flight rebuild state.
        raise NotImplementedError("TODO: implement freshness check")

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search indexed memories using metadata filters and FTS."""
        # TODO: Wait for freshness, apply metadata filters, run SQLite FTS,
        # return compact ranked results with snippets and matched fields.
        raise NotImplementedError("TODO: implement FTS search")

    def list_memories(
        self,
        project_id: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        sort: str = "updated_desc",
        limit: int = 50,
        cursor: str | None = None,
    ) -> ListPage:
        """List memories deterministically without relevance scoring."""
        # TODO: Apply filters, stable sort, cursor pagination, and return a
        # ListPage of compact MemoryRecord metadata.
        raise NotImplementedError("TODO: implement filtered memory listing")
