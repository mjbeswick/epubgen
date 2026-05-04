from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from epubgen.anthropic_client import create_message
from epubgen.errors import ApiError, OutlineError
from epubgen.prompts.outline import build_outline_messages, build_repair_messages
from epubgen.schema import Options, Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_text


def _extract_tool_input(response: Any) -> dict[str, Any]:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input  # type: ignore[no-any-return]
    raise OutlineError("model returned no tool_use block")


async def _call_outline(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = await create_message(model=model, max_tokens=4000, **payload)
    return _extract_tool_input(resp)


async def generate_outline(style: Style, opts: Options) -> Outline:
    payload = build_outline_messages(style, opts)
    raw = await _call_outline(opts.model, payload)
    raw["topic"] = opts.topic
    raw["style"] = style.name
    try:
        return Outline.model_validate(raw)
    except ValidationError as first_err:
        repair_payload = build_repair_messages(
            style, opts, json.dumps(raw, indent=2), str(first_err)
        )
        retry_raw = await _call_outline(opts.model, repair_payload)
        retry_raw["topic"] = opts.topic
        retry_raw["style"] = style.name
        try:
            return Outline.model_validate(retry_raw)
        except ValidationError as second_err:
            raise OutlineError(
                f"outline failed validation after one repair: {second_err}"
            ) from second_err


def load_outline(path: Path) -> Outline:
    return Outline.model_validate_json(path.read_text(encoding="utf-8"))


def save_outline(path: Path, outline: Outline) -> None:
    atomic_write_text(path, outline.model_dump_json(indent=2))


async def get_or_generate_outline(
    style: Style, opts: Options, workdir: Path
) -> Outline:
    path = workdir / "outline.json"
    if path.exists():
        return load_outline(path)
    try:
        outline = await generate_outline(style, opts)
    except ApiError:
        raise
    save_outline(path, outline)
    return outline
