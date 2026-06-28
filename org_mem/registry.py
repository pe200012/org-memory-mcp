"""Project registry for stable org-mem project IDs.

This module maps repository roots to stable project IDs and creates project
directory skeletons under the canonical memory root.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from org_mem.config import Config
from org_mem.locking import FileLock, atomic_write_text, state_lock_path
from org_mem.models import MemoryType, ProjectInfo

_TYPE_DIRS = {
    MemoryType.OVERVIEW: "overview",
    MemoryType.ARCHITECTURE: "architecture",
    MemoryType.DECISION: "decisions",
    MemoryType.INVARIANT: "invariants",
    MemoryType.CONVENTION: "conventions",
    MemoryType.PROBLEM: "problems",
    MemoryType.HANDOFF: "handoffs",
    MemoryType.OUTCOME: "outcomes",
}


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "project"


def _project_id(name_hint: str | None, root: Path) -> str:
    base = _slug(name_hint) if name_hint else _slug(root.name)
    h = hashlib.sha1(str(root).encode()).hexdigest()[:6]
    return f"{base}-{h}"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"roots": {}}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, indent=2))


def _scaffold(project_dir: Path, root: Path, name_hint: str | None) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    for dirname in _TYPE_DIRS.values():
        (project_dir / dirname).mkdir(exist_ok=True)
    org = project_dir / "project.org"
    if not org.exists():
        atomic_write_text(
            org,
            f"#+title: {name_hint or root.name}\n#+root: {root}\n",
        )


class ProjectRegistry:
    """Root-to-project mapping backed by XDG data."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._registry_path = config.data_dir / "projects.json"
        self._lock_path = state_lock_path(config)

    def activate_project(self, root_path: Path, name_hint: str | None = None) -> ProjectInfo:
        """Resolve or create a stable project ID for a root path."""
        with FileLock(self._lock_path):
            root = root_path.resolve()
            data = _load(self._registry_path)
            key = str(root)

            if key in data["roots"]:
                project_id = data["roots"][key]["project_id"]
                stored_hint = data["roots"][key].get("name_hint")
            else:
                project_id = _project_id(name_hint, root)
                stored_hint = name_hint
                data["roots"][key] = {"project_id": project_id, "name_hint": name_hint}
                _save(self._registry_path, data)

            project_dir = self._config.memory_root / "projects" / project_id
            _scaffold(project_dir, root, stored_hint or name_hint)

            return ProjectInfo(
                project_id=project_id,
                root_path=root,
                name_hint=stored_hint,
                project_dir=project_dir,
            )

    def get_project(self, project_id: str) -> ProjectInfo:
        """Read an existing project record by project ID."""
        with FileLock(self._lock_path):
            data = _load(self._registry_path)
            for root_str, entry in data["roots"].items():
                if entry["project_id"] == project_id:
                    root = Path(root_str)
                    return ProjectInfo(
                        project_id=project_id,
                        root_path=root,
                        name_hint=entry.get("name_hint"),
                        project_dir=self._config.memory_root / "projects" / project_id,
                    )
        raise KeyError(f"project_id not found: {project_id}")

    def ensure_global_project(self) -> ProjectInfo:
        """Ensure the reserved global memory tree exists."""
        with FileLock(self._lock_path):
            project_id = "global"
            project_dir = self._config.memory_root / "projects" / project_id
            root = self._config.memory_root
            _scaffold(project_dir, root, "global")
            return ProjectInfo(
                project_id=project_id,
                root_path=root,
                name_hint="global",
                project_dir=project_dir,
            )
