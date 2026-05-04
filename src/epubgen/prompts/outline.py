from __future__ import annotations

from typing import Any

from epubgen.schema import Options
from epubgen.styles import Style

OUTLINE_TOOL = {
    "name": "emit_outline",
    "description": "Emit the structured outline for the book.",
    "input_schema": {
        "type": "object",
        "required": ["title", "topic", "style", "chapters"],
        "properties": {
            "title": {"type": "string"},
            "subtitle": {"type": ["string", "null"]},
            "author": {"type": "string"},
            "topic": {"type": "string"},
            "style": {"type": "string"},
            "chapters": {
                "type": "array",
                "minItems": 3,
                "maxItems": 40,
                "items": {
                    "type": "object",
                    "required": ["number", "title", "synopsis", "beats", "word_target"],
                    "properties": {
                        "number": {"type": "integer", "minimum": 1},
                        "title": {"type": "string"},
                        "synopsis": {"type": "string"},
                        "beats": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 12,
                            "items": {
                                "type": "object",
                                "required": ["summary"],
                                "properties": {
                                    "summary": {"type": "string"},
                                    "word_target": {"type": ["integer", "null"]},
                                },
                            },
                        },
                        "code_examples": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 20,
                        },
                        "word_target": {"type": "integer", "minimum": 200},
                    },
                },
            },
        },
    },
}


def build_outline_messages(style: Style, opts: Options) -> dict[str, Any]:
    chapters_clause = (
        f"Aim for exactly {opts.chapters} chapters."
        if opts.chapters
        else "Choose a chapter count appropriate to the topic (typically 8–14)."
    )
    title_clause = ""
    if opts.preferred_title:
        title_clause = (
            f"\nUse exactly this title: {opts.preferred_title!r}.\n"
            f"Use exactly this subtitle: {opts.preferred_subtitle!r}."
            if opts.preferred_subtitle
            else f"\nUse exactly this title: {opts.preferred_title!r}."
        )
    user = (
        f"Topic: {opts.topic}\n"
        f"Style: {style.name}\n"
        f"Target words per chapter: ~{opts.words}\n"
        f"{chapters_clause}"
        f"{title_clause}\n"
        "Each chapter must include 3–8 beats and 0–6 code_examples "
        "(short natural-language descriptions of snippets to include).\n"
        "Use the emit_outline tool to return the outline."
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
                    "You design book outlines. "
                    "Match the voice and structure of the style guide above. "
                    "Return your answer by calling the emit_outline tool — never plain text."
                ),
            },
        ],
        "messages": [{"role": "user", "content": user}],
        "tools": [OUTLINE_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_outline"},
    }


def build_repair_messages(
    style: Style, opts: Options, prior_json: str, error: str
) -> dict[str, Any]:
    base = build_outline_messages(style, opts)
    base["messages"] = [
        {"role": "user", "content": base["messages"][0]["content"]},
        {"role": "assistant", "content": [{"type": "text", "text": prior_json}]},
        {
            "role": "user",
            "content": (
                f"That outline failed validation:\n{error}\n\n"
                "Re-emit a corrected outline using the emit_outline tool."
            ),
        },
    ]
    return base
