"""Crash-safe writes, readback verification, backups and advisory locks."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


class StateBusyError(TimeoutError):
    pass


class StateWriteError(OSError):
    pass


@contextmanager
def advisory_lock(path: Path, timeout: float = 2.0) -> Iterator[None]:
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    deadline = time.monotonic() + max(0.0, timeout)
    try:
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise StateBusyError(f"State is busy: {path}") from exc
                time.sleep(0.02)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def atomic_write_bytes(path: Path, content: bytes, *, mode: int = 0o600, keep_backup: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp_name = ""
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temp_name = handle.name
            os.chmod(temp_name, mode)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp_path = Path(temp_name)
        if keep_backup and path.exists():
            backup = path.with_suffix(path.suffix + ".lkg")
            backup.write_bytes(path.read_bytes())
            os.chmod(backup, mode)
        os.replace(temp_path, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        if path.read_bytes() != content:
            raise StateWriteError(f"Readback verification failed: {path}")
    except OSError as exc:
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)
        if isinstance(exc, StateWriteError):
            raise
        raise StateWriteError(str(exc)) from exc


def atomic_write_text(path: Path, content: str, **kwargs: Any) -> None:
    atomic_write_bytes(path, content.encode("utf-8"), **kwargs)


def atomic_write_json(path: Path, payload: Any, **kwargs: Any) -> None:
    encoded = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
    atomic_write_bytes(path, encoded, **kwargs)
