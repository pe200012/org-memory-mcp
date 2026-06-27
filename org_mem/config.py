"""Configuration loading for org-mem.

This module owns XDG defaults, TOML config loading, and environment overrides.
It should stay free of storage, indexing, and MCP server concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Config:
    """Runtime configuration resolved from defaults, config file, and env."""

    memory_root: Path
    data_dir: Path
    config_path: Path
    embedding_provider: str = "local"
    embedding_model: str | None = None
    openai_base_url: str | None = None
    openai_api_key: str | None = None


def load_config(config_path: Path | None = None) -> Config:
    """Load config from XDG defaults, TOML, and environment overrides."""
    # TODO: Resolve default paths, parse `config_path` with `tomllib`, then
    # apply ORG_MEMORY_* environment overrides so MCP client config can inject
    # deployment-specific settings without editing the persistent config file.
    raise NotImplementedError("TODO: implement XDG config loading and environment overrides")
