"""Configuration loading for org-mem.

This module owns XDG defaults, TOML config loading, and environment overrides.
It should stay free of storage, indexing, and MCP server concerns.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, fields, replace
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
    xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    xdg_data = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()

    if config_path is None:
        config_path = xdg_config / "org-memory-mcp" / "config.toml"

    kwargs: dict = {
        "config_path": config_path,
        "data_dir": xdg_data / "org-memory-mcp",
        "memory_root": Path("~/Documents/org/roam/agent-memory").expanduser(),
    }

    if config_path.exists():
        with open(config_path, "rb") as f:
            toml = tomllib.load(f)
        path_fields = {"memory_root", "data_dir"}
        for key in ("memory_root", "data_dir", "embedding_provider", "embedding_model", "openai_base_url", "openai_api_key"):
            if key in toml:
                kwargs[key] = Path(toml[key]).expanduser() if key in path_fields else toml[key]

    env_map = {
        "ORG_MEMORY_ROOT": ("memory_root", lambda v: Path(v).expanduser()),
        "ORG_MEMORY_DATA_DIR": ("data_dir", lambda v: Path(v).expanduser()),
        "ORG_MEMORY_EMBEDDING_PROVIDER": ("embedding_provider", str),
        "ORG_MEMORY_EMBEDDING_MODEL": ("embedding_model", str),
        "ORG_MEMORY_OPENAI_BASE_URL": ("openai_base_url", str),
        "ORG_MEMORY_OPENAI_API_KEY": ("openai_api_key", str),
    }
    for env_key, (field, cast) in env_map.items():
        if (val := os.environ.get(env_key)) is not None:
            kwargs[field] = cast(val)

    return Config(**kwargs)
