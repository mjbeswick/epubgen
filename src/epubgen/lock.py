"""Exclusive workdir file lock so two epubgen runs can't race on the same dir."""

from __future__ import annotations

import contextlib
import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from epubgen.errors import FsError


def _read_lock_pid(path: Path) -> int | None:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


@contextmanager
def lock_workdir(workdir: Path) -> Iterator[None]:
    """Acquire an exclusive flock on <workdir>/.lock for the duration of the block.

    Raises FsError if the lock is already held (likely by another epubgen process).
    Records the holding PID in the lock file for diagnostics.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    lock_path = workdir / ".lock"
    fp = open(lock_path, "a+", encoding="utf-8")  # noqa: SIM115 — explicit lifetime control
    try:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as e:
            fp.close()
            other = _read_lock_pid(lock_path)
            who = f" (held by PID {other})" if other else ""
            raise FsError(
                f"another epubgen run is using {workdir}{who}; "
                "wait for it to finish or pick a different --out"
            ) from e
        fp.seek(0)
        fp.truncate()
        fp.write(f"{os.getpid()}\n")
        fp.flush()
        try:
            yield
        finally:
            with contextlib.suppress(OSError):
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            fp.close()
            with contextlib.suppress(OSError):
                lock_path.unlink()
    except Exception:
        with contextlib.suppress(Exception):
            fp.close()
        raise
