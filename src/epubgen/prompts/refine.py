from __future__ import annotations

from typing import Any

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


def build_refine_messages(style: Style, topic: str) -> dict[str, Any]:
    user = (
        f"Topic from the user: {topic!r}\n\n"
        "Propose three distinct framings for a book on this topic, in the voice of the "
        f"{style.name} style above. For each, give:\n"
        "- title: a strong book title (≤8 words preferred)\n"
        "- subtitle: a clarifying subtitle (one phrase)\n"
        "- angle: one sentence on what makes this framing different from the others.\n\n"
        "Make the three meaningfully different in scope or stance — not three rewordings "
        "of the same idea. Use the emit_titles tool."
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
                    "Return your answer by calling the emit_titles tool — never plain text."
                ),
            },
        ],
        "messages": [{"role": "user", "content": user}],
        "tools": [REFINE_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_titles"},
    }
