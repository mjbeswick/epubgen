from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from epubgen.logsetup import get_logger
from epubgen.workdir import atomic_write_bytes, atomic_write_text

log = get_logger("diagrams")

_MERMAID_FENCE = re.compile(
    r"^```mermaid\s*\n(.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)
_VEGALITE_FENCE = re.compile(
    r"^```(?:vegalite|vega-lite)\s*\n(.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)


def has_mmdc() -> bool:
    return shutil.which("mmdc") is not None


def has_vl_convert() -> bool:
    try:
        import vl_convert  # noqa: F401
    except ImportError:
        return False
    return True


def _render_mermaid(src: str, out_path: Path) -> bool:
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


def _render_vegalite(src: str, out_path: Path) -> bool:
    try:
        import vl_convert as vlc
    except ImportError:
        log.warning("vl-convert not installed; skipping chart")
        return False
    try:
        spec = json.loads(src)
    except json.JSONDecodeError as e:
        log.warning("vegalite block has invalid JSON: %s", e)
        return False
    try:
        if out_path.suffix == ".png":
            data = vlc.vegalite_to_png(spec, scale=2.0)
            atomic_write_bytes(out_path, data)
        else:
            svg = vlc.vegalite_to_svg(spec)
            atomic_write_text(out_path, svg)
    except Exception as e:
        log.warning("vl-convert failed: %s", e)
        return False
    return True


def _find_blocks(text: str) -> list[tuple[int, int, str, str]]:
    """Return (start, end, kind, src) for every fenced figure block, in source order."""
    blocks: list[tuple[int, int, str, str]] = []
    for m in _MERMAID_FENCE.finditer(text):
        blocks.append((m.start(), m.end(), "mermaid", m.group(1)))
    for m in _VEGALITE_FENCE.finditer(text):
        blocks.append((m.start(), m.end(), "vegalite", m.group(1)))
    blocks.sort(key=lambda b: b[0])
    return blocks


def _render_for_kind(kind: str, src: str, out_path: Path) -> bool:
    if kind == "mermaid":
        return _render_mermaid(src, out_path)
    if kind == "vegalite":
        return _render_vegalite(src, out_path)
    return False


def _kind_available(kind: str) -> bool:
    if kind == "mermaid":
        return has_mmdc()
    if kind == "vegalite":
        return has_vl_convert()
    return False


def render_in_file(chapter_path: Path, workdir: Path, *, fmt: str = "svg") -> int:
    """Replace fenced figure blocks (mermaid + vegalite) in chapter_path with image refs.

    Renders each to <workdir>/diagrams/ch-NN-DD.<fmt>. Returns count rendered.
    Leaves blocks intact on failure (still readable as code).
    """
    text = chapter_path.read_text(encoding="utf-8")
    blocks = _find_blocks(text)
    if not blocks:
        return 0

    diag_dir = workdir / "diagrams"
    diag_dir.mkdir(parents=True, exist_ok=True)
    stem = chapter_path.stem  # ch-NN

    rendered = 0
    new_parts: list[str] = []
    cursor = 0
    for idx, (start, end, kind, src) in enumerate(blocks, start=1):
        new_parts.append(text[cursor:start])
        if not _kind_available(kind):
            log.info("%s unavailable; leaving %s block intact in %s", kind, kind, chapter_path.name)
            new_parts.append(text[start:end])
        else:
            out_path = diag_dir / f"{stem}-{idx:02d}.{fmt}"
            ok = out_path.exists() or _render_for_kind(kind, src, out_path)
            if ok:
                rendered += 1
                rel = out_path.relative_to(workdir)
                alt = "Diagram" if kind == "mermaid" else "Chart"
                new_parts.append(f"![{alt}]({rel})")
            else:
                new_parts.append(text[start:end])
        cursor = end
    new_parts.append(text[cursor:])

    if rendered:
        atomic_write_text(chapter_path, "".join(new_parts))
        log.info("rendered %d figure(s) in %s", rendered, chapter_path.name)
    return rendered


def render_all(chapter_paths: list[Path], workdir: Path, *, fmt: str = "svg") -> int:
    total = 0
    for p in chapter_paths:
        total += render_in_file(p, workdir, fmt=fmt)
    return total
