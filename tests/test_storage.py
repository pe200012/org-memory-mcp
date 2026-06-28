"""Tests for canonical Org file storage behavior."""

from __future__ import annotations

import multiprocessing
import time

import pytest

from org_mem.config import Config
from org_mem.locking import FileLock, state_lock_path
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
    assert record.path.name[:10].count("-") == 2
    assert "preserve-heap-location-during-dereference-use" in record.path.name
    assert record.path.name.endswith(".org")
    assert record.revision == 1
    assert record.memory_id in record.path.read_text(encoding="utf-8")


def test_write_memory_uses_unique_filename_for_duplicate_titles(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    first = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Same Title",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )
    second = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Same Title",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    assert first.memory_id != second.memory_id
    assert first.path != second.path
    assert first.path.exists()
    assert second.path.exists()


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

    updated_body = valid_body.replace("Dereference-use keeps pointer identity stable.", "Updated body text.")
    updated = storage.update_memory(
        record.memory_id,
        expected_revision=1,
        title="Updated",
        body=updated_body,
        evidence=[{"kind": "file", "value": "Updated.lean"}],
        tags=["updated", "semantics"],
    )

    assert updated.title == "Updated"
    assert updated.revision == 2
    assert "Updated body text." in updated.body
    assert updated.tags == ["updated", "semantics", "decision"]
    assert Evidence(kind="source", value="Updated.lean") in updated.evidence
    text = updated.path.read_text(encoding="utf-8")
    assert ":UPDATED:" in text


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


def test_review_preserves_project_overview_id_across_updates(memory_root, data_dir, config_path) -> None:
    storage = MemoryStorage(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    first = storage.write_project_overview(
        project_id="effspec-a91c3f",
        overview_body="* Project map\n\nFirst.\n",
        reviewed_revisions=[{"memory_id": "m1", "revision": 1}],
        expected_revision=None,
    )
    second = storage.write_project_overview(
        project_id="effspec-a91c3f",
        overview_body="* Project map\n\nSecond.\n",
        reviewed_revisions=[{"memory_id": "m1", "revision": 2}],
        expected_revision=1,
    )

    assert second.memory_id == first.memory_id
    assert second.revision == 2


def _update_memory_after_lock_release(
    config: Config,
    memory_id: str,
    ready: multiprocessing.Event,
    queue: multiprocessing.Queue,
) -> None:
    ready.set()
    started = time.monotonic()
    record = MemoryStorage(config).update_memory(memory_id, expected_revision=1, title="Blocked update")
    queue.put((record.revision, time.monotonic() - started))


def _read_memory_after_lock_release(
    config: Config,
    memory_id: str,
    ready: multiprocessing.Event,
    queue: multiprocessing.Queue,
) -> None:
    ready.set()
    queue.put(MemoryStorage(config).read_memory(memory_id).revision)


def test_update_memory_waits_for_shared_state_lock(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    storage = MemoryStorage(config)
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Concurrent update",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )
    ready = multiprocessing.Event()
    queue = multiprocessing.Queue()
    with FileLock(state_lock_path(config)):
        worker = multiprocessing.Process(
            target=_update_memory_after_lock_release,
            args=(config, record.memory_id, ready, queue),
        )
        worker.start()
        try:
            assert ready.wait(timeout=5)
            time.sleep(0.2)
            assert queue.empty()
        finally:
            worker.join(timeout=0.01)

    try:
        worker.join(timeout=5)
        assert worker.exitcode == 0
        revision, elapsed = queue.get(timeout=1)
    finally:
        worker.join(timeout=5)

    assert revision == 2
    assert elapsed >= 0.15


def test_read_memory_waits_for_shared_state_lock(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    storage = MemoryStorage(config)
    record = storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Concurrent read",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    ready = multiprocessing.Event()
    queue = multiprocessing.Queue()
    with FileLock(state_lock_path(config)):
        started = time.monotonic()
        reader = multiprocessing.Process(
            target=_read_memory_after_lock_release,
            args=(config, record.memory_id, ready, queue),
        )
        reader.start()
        assert ready.wait(timeout=5)
        time.sleep(0.2)
        assert queue.empty()

    reader.join(timeout=5)
    assert reader.exitcode == 0
    assert queue.get(timeout=1) == 1
    assert time.monotonic() - started >= 0.15
