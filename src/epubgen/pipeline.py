from __future__ import annotations

import asyncio
from pathlib import Path

from epubgen.assemble import assemble, maybe_make_azw3
from epubgen.chapters import generate_all
from epubgen.cover import existing_cover, generate_cover
from epubgen.logsetup import get_logger
from epubgen.outline import get_or_generate_outline
from epubgen.progress import progress
from epubgen.prompts.cover import build_cover_image_prompt
from epubgen.schema import Options
from epubgen.styles import load_style
from epubgen.workdir import ensure_workdir, freeze_options

log = get_logger("pipeline")


async def run_async(opts: Options) -> Path:
    log.info("loading style %s", opts.style)
    style = load_style(opts.style)
    workdir = ensure_workdir(opts.workdir)
    log.info("workdir: %s", workdir)
    freeze_options(workdir, opts.freeze_dict(), force=opts.force)

    log.info("resolving outline (cached if present)")
    outline = await get_or_generate_outline(style, opts, workdir)
    log.info("outline: %d chapters — %r", len(outline.chapters), outline.title)

    log.info("generating chapters (concurrency=%d)", opts.concurrency)
    with progress(total=len(outline.chapters)) as p:
        await generate_all(style, outline, opts, workdir, progress=p.update)

    cover_path: Path | None = None
    if not opts.no_cover:
        cover_path = existing_cover(workdir)
        if cover_path is None:
            prompt = build_cover_image_prompt(style, outline, opts.cover_prompt)
            log.info("generating cover")
            cover_path = generate_cover(outline, style, workdir, prompt=prompt)
        else:
            log.info("reusing existing cover: %s", cover_path)

    log.info("assembling epub via pandoc → %s", opts.out)
    epub = assemble(
        outline=outline, style=style, opts=opts, workdir=workdir, cover=cover_path
    )
    if opts.kindle:
        azw3 = maybe_make_azw3(epub)
        if azw3:
            log.info("emitted azw3: %s", azw3)
        else:
            log.info("kindlepreviewer not available; skipped azw3")
    return epub


def run(opts: Options) -> Path:
    return asyncio.run(run_async(opts))
