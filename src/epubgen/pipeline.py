from __future__ import annotations

import asyncio
from pathlib import Path

from epubgen.assemble import assemble, maybe_make_azw3
from epubgen.chapters import generate_all
from epubgen.cover import existing_cover, generate_cover
from epubgen.diagrams import render_all
from epubgen.logsetup import get_logger
from epubgen.outline import get_or_generate_outline
from epubgen.progress import figure_progress, phase, progress
from epubgen.prompts.cover import build_cover_image_prompt
from epubgen.schema import Options
from epubgen.styles import load_style
from epubgen.workdir import chapter_path, ensure_workdir, freeze_options

log = get_logger("pipeline")


async def run_async(opts: Options) -> Path:
    log.info("loading style %s", opts.style)
    style = load_style(opts.style)
    workdir = ensure_workdir(opts.workdir)
    log.info("workdir: %s", workdir)
    freeze_options(workdir, opts.freeze_dict(), force=opts.force)

    outline_path = workdir / "outline.json"
    if outline_path.exists():
        outline = await get_or_generate_outline(style, opts, workdir)
        log.info("outline (cached): %d chapters — %r", len(outline.chapters), outline.title)
    else:
        with phase("Generating outline"):
            outline = await get_or_generate_outline(style, opts, workdir)
        log.info("outline: %d chapters — %r", len(outline.chapters), outline.title)

    log.info("generating chapters (concurrency=%d)", opts.concurrency)
    with progress(total=len(outline.chapters)) as p:
        await generate_all(style, outline, opts, workdir, progress=p.update)

    if not opts.no_diagrams:
        chapter_files = [chapter_path(workdir, ch.number) for ch in outline.chapters]
        fmt = "png" if opts.kindle else "svg"
        skip = frozenset({"image"}) if opts.no_images else frozenset()
        # Count blocks first so we can show a real progress bar.
        from epubgen.diagrams import _find_blocks, render_in_file

        total = sum(
            sum(1 for b in _find_blocks(p.read_text(encoding="utf-8")) if b[2] not in skip)
            for p in chapter_files
        )
        if total:
            with figure_progress(total=total, label="figures") as bar:
                rendered = 0
                for cp in chapter_files:
                    rendered += render_in_file(cp, workdir, fmt=fmt, skip_kinds=skip)
                    bar.advance(note=cp.name)
                if rendered:
                    log.info("rendered %d figure(s) total", rendered)
        else:
            # Still call render_all so logs are consistent if any blocks slipped through.
            render_all(chapter_files, workdir, fmt=fmt, skip_kinds=skip)

    cover_path: Path | None = None
    if not opts.no_cover:
        cover_path = existing_cover(workdir)
        if cover_path is None:
            prompt = build_cover_image_prompt(style, outline, opts.cover_prompt)
            with phase("Generating cover"):
                cover_path = generate_cover(outline, style, workdir, prompt=prompt)
        else:
            log.info("reusing existing cover: %s", cover_path)

    with phase(f"Assembling EPUB → {opts.out}"):
        epub = assemble(
            outline=outline, style=style, opts=opts, workdir=workdir, cover=cover_path
        )
    if opts.kindle:
        with phase("Converting to AZW3"):
            azw3 = maybe_make_azw3(epub)
        if azw3:
            log.info("emitted azw3: %s", azw3)
        else:
            log.info("kindlepreviewer not available; skipped azw3")
    return epub


def run(opts: Options) -> Path:
    return asyncio.run(run_async(opts))
