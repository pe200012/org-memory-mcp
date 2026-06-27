"""Operational logging helpers for org-mem.

This module redacts sensitive fields before events reach stderr or rotating
log files. It has no dependency on storage or MCP internals.
"""

from __future__ import annotations

from typing import Any


def redact_log_event(event: dict[str, Any]) -> dict[str, Any]:
    """Redact memory bodies, embedding inputs, source snippets, and secrets."""
    # TODO: Copy the event, preserve operational fields, redact content-bearing
    # and secret fields, and return a JSON-serializable dictionary.
    raise NotImplementedError("TODO: implement operational log redaction")
