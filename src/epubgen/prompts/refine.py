from __future__ import annotations

from typing import Any

from epubgen.prompts._shared import ANTI_ATTRIBUTION
from epubgen.styles import Style

REFINE_TOOL = {
    "name": "emit_titles",
    "description": "Emit three distinct framings for the book.",
    "input_schema": {
        "type": "object",
        "required": ["suggestions"],
        "properties": {
            "suggestions": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": {
                    "type": "object",
                    "required": ["title", "subtitle", "angle"],
                    "properties": {
                        "title": {"type": "string"},
                        "subtitle": {"type": "string"},
                        "angle": {"type": "string"},
                    },
                },
            }
        },
    },
}


def build_refine_messages(style: Style, topic: str, hint: str | None = None) -> dict[str, Any]:
    hint_clause = (
        f"\n\nAdditional steering from the user (apply to all three): {hint!r}"
        if hint
        else ""
    )
    user = (
        f"Topic from the user: {topic!r}\n\n"
        "Propose three distinct framings for a book on this topic, in the voice of the "
        f"{style.name} style above. For each, give:\n"
        "- title: a strong book title (≤8 words, ≤60 chars).\n"
        "- subtitle: a clarifying subtitle (one phrase, ≤90 chars).\n"
        "- angle: ONE short sentence (≤140 chars) on what makes this framing distinct.\n\n"
        "Be terse. Make the three meaningfully different in scope or stance — not three "
        f"rewordings of the same idea. Use the emit_titles tool.{hint_clause}"
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
                    "You help authors find the right framing for a book. "
                    "Return your answer by calling the emit_titles tool — never plain text.\n\n"
                    + ANTI_ATTRIBUTION
                ),
            },
        ],
        "messages": [{"role": "user", "content": user}],
        "tools": [REFINE_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_titles"},
    }
