from __future__ import annotations

from typing import Any

from epubgen.errors import OutlineError
from epubgen.llm import create_message
from epubgen.logsetup import get_logger
from epubgen.prompts.description import build_description_messages
from epubgen.prompts.refine import build_refine_messages
from epubgen.schema import RefinedTopic, TopicSuggestions
from epubgen.styles import Style

log = get_logger("refine")


def _extract_tool_input(response: Any) -> dict[str, Any]:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input  # type: ignore[no-any-return]
    raise OutlineError("model returned no tool_use block for refine")


async def refine_topic(
    style: Style, topic: str, *, model: str, hint: str | None = None
) -> TopicSuggestions:
    log.info("refining topic %r for style %s (hint=%r)", topic, style.name, hint)
    payload = build_refine_messages(style, topic, hint=hint)
    resp = await create_message(model=model, max_tokens=1500, **payload)
    raw = _extract_tool_input(resp)
    suggestions = TopicSuggestions.model_validate(raw)
    log.debug("refined: %s", [s.title for s in suggestions.suggestions])
    return suggestions


async def refine_description(
    style: Style,
    topic: str,
    framing: RefinedTopic,
    *,
    model: str,
    hint: str | None = None,
) -> str:
    log.info("drafting description for %r (hint=%r)", framing.title, hint)
    payload = build_description_messages(style, topic, framing, hint=hint)
    resp = await create_message(model=model, max_tokens=1000, **payload)
    raw = _extract_tool_input(resp)
    desc = raw.get("description", "").strip()
    if not desc:
        raise OutlineError("description response missing 'description' field")
    return desc
