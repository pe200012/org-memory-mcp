"""Integration-style tests for the application service API."""

from __future__ import annotations

from org_mem.config import Config
from org_mem.hints import SCHEMA_TEXT, SCHEMA_URI
from org_mem.models import Evidence, LinkRelation, MemoryDraft, MemoryType
from org_mem.service import MemoryService


def test_service_project_activation_returns_schema_guidance(memory_root, data_dir, config_path, tmp_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    response = service.memory_project(str(repo_root), name_hint="demo")

    assert response["ok"] is True
    assert response["schema_uri"] == SCHEMA_URI
    assert response["schema_text"] == SCHEMA_TEXT
    assert "Memory types:" in response["schema_text"]
    assert "Required Org sections:" in response["schema_text"]
    assert "Agent-written non-overview memories require evidence" in response["schema_text"]


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


def test_service_global_search_returns_cross_project_results(
    memory_root, data_dir, config_path, valid_body, evidence
) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    for project_id in ["effspec-a91c3f", "klipper-b72a90"]:
        service.memory_write(
            MemoryDraft(
                project_id=project_id,
                memory_type=MemoryType.DECISION,
                title=f"{project_id} reusable workflow",
                body=valid_body.replace("pointer identity", "durable reusable workflow"),
                evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
                tags=["workflow"],
                created_by="agent",
            )
        )

    response = service.memory_global_search(query="durable reusable", tags=["workflow"])

    assert response["ok"] is True
    assert {result["project_id"] for result in response["results"]} == {"effspec-a91c3f", "klipper-b72a90"}


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
    assert response["error"]["field"] == "evidence"
    assert "evidence" in response["error"]["hint"]


def test_service_read_missing_memory_returns_useful_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_read("missing-memory-id")

    assert response["ok"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["field"] == "memory_id"
    assert "memory_search" in response["error"]["hint"]


def test_service_update_reports_revision_conflict(memory_root, data_dir, config_path, valid_body, evidence) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    created = service.storage.write_memory(
        MemoryDraft(
            project_id="effspec-a91c3f",
            memory_type=MemoryType.DECISION,
            title="Original",
            body=valid_body,
            evidence=[Evidence(kind="symbol", value=evidence[0]["value"])],
            created_by="agent",
        )
    )

    response = service.memory_update(created.memory_id, expected_revision=2, title="Stale")

    assert response["ok"] is False
    assert response["error"]["code"] == "revision_conflict"
    assert response["error"]["field"] == "expected_revision"
    assert "memory_read" in response["error"]["hint"]


def test_service_update_missing_memory_returns_useful_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_update("missing-memory-id", expected_revision=1, title="Missing")

    assert response["ok"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["field"] == "memory_id"
    assert "memory_search" in response["error"]["hint"]


def test_service_list_invalid_filter_returns_useful_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_list(project_id="effspec-a91c3f", memory_type="bogus")

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_memory_type"
    assert response["error"]["field"] == "memory_type"
    assert "decision" in response["error"]["hint"]


def test_service_search_invalid_status_returns_useful_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_search(project_id="effspec-a91c3f", query="heap", status="bogus")

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_status"
    assert response["error"]["field"] == "status"
    assert "active" in response["error"]["hint"]


def test_service_global_search_reports_index_rebuild_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))
    project_dir = memory_root / "projects" / "effspec-a91c3f"
    project_dir.mkdir(parents=True)
    (project_dir / "bad.org").write_text(
        "\n".join(
            [
                ":PROPERTIES:",
                ":ID:       bad-memory",
                ":PROJECT_ID:      effspec-a91c3f",
                ":MEMORY_TYPE:     bogus",
                ":STATUS:          active",
                ":REVISION:        1",
                ":END:",
                "#+title: Bad memory",
                "* Content",
            ]
        ),
        encoding="utf-8",
    )

    response = service.memory_global_search(query="heap")

    assert response["ok"] is False
    assert response["error"]["code"] == "index_rebuild_failed"
    assert response["error"]["field"] == "index"
    assert "bad.org" in response["error"]["message"]


def test_service_link_missing_memory_returns_useful_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_link("missing-source", "missing-target", relation=LinkRelation.SUPPORTS)

    assert response["ok"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["field"] == "memory_id"


def test_service_archive_missing_memory_returns_useful_error(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_archive("missing-memory-id", expected_revision=1)

    assert response["ok"] is False
    assert response["error"]["code"] == "not_found"
    assert response["error"]["field"] == "memory_id"


def test_service_review_reports_malformed_reviewed_revision(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_review(
        project_id="effspec-a91c3f",
        overview_body="* Project map\n\nCurrent memory state.\n",
        reviewed_revisions=[{"memory_id": "0197a8d4-52dc-71ec-a1cb-0f93eb217b38"}],
    )

    assert response["ok"] is False
    assert response["error"]["code"] == "invalid_reviewed_revisions"
    assert response["error"]["field"] == "reviewed_revisions"
    assert "revision" in response["error"]["message"]


def test_service_review_updates_project_overview(memory_root, data_dir, config_path) -> None:
    service = MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    response = service.memory_review(
        project_id="effspec-a91c3f",
        overview_body="* Project map\n\nCurrent memory state.\n",
        reviewed_revisions=[{"memory_id": "0197a8d4-52dc-71ec-a1cb-0f93eb217b38", "revision": 3}],
    )

    assert response["ok"] is True
    assert response["path"].endswith("projects/effspec-a91c3f/project.org")
