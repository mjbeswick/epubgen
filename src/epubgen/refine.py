from __future__ import annotations

from typing import Any

from epubgen.anthropic_client import create_message
from epubgen.errors import OutlineError
from epubgen.logsetup import get_logger
from epubgen.prompts.refine import build_refine_messages
from epubgen.schema import TopicSuggestions
from epubgen.styles import Style

log = get_logger("refine")


def _extract_tool_input(response: Any) -> dict[str, Any]:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return block.input  # type: ignore[no-any-return]
    raise OutlineError("model returned no tool_use block for refine")


async def refine_topic(style: Style, topic: str, *, model: str) -> TopicSuggestions:
    log.info("refining topic %r for style %s", topic, style.name)
    payload = build_refine_messages(style, topic)
    resp = await create_message(model=model, max_tokens=1500, **payload)
    raw = _extract_tool_input(resp)
    suggestions = TopicSuggestions.model_validate(raw)
    log.debug("refined: %s", [s.title for s in suggestions.suggestions])
    return suggestions
