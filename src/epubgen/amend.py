"""Edit an existing book workdir in place.

The workdir is the source of truth: outline.json + ch-NN.md + options.json +
cover.{png,svg}. Amend operations mutate those files (with backups) then
reassembly produces a fresh .epub.
"""

from __future__ import annotations

import json
import shutil
import time
from collections.abc import Iterable
from pathlib import Path

from epubgen.errors import ConfigError, FsError
from epubgen.logsetup import get_logger
from epubgen.outline import load_outline, save_outline
from epubgen.schema import Chapter, Outline
from epubgen.workdir import atomic_write_text, chapter_path

log = get_logger("amend")


# ---------- workdir loading ----------

def load_workdir(workdir: Path) -> tuple[Outline, dict]:
    """Return (outline, frozen options dict). Raises FsError if either missing."""
    if not (workdir / "outline.json").exists():
        raise FsError(f"no outline.json in {workdir}")
    if not (workdir / "options.json").exists():
        raise FsError(f"no options.json in {workdir}")
    outline = load_outline(workdir / "outline.json")
    frozen = json.loads((workdir / "options.json").read_text())
    return outline, frozen


# ---------- archive (backup) ----------

def _archive_dir(workdir: Path) -> Path:
    p = workdir / ".archive"
    p.mkdir(exist_ok=True)
    return p


def archive(workdir: Path, src: Path) -> Path:
    """Move `src` into <workdir>/.archive/ with a timestamp suffix. Idempotent."""
    if not src.exists():
        return src
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = _archive_dir(workdir) / f"{src.stem}-{ts}{src.suffix}"
    shutil.move(str(src), dest)
    log.info("archived %s → %s", src.name, dest)
    return dest


# ---------- chapter file renumbering ----------

_TMP_SUFFIX = ".amend-tmp"


def _renumber_files(workdir: Path, mapping: dict[int, int]) -> None:
    """Rename ch-NN.md files according to mapping {old: new}.

    Two-phase to handle any permutation safely: rename sources to a sentinel
    name, then rename sentinels to final names. Skips no-op entries.
    """
    moves = [(old, new) for old, new in mapping.items() if old != new]
    if not moves:
        return
    # Phase 1 — to temp.
    for old, _ in moves:
        src = chapter_path(workdir, old)
        if not src.exists():
            raise FsError(f"cannot renumber: missing {src.name}")
        tmp = src.with_suffix(src.suffix + _TMP_SUFFIX)
        src.rename(tmp)
    # Phase 2 — temp to final.
    for old, new in moves:
        src = chapter_path(workdir, old)  # path object, not the file
        tmp = src.with_suffix(src.suffix + _TMP_SUFFIX)
        dest = chapter_path(workdir, new)
        if dest.exists():
            raise FsError(f"renumber clash: {dest.name} already exists")
        tmp.rename(dest)
    log.info("renumbered %d chapter file(s): %s", len(moves), moves)


def _apply_chapter_numbers(outline: Outline, mapping: dict[int, int]) -> Outline:
    """Return a new Outline with chapter.number remapped per `mapping`. Other
    chapters keep their existing numbers."""
    new_chapters = [
        ch.model_copy(update={"number": mapping.get(ch.number, ch.number)})
        for ch in outline.chapters
    ]
    return outline.model_copy(update={"chapters": new_chapters})


def _sort_and_validate(outline: Outline, workdir: Path) -> Outline:
    """Sort chapters by number, assert invariants, return."""
    sorted_chs = sorted(outline.chapters, key=lambda c: c.number)
    out = outline.model_copy(update={"chapters": sorted_chs})
    seen: set[int] = set()
    for i, ch in enumerate(out.chapters, start=1):
        if ch.number != i:
            raise FsError(
                f"chapter numbering invariant broken at index {i}: "
                f"got number={ch.number}, expected {i}"
            )
        if ch.number in seen:
            raise FsError(f"duplicate chapter number {ch.number}")
        seen.add(ch.number)
        if not chapter_path(workdir, ch.number).exists():
            raise FsError(f"missing file for chapter {ch.number}")
    return out


