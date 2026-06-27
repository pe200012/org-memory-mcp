"""Integration-style tests for the application service API."""

from __future__ import annotations

from org_mem.config import Config
from org_mem.models import Evidence, MemoryDraft, MemoryType
from org_mem.service import MemoryService


def test_service_write_enqueues_reindex(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Preserve heap location during dereference use",
        body=valid_body,
        evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
        created_by="agent",
    )

    response = service.memory_write(draft)

    assert response["ok"] is True
    assert response["indexed"] is False
    assert service.index.pending_projects() == ["effspec-a91c3f"]


def test_service_search_blocks_until_fresh(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    service.index.enqueue_rebuild("effspec-a91c3f")

    response = service.memory_search(project_id="effspec-a91c3f", query="heap location")

    assert response["ok"] is True
    assert service.index.is_fresh("effspec-a91c3f")


def test_service_validation_error_uses_ok_envelope(memory_root, data_dir, config_path, valid_body) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    draft = MemoryDraft(
        project_id="effspec-a91c3f",
        memory_type=MemoryType.DECISION,
        title="Missing evidence",
        body=valid_body,
        evidence=[],
        created_by="agent",
    )

    response = service.memory_write(draft)

    assert response["ok"] is False
    assert response["error"]["code"] == "missing_required_evidence"


def test_service_review_updates_project_overview(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_review(
        project_id="effspec-a91c3f",
        overview_body="* Project map\n\nCurrent memory state.\n",
        reviewed_revisions=[{"memory_id": "0197a8d4-52dc-71ec-a1cb-0f93eb217b38", "revision": 3}],
    )

    assert response["ok"] is True
    assert response["path"].endswith("projects/effspec-a91c3f/project.org")
