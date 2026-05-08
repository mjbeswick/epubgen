import os
from pathlib import Path

import pytest

from epubgen.errors import FsError
from epubgen.lock import lock_workdir


def test_lock_creates_and_releases(tmp_path: Path):
    wd = tmp_path / "wd"
    with lock_workdir(wd):
        assert (wd / ".lock").exists()
    # Released → file gone.
    assert not (wd / ".lock").exists()


def test_lock_records_pid(tmp_path: Path):
    wd = tmp_path / "wd"
    with lock_workdir(wd):
        recorded = (wd / ".lock").read_text(encoding="utf-8").strip()
        assert recorded == str(os.getpid())


def test_lock_blocks_concurrent_holder(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    import fcntl

    with open(wd / ".lock", "a+", encoding="utf-8") as fp:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with pytest.raises(FsError, match="another epubgen run is using"), lock_workdir(wd):
                pass
        finally:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)


def test_lock_idempotent_after_clean_release(tmp_path: Path):
    wd = tmp_path / "wd"
    with lock_workdir(wd):
        pass
    # Re-acquire — should succeed.
    with lock_workdir(wd):
        pass
