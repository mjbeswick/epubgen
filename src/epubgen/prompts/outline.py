from __future__ import annotations

from typing import Any

from epubgen.prompts._shared import ANTI_ATTRIBUTION
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
                        "tables": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 10,
                        },
                        "diagrams": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 10,
                        },
                        "charts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 10,
                        },
                        "images": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 4,
                        },
                        "word_target": {"type": "integer", "minimum": 200},
                    },
                },
            },
        },
    },
}


def build_outline_messages(
    style: Style, opts: Options, hint: str | None = None
) -> dict[str, Any]:
    chapters_clause = (
        f"Aim for exactly {opts.chapters} chapters."
        if opts.chapters
        else (
            "Choose the chapter COUNT yourself based on the topic's natural breadth "
            "and the style's typical book length — anywhere from 6 to 16 chapters."
        )
    )
    words_clause = (
        f"Target words per chapter: ~{opts.words}."
        if opts.words
        else (
            "Set each chapter's word_target based on its actual depth — a short framing "
            "or summary chapter may be 1200–2000 words; a typical chapter 2500–4000; "
            "a deep technical dive 4500–6500. VARY the targets across the book; do not "
            "make every chapter the same length. Respect the style guide's '## Length' "
            "section as the overall envelope."
        )
    )
    hint_clause = (
        f"\nAdditional steering from the user: {hint!r}" if hint else ""
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
        f"{words_clause}\n"
        f"{chapters_clause}"
        f"{title_clause}\n"
        "For each chapter populate:\n"
        "- 3–8 beats covering the chapter's substance.\n"
        "- 0–6 code_examples: short descriptions of runnable snippets to include.\n"
        "- 0–4 tables: short descriptions of data the reader benefits from in tabular form "
        "(e.g. 'parameter reference', 'tradeoff matrix', 'benchmark results').\n"
        "- 0–3 diagrams: short descriptions of figures that aid understanding "
        "(e.g. 'sequence diagram of the request lifecycle', 'class hierarchy', "
        "'state machine'). Diagrams will be rendered from Mermaid syntax.\n"
        "- 0–3 charts: short descriptions of data visualizations "
        "(e.g. 'histogram of latency p50/p95/p99', 'memory growth over time', "
        "'comparison bar chart of three approaches'). Charts will be rendered "
        "from Vega-Lite JSON.\n"
        "- 0–2 images: short descriptions of generated illustrative images "
        "(e.g. 'photo-realistic shot of a server rack with overlaid heat map', "
        "'stylized illustration of a CPU pipeline'). Use SPARINGLY — only when "
        "an image adds something diagrams/charts cannot. Each image costs ~$0.04.\n"
        f"{hint_clause}\n"
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
                    "Return your answer by calling the emit_outline tool — never plain text.\n\n"
                    + ANTI_ATTRIBUTION
                ),
            },
        ],
        "messages": [{"role": "user", "content": user}],
        "tools": [OUTLINE_TOOL],
        "tool_choice": {"type": "tool", "name": "emit_outline"},
    }


def build_repair_messages(
    style: Style, opts: Options, prior_json: str, error: str, hint: str | None = None
) -> dict[str, Any]:
    base = build_outline_messages(style, opts, hint=hint)
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
