from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

from epubgen.anthropic_client import create_message
from epubgen.errors import ApiError
from epubgen.prompts.chapter import build_chapter_messages
from epubgen.schema import Chapter, Options, Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_text, chapter_path


def _extract_text(response: Any) -> str:
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    if not parts:
        raise ApiError("chapter response had no text blocks")
    return "\n".join(parts).strip() + "\n"


async def generate_chapter(
    style: Style, outline: Outline, chapter: Chapter, opts: Options
) -> tuple[str, dict[str, int]]:
    payload = build_chapter_messages(style, outline, chapter, opts)
    resp = await create_message(model=opts.model, max_tokens=8000, **payload)
    text = _extract_text(resp)
    usage = getattr(resp, "usage", None)
    cache_stats = {
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    } if usage else {}
    return text, cache_stats


ProgressFn = Callable[[int, str, dict[str, int] | None], None]


async def generate_all(
    style: Style,
    outline: Outline,
    opts: Options,
    workdir: Path,
    progress: ProgressFn | None = None,
) -> None:
    sem = asyncio.Semaphore(opts.concurrency)

    async def one(ch: Chapter) -> None:
        path = chapter_path(workdir, ch.number)
        if path.exists():
            if progress:
                progress(ch.number, "skip", None)
            return
        if progress:
            progress(ch.number, "start", None)
        async with sem:
            text, stats = await generate_chapter(style, outline, ch, opts)
        atomic_write_text(path, text)
        if progress:
            progress(ch.number, "done", stats)

    await asyncio.gather(*(one(ch) for ch in outline.chapters))
