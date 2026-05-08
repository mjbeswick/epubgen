"""High-level amend orchestration. Wraps the pure mutators in `amend.py`
with diagram rendering, cover handling, and EPUB reassembly.
"""

from __future__ import annotations

from pathlib import Path

from epubgen import amend
from epubgen.assemble import assemble, maybe_make_azw3
from epubgen.cover import existing_cover, generate_cover
from epubgen.diagrams import render_all
from epubgen.errors import FsError
from epubgen.lock import lock_workdir
from epubgen.logsetup import get_logger
from epubgen.progress import phase
from epubgen.prompts.cover import build_cover_image_prompt
from epubgen.schema import Options, Outline
from epubgen.styles import load_style
from epubgen.workdir import chapter_path, slugify

log = get_logger("amend_pipeline")


def _resolve_out(out: Path | None, outline: Outline) -> Path:
    return out or Path(f"./{slugify(outline.title)}.epub")


def _opts_from_frozen(frozen: dict, *, workdir: Path, out: Path) -> Options:
    # Defensive: drop keys Options doesn't know about so older workdirs still load.
    allowed = set(Options.model_fields.keys())
    return Options(out=out, workdir=workdir, **{k: v for k, v in frozen.items() if k in allowed})


def rebuild(workdir: Path, *, out: Path | None = None, regen_cover: bool = False) -> Path:
    """Re-render figures, ensure a cover, and reassemble the EPUB.

    No API calls unless `regen_cover` is True (and even then only if the
    cover provider needs one). Used by `epubgen amend rebuild` and by all
    other amend ops as their final step.
    """
    outline, frozen = amend.load_workdir(workdir)
    out_path = _resolve_out(out, outline)
    opts = _opts_from_frozen(frozen, workdir=workdir, out=out_path)
    style = load_style(outline.style)

    with lock_workdir(workdir):
        # Validate invariant before doing anything destructive.
        chapter_files = [chapter_path(workdir, ch.number) for ch in outline.chapters]
        missing = [str(p) for p in chapter_files if not p.exists()]
        if missing:
            raise FsError(f"missing chapter files: {missing}")

        # Re-render any figures that don't have rendered counterparts. The
        # diagram pipeline is idempotent — already-rendered files are skipped.
        if not opts.no_diagrams:
            skip = frozenset({"image"}) if opts.no_images else frozenset()
            render_all(chapter_files, workdir, fmt="svg", skip_kinds=skip)

        cover_path = existing_cover(workdir)
        if regen_cover or cover_path is None:
            if regen_cover and cover_path is not None:
                amend.archive(workdir, cover_path)
                cover_path = None
            if not opts.no_cover:
                prompt = build_cover_image_prompt(style, outline, opts.cover_prompt)
                with phase("Generating cover"):
                    cover_path = generate_cover(outline, style, workdir, prompt=prompt)

        with phase(f"Assembling EPUB → {opts.out}"):
            epub = assemble(
                outline=outline, style=style, opts=opts, workdir=workdir, cover=cover_path
            )
        if opts.ereader:
            azw3 = maybe_make_azw3(epub)
            if azw3:
                log.info("emitted azw3: %s", azw3)
        return epub
