"""Tests for SQLite metadata, FTS, and async indexing semantics."""

from __future__ import annotations

from org_mem.config import Config
from org_mem.index import IndexRebuildError, MemoryIndex
from org_mem.models import Evidence, MemoryDraft, MemoryType, SearchQuery
from org_mem.storage import MemoryStorage


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


def test_rebuild_project_reports_malformed_org_files(memory_root, data_dir, config_path) -> None:
    project_dir = memory_root / "projects" / "effspec-a91c3f" / "decisions"
    project_dir.mkdir(parents=True)
    (project_dir / "bad.org").write_text(
        ":PROPERTIES:\n:ID:       bad\n:MEMORY_TYPE:     not-a-type\n:END:\n#+title: Bad\n",
        encoding="utf-8",
    )
    index = MemoryIndex(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    try:
        index.rebuild_project("effspec-a91c3f")
    except IndexRebuildError as exc:
        assert "bad.org" in str(exc)
    else:
        raise AssertionError("malformed Org file should make rebuild fail")


def test_search_rebuilds_when_another_instance_wrote_org_files(
    memory_root, data_dir, config_path, valid_body, evidence
) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    index = MemoryIndex(config)
    index.rebuild_project("effspec-a91c3f")
    storage = MemoryStorage(config)
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="External write visibility",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    results = index.search(SearchQuery(project_id="effspec-a91c3f", query="pointer identity"))

    assert [result.memory_id for result in results] == [record.memory_id]


def test_global_search_returns_hits_across_projects_with_provenance(
    memory_root, data_dir, config_path, valid_body, evidence
) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    storage = MemoryStorage(config)
    first = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Reusable lock discipline",
            body=valid_body.replace("pointer identity", "advisory lock reusable workflow"),
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            tags=["workflow"],
            created_by="agent",
        )
    )
    second = storage.write_memory(
        MemoryDraft(
            project_id="klipper-b72a90",
            memory_type=MemoryType.OUTCOME,
            title="Reusable SQLite recovery",
            body=valid_body.replace("pointer identity", "advisory lock reusable workflow"),
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            tags=["workflow"],
            created_by="agent",
        )
    )
    index = MemoryIndex(config)

    results = index.search_global(query="advisory lock reusable", tags=["workflow"])

    assert {result.memory_id for result in results} == {first.memory_id, second.memory_id}
    assert {result.project_id for result in results} == {"effspec-a91c3f", "klipper-b72a90"}


def test_global_search_rebuilds_changed_project_trees(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    index = MemoryIndex(config)
    index.rebuild_project("effspec-a91c3f")
    record = MemoryStorage(config).write_memory(
        MemoryDraft(
            project_id="new-project-123",
            memory_type=MemoryType.DECISION,
            title="External global write visibility",
            body=valid_body.replace("pointer identity", "cross project freshness marker"),
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    results = index.search_global(query="freshness marker")

    assert [result.memory_id for result in results] == [record.memory_id]
