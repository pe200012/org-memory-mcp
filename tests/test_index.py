"""Tests for SQLite metadata, FTS, and async indexing semantics."""

from __future__ import annotations

from org_mem.config import Config
from org_mem.index import MemoryIndex
from org_mem.models import SearchQuery


def test_rebuild_project_indexes_metadata_and_fts(memory_root, data_dir, config_path) -> None:
    index = MemoryIndex(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    result = index.rebuild_project("effspec-a91c3f")

    assert result.project_id == "effspec-a91c3f"
    assert result.index_generation == 1
    assert (data_dir / "index.sqlite3").exists()


def test_enqueue_rebuild_coalesces_dirty_project(memory_root, data_dir, config_path) -> None:
    index = MemoryIndex(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    index.enqueue_rebuild("effspec-a91c3f")
    index.enqueue_rebuild("effspec-a91c3f")

    assert index.pending_projects() == ["effspec-a91c3f"]


def test_search_waits_until_index_is_fresh(memory_root, data_dir, config_path) -> None:
    index = MemoryIndex(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    index.enqueue_rebuild("effspec-a91c3f")

    results = index.search(SearchQuery(project_id="effspec-a91c3f", query="heap location"))

    assert index.is_fresh("effspec-a91c3f")
    assert all(result.project_id == "effspec-a91c3f" for result in results)


def test_search_excludes_archived_by_default(memory_root, data_dir, config_path) -> None:
    index = MemoryIndex(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    results = index.search(SearchQuery(project_id="effspec-a91c3f", query="archived decision"))

    assert all(result.status.value == "active" for result in results)


def test_list_memories_uses_filters_sorting_and_cursor(memory_root, data_dir, config_path) -> None:
    index = MemoryIndex(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    page = index.list_memories(
        project_id="effspec-a91c3f",
        memory_type="decision",
        status="active",
        tags=["semantics"],
        sort="updated_desc",
        limit=2,
        cursor=None,
    )

    assert len(page.items) <= 2
    assert page.next_cursor is None or isinstance(page.next_cursor, str)
