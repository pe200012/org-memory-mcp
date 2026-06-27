"""Tests for operational logging redaction policy."""

from __future__ import annotations

from org_mem.logging import redact_log_event


def test_redact_log_event_keeps_operational_fields() -> None:
    event = redact_log_event(
        {
            "tool": "memory_write",
            "project_id": "effspec-a91c3f",
            "memory_id": "0197a8d4-52dc-71ec-a1cb-0f93eb217b38",
            "revision": 3,
            "duration_ms": 12,
            "index_generation": 7,
            "error_code": None,
            "body": "Private proof notes",
            "embedding_input": "Private proof notes",
            "api_key": "secret",
        }
    )

    assert event["tool"] == "memory_write"
    assert event["project_id"] == "effspec-a91c3f"
    assert event["memory_id"] == "0197a8d4-52dc-71ec-a1cb-0f93eb217b38"
    assert event["body"] == "[redacted]"
    assert event["embedding_input"] == "[redacted]"
    assert event["api_key"] == "[redacted]"
