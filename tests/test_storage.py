"""Tests for canonical Org file storage behavior."""

from __future__ import annotations

import pytest

from org_mem.config import Config
from org_mem.models import Evidence, LinkRelation, MemoryDraft, MemoryType
from org_mem.storage import MemoryStorage, RevisionConflict


def test_write_memory_creates_type_directory_file(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Preserve heap location during dereference use",
        body=valid_body,
        evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
        tags=["effspec"],
        created_by="agent",
    )

    record = storage.write_memory(draft)

    assert record.path.parent == memory_root / "projects" / "effspec-a91c3f" / "decisions"
    assert record.path.name.endswith(".org")
    assert record.revision == 1
    assert record.memory_id in record.path.read_text(encoding="utf-8")


def test_read_memory_returns_stored_record(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Read me",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    loaded = storage.read_memory(record.memory_id)

    assert loaded.memory_id == record.memory_id
    assert loaded.title == "Read me"
    assert loaded.revision == 1


def test_update_memory_requires_expected_revision(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Original",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    with pytest.raises(RevisionConflict):
        storage.update_memory(record.memory_id, expected_revision=2, title="Stale update")


def test_update_memory_increments_revision(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Original",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    updated = storage.update_memory(record.memory_id, expected_revision=1, title="Updated")

    assert updated.title == "Updated"
    assert updated.revision == 2


def test_archive_memory_keeps_file_and_sets_status(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Archive me",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    archived = storage.archive_memory(record.memory_id, expected_revision=1, reason="superseded")

    assert archived.status.value == "archived"
    assert archived.path.exists()
    assert archived.revision == 2


def test_link_memory_adds_typed_org_id_relation(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    source = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Source",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )
    target = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.INVARIANT,
            title="Target",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    linked = storage.link_memory(
        source.memory_id,
        target.memory_id,
        relation=LinkRelation.SUPPORTS,
        note="used by proof",
        expected_revision=1,
    )

    assert linked.revision == 2
    assert f"[[id:{target.memory_id}][supports: Target]]" in linked.path.read_text(encoding="utf-8")


def test_review_writes_project_overview_with_reviewed_revisions(memory_root, data_dir, config_path) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    overview = storage.write_project_overview(
        project_id="effspec-a91c3f",
        overview_body="* Project map\n\nCurrent proof memory map.\n",
        reviewed_revisions=[{"memory_id": "0197a8d4-52dc-71ec-a1cb-0f93eb217b38", "revision": 3}],
        expected_revision=None,
    )

    assert overview.path == memory_root / "projects" / "effspec-a91c3f" / "project.org"
    text = overview.path.read_text(encoding="utf-8")
    assert "0197a8d4-52dc-71ec-a1cb-0f93eb217b38" in text
    assert "REVISION=3" in text
