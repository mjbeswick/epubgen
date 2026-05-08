from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from epubgen.anthropic_client import create_message
from epubgen.errors import ApiError
from epubgen.logsetup import get_logger
from epubgen.prompts.chapter import build_chapter_messages, build_revise_messages
from epubgen.schema import Chapter, Options, Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_text, chapter_path

log = get_logger("chapters")


_CHAPTER_MAX_TOKENS = 16000


def _extract_text(response: Any) -> str:
    parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    if not parts:
        raise ApiError("chapter response had no text blocks")
    if getattr(response, "stop_reason", None) == "max_tokens":
        log.warning(
            "chapter response truncated at max_tokens=%d; chapter may be incomplete",
            _CHAPTER_MAX_TOKENS,
        )
    return "\n".join(parts).strip() + "\n"


async def revise_chapter(
    style: Style,
    outline: Outline,
    chapter: Chapter,
    current_text: str,
    instruction: str,
    opts: Options,
    sources_text: str = "",
) -> tuple[str, dict[str, int]]:
    payload = build_revise_messages(
        style, outline, chapter, current_text, instruction, opts, sources_text=sources_text
    )
    resp = await create_message(model=opts.model, max_tokens=_CHAPTER_MAX_TOKENS, **payload)
    text = _extract_text(resp)
    usage = getattr(resp, "usage", None)
    cache_stats = {
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "input_tokens": getattr(usage, "input_tokens", 0) or 0,
        "output_tokens": getattr(usage, "output_tokens", 0) or 0,
    } if usage else {}
    return text, cache_stats


async def generate_chapter(
    style: Style, outline: Outline, chapter: Chapter, opts: Options, sources_text: str = ""
) -> tuple[str, dict[str, int]]:
    payload = build_chapter_messages(style, outline, chapter, opts, sources_text=sources_text)
    resp = await create_message(model=opts.model, max_tokens=_CHAPTER_MAX_TOKENS, **payload)
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
    sources_text: str = "",
) -> None:
    sem = asyncio.Semaphore(opts.concurrency)

    async def one(ch: Chapter) -> None:
        path = chapter_path(workdir, ch.number)
        if path.exists():
            log.info("ch %02d skip (exists: %s)", ch.number, path.name)
            if progress:
                progress(ch.number, "skip", None, ch.title)
            return
        if progress:
            progress(ch.number, "queued", None, ch.title)
        async with sem:
            log.info("ch %02d running: %r", ch.number, ch.title)
            if progress:
                progress(ch.number, "start", None, ch.title)
            t0 = time.monotonic()
            text, stats = await generate_chapter(style, outline, ch, opts, sources_text=sources_text)
            elapsed = time.monotonic() - t0
            atomic_write_text(path, text)
            log.info(
                "ch %02d done in %.1fs (out_tok=%s cache_read=%s cache_create=%s)",
                ch.number,
                elapsed,
                stats.get("output_tokens"),
                stats.get("cache_read_input_tokens"),
                stats.get("cache_creation_input_tokens"),
            )
            if progress:
                progress(ch.number, "done", stats, ch.title)

    await asyncio.gather(*(one(ch) for ch in outline.chapters))
