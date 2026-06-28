"""Tests for project identity and registry persistence."""

from __future__ import annotations

import json
import multiprocessing
import time

from org_mem.config import Config
from org_mem.locking import FileLock, state_lock_path
from org_mem.registry import ProjectRegistry


def test_memory_project_creates_stable_project_id(memory_root, data_dir, config_path, tmp_path) -> None:
    project_root = tmp_path / "EffSpec Proofs"
    project_root.mkdir()
    registry = ProjectRegistry(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    first = registry.activate_project(root_path=project_root, name_hint="effspec")
    second = registry.activate_project(root_path=project_root, name_hint="renamed-hint")

    assert first.project_id == second.project_id
    assert first.project_id.startswith("effspec-")
    assert first.root_path == project_root.resolve()


def test_memory_project_persists_root_mapping(memory_root, data_dir, config_path, tmp_path) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    registry = ProjectRegistry(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    project = registry.activate_project(root_path=project_root, name_hint="repo")

    registry_path = data_dir / "projects.json"
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    assert payload["roots"][str(project_root.resolve())]["project_id"] == project.project_id


def test_memory_project_creates_type_directories(memory_root, data_dir, config_path, tmp_path) -> None:
    project_root = tmp_path / "repo"
    project_root.mkdir()
    registry = ProjectRegistry(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))

    project = registry.activate_project(root_path=project_root, name_hint="repo")

    project_dir = memory_root / "projects" / project.project_id
    assert (project_dir / "project.org").exists()
    for dirname in [
        "overview",
        "architecture",
        "decisions",
        "invariants",
        "conventions",
        "problems",
        "handoffs",
        "outcomes",
    ]:
        assert (project_dir / dirname).is_dir()


def _activate_project_after_lock_release(
    config: Config,
    root_path,
    ready: multiprocessing.Event,
    queue: multiprocessing.Queue,
) -> None:
    ready.set()
    project = ProjectRegistry(config).activate_project(root_path=root_path, name_hint="repo")
    queue.put(project.project_id)


def test_memory_project_waits_for_shared_state_lock(memory_root, data_dir, config_path, tmp_path) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    project_root = tmp_path / "repo"
    project_root.mkdir()
    ready = multiprocessing.Event()
    queue = multiprocessing.Queue()

    with FileLock(state_lock_path(config)):
        worker = multiprocessing.Process(
            target=_activate_project_after_lock_release,
            args=(config, project_root, ready, queue),
        )
        worker.start()
        assert ready.wait(timeout=5)
        time.sleep(0.2)
        assert queue.empty()

    worker.join(timeout=5)
    assert worker.exitcode == 0
    assert queue.get(timeout=1).startswith("repo-")
