"""Operational logging helpers for org-mem.

This module redacts sensitive fields before events reach stderr or rotating
log files. It has no dependency on storage or MCP internals.
"""

from __future__ import annotations

from typing import Any


_REDACTED_FIELDS = frozenset({"body", "embedding_input", "source_snippet", "api_key", "token", "password", "secret"})


def redact_log_event(event: dict[str, Any]) -> dict[str, Any]:
    """Redact memory bodies, embedding inputs, source snippets, and secrets."""
    return {k: ("[redacted]" if k in _REDACTED_FIELDS else v) for k, v in event.items()}
