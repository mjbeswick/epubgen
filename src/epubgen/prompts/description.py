from __future__ import annotations

from typing import Any

from epubgen.prompts._shared import ANTI_ATTRIBUTION
from epubgen.schema import RefinedTopic
from epubgen.styles import Style

DESCRIPTION_TOOL = {
    "name": "emit_description",
    "description": "Emit a back-cover description for the book.",
    "input_schema": {
        "type": "object",
        "required": ["description"],
        "properties": {
            "description": {"type": "string", "minLength": 80, "maxLength": 1200},
        },
    },
}


def build_description_messages(
    style: Style, topic: str, framing: RefinedTopic, hint: str | None = None
) -> dict[str, Any]:
    hint_clause = (
        f"\n\nAdditional steering from the user: {hint!r}" if hint else ""
    )
    user = (
        f"Book topic: {topic!r}\n"
        f"Title: {framing.title}\n"
        f"Subtitle: {framing.subtitle}\n"
        f"Editorial angle: {framing.angle}\n\n"
        "Write a back-cover description for this book in the voice of the style above. "
        "Two short paragraphs, ~100–160 words total. "
        "First paragraph: who this book is for and the problem it solves. "
        "Second paragraph: what the reader will be able to do by the end. "
        "No bullet lists. No marketing puffery. Concrete, specific, useful. "
        f"Use the emit_description tool.{hint_clause}"
    )
    return {
        "system": [
            {
                "type": "text",
                "text": style.guide,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": (
                    "You write back-cover descriptions for technical books. "
                    "Return your answer by calling the emit_description tool "
                    "— never plain text.\n\n"
                    + ANTI_ATTRIBUTION
                ),
            },
        ],
        "messages": [{"role": "user", "content": user}],
        "tools": [DESCRIPTION_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_description"},
    }
