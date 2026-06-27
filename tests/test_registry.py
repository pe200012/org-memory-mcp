"""Tests for project identity and registry persistence."""

from __future__ import annotations

import json

from org_mem.config import Config
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
