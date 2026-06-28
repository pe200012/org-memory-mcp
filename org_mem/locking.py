"""Cross-process state locking and atomic text replacement.

This module provides the small synchronization layer shared by canonical Org
storage, the project registry, and SQLite index rebuilds.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import TracebackType
from typing import IO

import fcntl

from org_mem.config import Config


def state_lock_path(config: Config) -> Path:
    """Return the shared lock path for all mutable org-mem state."""
    return config.data_dir / "org-mem.lock"


class FileLock:
    """Advisory exclusive file lock shared by independent server processes."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._file: IO[str] | None = None

    def acquire(self) -> None:
        """Acquire the exclusive advisory lock, blocking until available."""
        if self._file is not None:
            return
        self._path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = self._path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except BaseException:
            lock_file.close()
            raise
        self._file = lock_file

    def release(self) -> None:
        """Release the advisory lock."""
        if self._file is None:
            return
        lock_file = self._file
        self._file = None
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        finally:
            lock_file.close()

    def __enter__(self) -> FileLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.release()


def atomic_write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    """Write text through a same-directory temporary file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        _fsync_directory(path.parent)
    except BaseException:
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _fsync_directory(path: Path) -> None:
    """Flush a directory entry after an atomic replacement."""
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
