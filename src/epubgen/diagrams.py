from __future__ import annotations

import contextlib
import re
import shutil
import subprocess
from pathlib import Path

from epubgen.logsetup import get_logger
from epubgen.workdir import atomic_write_text

log = get_logger("diagrams")

_MERMAID_FENCE = re.compile(
    r"^```mermaid\s*\n(.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)


def has_mmdc() -> bool:
    return shutil.which("mmdc") is not None


def _render_one(src: str, out_path: Path) -> bool:
    src_file = out_path.with_suffix(".mmd")
    atomic_write_text(src_file, src)
    args = [
        "mmdc",
        "-i", str(src_file),
        "-o", str(out_path),
        "-b", "transparent",
        "--quiet",
    ]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        log.warning("mmdc unavailable or timed out: %s", e)
        return False
    finally:
        with contextlib.suppress(OSError):
            src_file.unlink()
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-5:]
        log.warning("mmdc failed (rc=%d): %s", result.returncode, " | ".join(tail))
        return False
    return out_path.exists()


def render_in_file(chapter_path: Path, workdir: Path, *, fmt: str = "svg") -> int:
    """Replace ```mermaid blocks in chapter_path with image refs.

    Renders each block to <workdir>/diagrams/ch-NN-DD.<fmt>. Returns count rendered.
    Leaves blocks intact on failure (still readable as code).
    """
    text = chapter_path.read_text(encoding="utf-8")
    matches = list(_MERMAID_FENCE.finditer(text))
    if not matches:
        return 0
    if not has_mmdc():
        log.info("mmdc not on PATH; %d mermaid block(s) in %s left as code",
                 len(matches), chapter_path.name)
        return 0

    diag_dir = workdir / "diagrams"
    diag_dir.mkdir(parents=True, exist_ok=True)
    stem = chapter_path.stem  # ch-NN

    rendered = 0
    new_text = text
    # Iterate in reverse so byte offsets stay valid as we splice.
    for idx, m in enumerate(reversed(matches), start=1):
        diag_idx = len(matches) - idx + 1
        out_path = diag_dir / f"{stem}-{diag_idx:02d}.{fmt}"
        src = m.group(1)
        if out_path.exists() or _render_one(src, out_path):
            rendered += 1
            rel = out_path.relative_to(workdir)
            replacement = f"![Diagram]({rel})"
            new_text = new_text[: m.start()] + replacement + new_text[m.end():]

    if rendered:
        atomic_write_text(chapter_path, new_text)
        log.info("rendered %d diagram(s) in %s", rendered, chapter_path.name)
    return rendered


def render_all(chapter_paths: list[Path], workdir: Path, *, fmt: str = "svg") -> int:
    total = 0
    for p in chapter_paths:
        total += render_in_file(p, workdir, fmt=fmt)
    return total