def renormalize(workdir: Path, outline: Outline) -> Outline:
    """Renumber outline + files so chapters[i].number == i+1. Idempotent."""
    target = {ch.number: i + 1 for i, ch in enumerate(
        sorted(outline.chapters, key=lambda c: c.number)
    )}
    if all(old == new for old, new in target.items()):
        return _sort_and_validate(outline, workdir)
    _renumber_files(workdir, target)
    new_outline = _apply_chapter_numbers(outline, target)
    return _sort_and_validate(new_outline, workdir)


# ---------- mutating operations (no API calls) ----------

def remove_chapter(workdir: Path, outline: Outline, n: int) -> Outline:
    """Remove chapter N. Archives its file and renormalizes."""
    if not any(ch.number == n for ch in outline.chapters):
        raise ConfigError(f"chapter {n} not found")
    archive(workdir, chapter_path(workdir, n))
    new_chapters = [ch for ch in outline.chapters if ch.number != n]
    new_outline = outline.model_copy(update={"chapters": new_chapters})
    return renormalize(workdir, new_outline)


def reorder_chapter(workdir: Path, outline: Outline, frm: int, to: int) -> Outline:
    """Move chapter FROM to position TO (1-indexed)."""
    chs = sorted(outline.chapters, key=lambda c: c.number)
    if not (1 <= frm <= len(chs) and 1 <= to <= len(chs)):
        raise ConfigError(
            f"reorder out of range: frm={frm} to={to}, have {len(chs)} chapters"
        )
    if frm == to:
        return outline
    moving = next(c for c in chs if c.number == frm)
    rest = [c for c in chs if c.number != frm]
    rest.insert(to - 1, moving)
    # `rest` is the desired final order. Map each chapter's current number
    # to its 1-indexed position in that order, then do a single renumber pass.
    mapping = {c.number: i + 1 for i, c in enumerate(rest)}
    _renumber_files(workdir, mapping)
    new_chapters = [c.model_copy(update={"number": mapping[c.number]}) for c in rest]
    final = outline.model_copy(update={"chapters": new_chapters})
    return _sort_and_validate(final, workdir)


def insert_chapter(
    workdir: Path, outline: Outline, position: int, chapter: Chapter
) -> Outline:
    """Insert `chapter` at 1-indexed `position`. Renumbers subsequent chapters.

    Caller is responsible for writing the chapter's content file at the
    correct ch-NN.md path (this function reserves the slot via renumbering
    but does not generate content).
    """
    chs = sorted(outline.chapters, key=lambda c: c.number)
    if not (1 <= position <= len(chs) + 1):
        raise ConfigError(
            f"insert position {position} out of range (1..{len(chs) + 1})"
        )
    # Shift existing chapters at `position` and beyond by +1, in reverse order.
    to_shift = [c for c in chs if c.number >= position]
    mapping = {c.number: c.number + 1 for c in to_shift}
    _renumber_files(workdir, mapping)
    shifted = [
        c.model_copy(update={"number": mapping.get(c.number, c.number)}) for c in chs
    ]
    new_ch = chapter.model_copy(update={"number": position})
    chs_out = sorted([*shifted, new_ch], key=lambda c: c.number)
    return outline.model_copy(update={"chapters": chs_out})


def retitle(
    outline: Outline, *, title: str | None = None, subtitle: str | None | type = ...,
) -> Outline:
    """Update title and/or subtitle. Pass `subtitle=None` to clear it; omit to keep."""
    update: dict = {}
    if title is not None:
        update["title"] = title
    if subtitle is not ...:
        update["subtitle"] = subtitle
    if not update:
        return outline
    return outline.model_copy(update=update)


def archive_chapter_for_rewrite(workdir: Path, n: int) -> Path:
    """Move ch-NN.md to .archive/ so a fresh generation can write it."""
    return archive(workdir, chapter_path(workdir, n))


# ---------- save ----------

def save(workdir: Path, outline: Outline, *, frozen: dict | None = None) -> None:
    save_outline(workdir / "outline.json", outline)
    if frozen is not None:
        atomic_write_text(workdir / "options.json", json.dumps(frozen, indent=2, sort_keys=True))


# ---------- rebuild (assemble only, no API) ----------

def chapter_files(workdir: Path, outline: Outline) -> Iterable[Path]:
    return (chapter_path(workdir, ch.number) for ch in outline.chapters)
