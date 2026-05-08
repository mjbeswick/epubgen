from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path
from typing import Any

from epubgen.errors import FsError


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower())
    return s.strip("-") or "book"


def default_workdir(out: Path) -> Path:
    return out.with_suffix(out.suffix + ".work") if out.suffix else Path(str(out) + ".work")


def ensure_workdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError as e:
        raise FsError(f"failed to write {path}: {e}") from e
    finally:
        if tmp.exists():
            with contextlib.suppress(OSError):
                tmp.unlink()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except OSError as e:
        raise FsError(f"failed to write {path}: {e}") from e


def freeze_options(workdir: Path, frozen: dict[str, Any], *, force: bool) -> None:
    path = workdir / "options.json"
    if path.exists():
        existing = json.loads(path.read_text())
        # Backfill keys added in later schema versions whose new default is "empty"
        # (None / [] / {}). Older workdirs predate these keys and would otherwise
        # always mismatch.
        for k, v in frozen.items():
            if k not in existing and v in (None, [], {}):
                existing[k] = v
        if existing != frozen and not force:
            diffs = [k for k in set(existing) | set(frozen) if existing.get(k) != frozen.get(k)]
            raise FsError(
                f"options.json mismatch in {workdir} (changed: {sorted(diffs)}); "
                "pass --force to override"
            )
    atomic_write_text(path, json.dumps(frozen, indent=2, sort_keys=True))


def chapter_path(workdir: Path, n: int) -> Path:
    return workdir / f"ch-{n:02d}.md"
