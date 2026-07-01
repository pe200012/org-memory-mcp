"""Golden-set retrieval benchmark seed.

This is the gate for retrieval changes, not a finished benchmark. Each case is a
(query -> expected memory_id) fact about how curated memories should be found.

Grow it before adding retrieval features. The rule: a new channel (dense
embeddings, typed-graph expansion, an edge table) must not regress these cases,
and is only justified when it turns a currently-failing case green. If plain
status-aware FTS already passes everything you can think of, the edge table is
YAGNI.
"""

from __future__ import annotations

import pytest

from org_mem.config import Config
from org_mem.models import LinkRelation, MemoryDraft, MemoryType
from org_mem.service import MemoryService

PROJECT = "golden-proj"


def _base_body(content: str, source: str) -> str:
    return (
        f"* Content\n\n{content}\n\n"
        f"* Sources\n\n- {source}\n\n"
        "* Related memories\n"
    )


def _write(svc: MemoryService, memory_type: MemoryType, title: str, content: str, source: str) -> str:
    resp = svc.memory_write(
        MemoryDraft(
            project_id=PROJECT,
            memory_type=memory_type,
            title=title,
            body=_base_body(content, source),
            evidence=[{"kind": "symbol", "value": source.split(" :: ")[-1]}],
        )
    )
    assert resp["ok"], resp
    return resp["memory_id"]


def _ids(resp: dict) -> list[str]:
    assert resp["ok"], resp
    return [r["memory_id"] for r in resp["results"]]


@pytest.fixture
def svc(memory_root, data_dir, config_path) -> MemoryService:
    return MemoryService(Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path))


def test_exact_symbol_lookup(svc: MemoryService) -> None:
    """A query naming a concrete symbol finds the memory whose Sources cite it."""
    target = _write(svc, MemoryType.INVARIANT, "Owner tag stays at stack bottom",
                    "The owner tag remains at the stack bottom.", "symbol :: path_use_preservation")
    _write(svc, MemoryType.CONVENTION, "Formatting", "Run the formatter.", "command :: uv run ruff")

    assert target in _ids(svc.memory_search(PROJECT, "path_use_preservation"))


def test_supersede_hides_old_from_default_search(svc: MemoryService) -> None:
    """After B supersedes A, current-state search returns B, not A; history keeps A."""
    old = _write(svc, MemoryType.CONVENTION, "Ownership rule v1",
                 "Ownership tag lives in the header.", "symbol :: ownership_tag")
    new = _write(svc, MemoryType.CONVENTION, "Ownership rule v2",
                 "Ownership tag lives at the stack bottom.", "symbol :: ownership_tag")
    resp = svc.memory_link(new, old, relation=LinkRelation.SUPERSEDES, expected_revision=1)
    assert resp["ok"], resp

    current = _ids(svc.memory_search(PROJECT, "ownership"))
    assert new in current
    assert old not in current

    history = _ids(svc.memory_search(PROJECT, "ownership", status="superseded"))
    assert old in history


def test_problem_is_findable_by_symptom(svc: MemoryService) -> None:
    """A diagnostic query surfaces the matching problem memory."""
    body = (
        "* Content\n\nLock ordering inverts under contention.\n\n"
        "* Sources\n\n- test :: test_locking.py\n\n"
        "* Symptoms\n\nDeadlock under concurrent writes.\n\n"
        "* Diagnosis\n\nInverted lock order.\n\n"
        "* Fix\n\nAcquire in canonical order.\n\n"
        "* Prevention\n\nSingle lock helper.\n\n"
        "* Related memories\n"
    )
    resp = svc.memory_write(
        MemoryDraft(project_id=PROJECT, memory_type=MemoryType.PROBLEM, title="Write deadlock",
                    body=body, evidence=[{"kind": "test", "value": "test_locking.py"}])
    )
    assert resp["ok"], resp

    assert resp["memory_id"] in _ids(svc.memory_search(PROJECT, "deadlock"))
