"""Tests for configuration defaults and MCP-friendly overrides."""

from __future__ import annotations

from pathlib import Path

from org_mem.config import Config, load_config


def test_load_config_uses_design_defaults(monkeypatch) -> None:
    monkeypatch.delenv("ORG_MEMORY_ROOT", raising=False)
    monkeypatch.delenv("ORG_MEMORY_DATA_DIR", raising=False)

    config = load_config(config_path=None)

    assert config.memory_root == Path.home() / "Documents/org/roam/agent-memory"
    assert config.data_dir == Path.home() / ".local/share/org-memory-mcp"
    assert config.config_path == Path.home() / ".config/org-memory-mcp/config.toml"
    assert config.embedding_provider == "local"


def test_environment_overrides_take_precedence(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ORG_MEMORY_ROOT", str(tmp_path / "memory-root"))
    monkeypatch.setenv("ORG_MEMORY_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("ORG_MEMORY_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("ORG_MEMORY_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("ORG_MEMORY_OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("ORG_MEMORY_OPENAI_API_KEY", "secret")

    config = load_config(config_path=None)

    assert config.memory_root == tmp_path / "memory-root"
    assert config.data_dir == tmp_path / "data"
    assert config.embedding_provider == "openai-compatible"
    assert config.embedding_model == "text-embedding-3-small"
    assert config.openai_base_url == "https://api.example.test/v1"
    assert config.openai_api_key == "secret"


def test_config_file_values_are_loaded_before_environment_overrides(config_path) -> None:
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        "\n".join(
            [
                'memory_root = "/tmp/org-memory"',
                'data_dir = "/tmp/org-memory-data"',
                'embedding_provider = "local"',
                'embedding_model = "all-MiniLM-L6-v2"',
            ]
        ),
        encoding="utf-8",
    )

    config = load_config(config_path=config_path)

    assert config == Config(
        memory_root=Path("/tmp/org-memory"),
        data_dir=Path("/tmp/org-memory-data"),
        config_path=config_path,
        embedding_provider="local",
        embedding_model="all-MiniLM-L6-v2",
        openai_base_url=None,
        openai_api_key=None,
    )
