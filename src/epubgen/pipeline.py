from __future__ import annotations

import asyncio
from pathlib import Path

from epubgen.assemble import assemble, maybe_make_azw3
from epubgen.chapters import generate_all
from epubgen.cover import existing_cover, generate_cover
from epubgen.outline import get_or_generate_outline
from epubgen.progress import progress
from epubgen.prompts.cover import build_cover_image_prompt
from epubgen.schema import Options
from epubgen.styles import load_style
from epubgen.workdir import ensure_workdir, freeze_options


async def run_async(opts: Options) -> Path:
    style = load_style(opts.style)
    workdir = ensure_workdir(opts.workdir)
    freeze_options(workdir, opts.freeze_dict(), force=opts.force)

    outline = await get_or_generate_outline(style, opts, workdir)

    with progress(total=len(outline.chapters)) as p:
        await generate_all(style, outline, opts, workdir, progress=p.update)

    cover_path: Path | None = None
    if not opts.no_cover:
        cover_path = existing_cover(workdir)
        if cover_path is None:
            prompt = build_cover_image_prompt(style, outline, opts.cover_prompt)
            cover_path = generate_cover(outline, style, workdir, prompt=prompt)

    epub = assemble(
        outline=outline, style=style, opts=opts, workdir=workdir, cover=cover_path
    )
    if opts.kindle:
        maybe_make_azw3(epub)
    return epub


def run(opts: Options) -> Path:
    return asyncio.run(run_async(opts))
