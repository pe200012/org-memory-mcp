"""SQLite metadata, FTS, and async index freshness.

This module owns all derived cache state. Org files remain canonical, so every
index row must be rebuildable from storage.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import sqlite3
import threading
from pathlib import Path

from org_mem.config import Config
from org_mem.locking import FileLock, state_lock_path
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
CREATE TABLE IF NOT EXISTS project_snapshots (
    project_id TEXT PRIMARY KEY,
    snapshot TEXT NOT NULL
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
        self._lock_path = state_lock_path(config)
        config.data_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(config.data_dir / "index.sqlite3"), check_same_thread=False, timeout=30
        )
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        # Dirty queue is in-process because Org files are canonical.
        self._dirty: dict[str, bool] = {}
        with FileLock(self._lock_path):
            with self._lock:
                self._conn.executescript(_SCHEMA)
                self._conn.commit()

    def rebuild_project(self, project_id: str) -> IndexRebuildResult:
        """Rebuild derived index rows for one project from Org files."""
        with FileLock(self._lock_path):
            project_dir = self._config.memory_root / "projects" / project_id
            records: list[tuple[MemoryRecord, Path]] = []
            errors: list[str] = []
            if project_dir.exists():
                for path in project_dir.rglob("*.org"):
                    try:
                        record = parse_memory(path.read_text(encoding="utf-8"))
                        if record.memory_id:
                            records.append((dataclasses.replace(record, path=path), path))
                    except Exception as exc:
                        errors.append(f"{path}: {exc}")
            if errors:
                raise IndexRebuildError("; ".join(errors))

            snapshot = self._project_snapshot(project_id)
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
                self._conn.execute(
                    "INSERT OR REPLACE INTO project_snapshots (project_id, snapshot) VALUES (?, ?)",
                    (project_id, snapshot),
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
        elif self._needs_rebuild(project_id):
            self.rebuild_project(project_id)

    def wait_until_all_indexes_fresh(self) -> None:
        """Block until every known project has a fresh derived index."""
        for project_id in self._known_project_ids():
            project_dir = self._config.memory_root / "projects" / project_id
            if project_id in self._dirty:
                del self._dirty[project_id]
                self.rebuild_project(project_id)
            elif self._needs_rebuild(project_id) or not project_dir.exists():
                self.rebuild_project(project_id)

    def is_fresh(self, project_id: str) -> bool:
        """Return whether a project has no pending rebuild work."""
        return project_id not in self._dirty

    def search(self, query: SearchQuery) -> list[SearchResult]:
        """Search indexed memories using metadata filters and FTS."""
        self.wait_until_index_fresh(query.project_id)

        rows = self._search_rows(
            query=query.query,
            status=query.status,
            memory_type=query.memory_type,
            tags=query.tags,
            limit=query.limit,
            project_id=query.project_id,
        )
        return self._results_from_rows(rows)

    def search_global(
        self,
        query: str,
        memory_type: str | None = None,
        status: str = "active",
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        """Search indexed memories across every project."""
        self.wait_until_all_indexes_fresh()

        rows = self._search_rows(
            query=query,
            status=status,
            memory_type=memory_type,
            tags=tags or [],
            limit=limit,
            project_id=None,
        )
        return self._results_from_rows(rows)

    def _search_rows(
        self,
        query: str,
        status: str,
        memory_type: str | None,
        tags: list[str],
        limit: int,
        project_id: str | None,
    ) -> list[sqlite3.Row]:
        with self._lock:
            sql = (
                "SELECT m.memory_id, m.project_id, m.title, m.memory_type, m.status,"
                " m.revision, m.path, memories_fts.rank as score,"
                " snippet(memories_fts, -1, '', '', '...', 10) as snippet"
                " FROM memories_fts"
                " JOIN memories m ON memories_fts.memory_id = m.memory_id"
                " WHERE memories_fts MATCH ?"
                "   AND m.status = ?"
            )
            params: list = [query, status]

            if project_id is not None:
                sql += " AND m.project_id = ?"
                params.append(project_id)

            if memory_type:
                sql += " AND m.memory_type = ?"
                params.append(memory_type)

            for tag in tags:
                sql += ' AND m.tags LIKE ?'
                params.append(f'%"{tag}"%')

            sql += " ORDER BY rank LIMIT ?"
            params.append(limit)

            try:
                return self._conn.execute(sql, params).fetchall()
            except sqlite3.OperationalError:
                return []

    def _results_from_rows(self, rows: list[sqlite3.Row]) -> list[SearchResult]:
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

    def _needs_rebuild(self, project_id: str) -> bool:
        """Return whether canonical Org files changed since the last rebuild."""
        with FileLock(self._lock_path):
            project_dir = self._config.memory_root / "projects" / project_id
            if not project_dir.exists():
                return False
            snapshot = self._project_snapshot(project_id)
            with self._lock:
                row = self._conn.execute(
                    "SELECT snapshot FROM project_snapshots WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
            return row is None or row["snapshot"] != snapshot

    def _known_project_ids(self) -> list[str]:
        """Return project IDs discovered from disk, dirty queue, and index rows."""
        project_ids = set(self._dirty)
        projects_dir = self._config.memory_root / "projects"
        with FileLock(self._lock_path):
            if projects_dir.exists():
                project_ids.update(path.name for path in projects_dir.iterdir() if path.is_dir())
            with self._lock:
                rows = self._conn.execute("SELECT DISTINCT project_id FROM memories").fetchall()
            project_ids.update(row["project_id"] for row in rows)
        return sorted(project_ids)

    def _project_snapshot(self, project_id: str) -> str:
        """Return a deterministic fingerprint for a project's Org file tree."""
        project_dir = self._config.memory_root / "projects" / project_id
        if not project_dir.exists():
            return "missing"
        digest = hashlib.sha256()
        for path in sorted(project_dir.rglob("*.org")):
            stat = path.stat()
            rel = path.relative_to(project_dir).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
            digest.update(b"\0")
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(b"\0")
        return digest.hexdigest()


class IndexRebuildError(RuntimeError):
    """Raised when canonical Org files cannot be indexed safely."""
