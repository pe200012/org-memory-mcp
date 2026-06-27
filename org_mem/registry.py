"""Project registry for stable org-mem project IDs.

This module maps repository roots to stable project IDs and creates project
directory skeletons under the canonical memory root.
"""

from __future__ import annotations

from pathlib import Path

from org_mem.config import Config
from org_mem.models import ProjectInfo


class ProjectRegistry:
    """Root-to-project mapping backed by XDG data."""

    def __init__(self, config: Config) -> None:
        """Create a registry bound to one resolved config."""
        # TODO: Store config, compute projects.json path, and prepare lazy
        # loading so tests can isolate registry state per tmp directory.
        raise NotImplementedError("TODO: implement project registry initialization")

    def activate_project(self, root_path: Path, name_hint: str | None = None) -> ProjectInfo:
        """Resolve or create a stable project ID for a root path."""
        # TODO: Resolve root_path, derive slug/hash, persist root mapping,
        # create `projects/<project_id>/project.org`, and ensure type dirs.
        raise NotImplementedError("TODO: implement idempotent project activation")

    def get_project(self, project_id: str) -> ProjectInfo:
        """Read an existing project record by project ID."""
        # TODO: Load projects.json, find the matching project_id, and return a
        # ProjectInfo with the canonical project directory.
        raise NotImplementedError("TODO: implement project lookup")

    def ensure_global_project(self) -> ProjectInfo:
        """Ensure the reserved global memory tree exists."""
        # TODO: Create the `global` memory tree with the same type directories
        # and project.org conventions used for normal projects.
        raise NotImplementedError("TODO: implement global project setup")
