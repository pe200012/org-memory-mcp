"""Shared pytest fixtures for org-mem behavior tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    """Return an isolated canonical Org memory root."""
    return tmp_path / "org" / "roam" / "agent-memory"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """Return an isolated XDG data directory."""
    return tmp_path / "xdg-data" / "org-memory-mcp"


@pytest.fixture
def config_path(tmp_path: Path) -> Path:
    """Return an isolated XDG config file path."""
    return tmp_path / "xdg-config" / "org-memory-mcp" / "config.toml"


@pytest.fixture
def valid_body() -> str:
    """Return a minimal body satisfying the required Org sections."""
    return (
        "* Content\n"
        "\n"
        "Dereference-use keeps pointer identity stable.\n"
        "\n"
        "* Sources\n"
        "\n"
        "- File: =EffSpec/Pcc/Semantics.lean=\n"
        "- Theorem: =path_use_preservation=\n"
        "\n"
        "* Related memories\n"
    )


@pytest.fixture
def evidence() -> list[dict[str, str]]:
    """Return one evidence item for agent-written memory tests."""
    return [{"kind": "symbol", "value": "path_use_preservation"}]
