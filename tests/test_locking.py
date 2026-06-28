"""Tests for cross-process file locking and atomic writes."""

from __future__ import annotations

import multiprocessing
import threading
import time
from pathlib import Path

from org_mem.config import Config
from org_mem.locking import FileLock, atomic_write_text, state_lock_path


def _hold_lock(config: Config, ready: multiprocessing.Event, release: multiprocessing.Event) -> None:
    lock = FileLock(state_lock_path(config))
    with lock:
        ready.set()
        release.wait(timeout=5)


def test_file_lock_blocks_other_processes(memory_root, data_dir, config_path) -> None:
    config = Config(memory_root=memory_root, data_dir=data_dir, config_path=config_path)
    ready = multiprocessing.Event()
    release = multiprocessing.Event()
    holder = multiprocessing.Process(target=_hold_lock, args=(config, ready, release))
    holder.start()
    try:
        assert ready.wait(timeout=5)
        started = time.monotonic()
        timer = threading.Timer(0.2, release.set)
        timer.start()

        with FileLock(state_lock_path(config)):
            elapsed = time.monotonic() - started

        timer.cancel()
        assert elapsed >= 0.15
    finally:
        release.set()
        holder.join(timeout=5)
        assert holder.exitcode == 0


def test_atomic_write_text_preserves_previous_content_when_replace_fails(tmp_path, monkeypatch) -> None:
    path = tmp_path / "memory.org"
    path.write_text("old", encoding="utf-8")

    def fail_replace(src: str | bytes | Path, dst: str | bytes | Path) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("org_mem.locking.os.replace", fail_replace)

    try:
        atomic_write_text(path, "new")
    except OSError:
        pass
    else:
        raise AssertionError("failed replace should surface")

    assert path.read_text(encoding="utf-8") == "old"
