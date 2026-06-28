"""SQLite metadata, FTS, and async index freshness.

This module owns all derived cache state. Org files remain canonical, so every
index row must be rebuildable from storage.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
import threading
from pathlib import Path

from org_mem.config import Config
from org_mem.models import (
    IndexRebuildResult,
    ListPage,
    MemoryRecord,
    MemoryStatus,
    MemoryType,
    SearchQuery,
    SearchResult,
)
from org_mem.org_file import parse_memory

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT UNIQUE NOT NULL,
    project_id TEXT NOT NULL,
    memory_type TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    revision INTEGER NOT NULL,
    tags TEXT NOT NULL,
    path TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project_generations (
    project_id TEXT PRIMARY KEY,
    generation INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    memory_id,
    project_id,
    title,
    body,
    tags,
    tokenize='porter unicode61'
);
"""


class MemoryIndex:
    """Rebuildable SQLite metadata and FTS index."""

    def __init__(self, config: Config) -> None:
        self._config = config
        config.data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(config.data_dir / "index.sqlite3"), check_same_thread=False
        )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        # ponytail: in-process dict suffices; no persistence needed for dirty queue
        self._dirty: dict[str, bool] = {}
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def rebuild_project(self, project_id: str) -> IndexRebuildResult:
        """Rebuild derived index rows for one project from Org files."""
        project_dir = self._config.memory_root / "projects" / project_id
        records: list[tuple[MemoryRecord, Path]] = []
        if project_dir.exists():
            for path in project_dir.rglob("*.org"):
                try:
                    record = parse_memory(path.read_text(encoding="utf-8"))
                    if record.memory_id:
                        records.append((dataclasses.replace(record, path=path), path))
                except Exception:
                    continue

        with self._lock:
            row = self._conn.execute(
                "SELECT generation FROM project_generations WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            generation = (row["generation"] if row else 0) + 1

            self._conn.execute("DELETE FROM memories WHERE project_id = ?", (project_id,))
            self._conn.execute("DELETE FROM memories_fts WHERE project_id = ?", (project_id,))

            for record, path in records:
                tags_json = json.dumps(record.tags)
                self._conn.execute(
                    "INSERT OR REPLACE INTO memories"
                    " (memory_id, project_id, memory_type, title, body, status, revision, tags, path)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        record.memory_id, project_id, record.memory_type.value,
                        record.title, record.body, record.status.value,
                        record.revision, tags_json, str(path),
                    ),
                )
                self._conn.execute(
                    "INSERT INTO memories_fts (memory_id, project_id, title, body, tags)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (record.memory_id, project_id, record.title, record.body, " ".join(record.tags)),
                )

            self._conn.execute(
                "INSERT OR REPLACE INTO project_generations (project_id, generation) VALUES (?, ?)",
                (project_id, generation),
            )
            self._conn.commit()

        return IndexRebuildResult(project_id=project_id, index_generation=generation)

    def enqueue_rebuild(self, project_id: str) -> None:
        """Mark one project dirty for background rebuild."""
        self._dirty[project_id] = True

    def pending_projects(self) -> list[str]:
        """Return dirty project IDs in deterministic order."""
        return sorted(self._dirty)

    def wait_until_index_fresh(self, project_id: str) -> None:
        """Block until a project's queued rebuild finishes."""
        if project_id in self._dirty:
            del self._dirty[project_id]
            self.rebuild_project(project_id)

    def is_fresh(self, project_id: str) -> bool:
        """Return whether a project has no pending rebuild work."""
        return project_id not in self._dirty

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search indexed memories using metadata filters and FTS."""
        self.wait_until_index_fresh(query.project_id)

        with self._lock:
            sql = (
                "SELECT m.memory_id, m.project_id, m.title, m.memory_type, m.status,"
                " m.revision, m.path, memories_fts.rank as score,"
                " snippet(memories_fts, -1, '', '', '...', 10) as snippet"
                " FROM memories_fts"
                " JOIN memories m ON memories_fts.memory_id = m.memory_id"
                " WHERE memories_fts MATCH ?"
                "   AND m.project_id = ?"
                "   AND m.status = ?"
            )
            params: list = [query.query, query.project_id, query.status]

            if query.memory_type:
                sql += " AND m.memory_type = ?"
                params.append(query.memory_type)

            for tag in query.tags:
                sql += ' AND m.tags LIKE ?'
                params.append(f'%"{tag}"%')

            sql += " ORDER BY rank LIMIT ?"
            params.append(query.limit)

            try:
                rows = self._conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                rows = []

        return [
            SearchResult(
                memory_id=row["memory_id"],
                project_id=row["project_id"],
                title=row["title"],
                memory_type=MemoryType(row["memory_type"]),
                status=MemoryStatus(row["status"]),
                revision=row["revision"],
                score=float(row["score"] or 0.0),
                matched_fields=["title", "body"],
                snippet=row["snippet"] or "",
                path=row["path"],
            )
            for row in rows
        ]

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
        with self._lock:
            sql = "SELECT * FROM memories WHERE project_id = ? AND status = ?"
            params: list = [project_id, status]

            if memory_type:
                sql += " AND memory_type = ?"
                params.append(memory_type)

            if tags:
                for tag in tags:
                    sql += ' AND tags LIKE ?'
                    params.append(f'%"{tag}"%')

            if cursor:
                op = "<" if sort == "updated_desc" else ">"
                sql += f" AND rowid {op} ?"
                params.append(int(cursor))

            order = "DESC" if sort == "updated_desc" else "ASC"
            sql += f" ORDER BY rowid {order} LIMIT ?"
            params.append(limit + 1)

            rows = self._conn.execute(sql, params).fetchall()

        has_more = len(rows) > limit
        rows = rows[:limit]

        items = [
            MemoryRecord(
                memory_id=row["memory_id"],
                project_id=row["project_id"],
                memory_type=MemoryType(row["memory_type"]),
                title=row["title"],
                body=row["body"],
                path=Path(row["path"]),
                status=MemoryStatus(row["status"]),
                revision=row["revision"],
                tags=json.loads(row["tags"]),
            )
            for row in rows
        ]

        next_cursor = str(rows[-1]["rowid"]) if has_more and rows else None
        return ListPage(items=items, next_cursor=next_cursor)
