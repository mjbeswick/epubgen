from __future__ import annotations

import json
from typing import Any

from epubgen.prompts._shared import ANTI_ATTRIBUTION
from epubgen.schema import Chapter, Options, Outline
from epubgen.styles import Style


def canonical_outline_text(outline: Outline) -> str:
    # Stable across runs so the cache key for breakpoint 2 is byte-stable.
    return json.dumps(outline.model_dump(), sort_keys=True, indent=2)


def build_revise_messages(
    style: Style,
    outline: Outline,
    chapter: Chapter,
    current_text: str,
    instruction: str,
    opts: Options,
    sources_text: str = "",
) -> dict[str, Any]:
    """Build a payload that asks the model to revise an existing chapter.

    Reuses the same cached system blocks (style, optional sources, outline) as
    fresh chapter generation so the cache prefix is preserved across rewrite
    and revise calls in the same run.
    """
    ereader_clause = (
        "\n\nE-reader constraint (≈6\" screens, reflowable): code lines must be ≤60 characters; "
        "tables ≤4 columns. Apply this to any new or modified content."
        if opts.ereader
        else ""
    )
    user = (
        f'Revise Chapter {chapter.number}: "{chapter.title}".\n\n'
        f"Current content (between <<< >>> markers):\n\n"
        f"<<<\n{current_text.rstrip()}\n>>>\n\n"
        f"Instruction from the user:\n{instruction}\n\n"
        "Return ONLY the revised chapter markdown — no preamble, no commentary, "
        "no explanation of changes. Begin with `# {title}` as the H1. Preserve "
        "untouched sections verbatim; only modify what the instruction requires. "
        "If adding new content, place it where it belongs structurally (the user "
        "may specify, otherwise use your judgement). Keep the chapter's voice "
        "consistent with the surrounding material and the style guide."
        f"{ereader_clause}"
    )
    system: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": style.guide,
            "cache_control": {"type": "ephemeral"},
        },
    ]
    if sources_text:
        system.append({
            "type": "text",
            "text": sources_text,
            "cache_control": {"type": "ephemeral"},
        })
    system.append({
        "type": "text",
        "text": (
            "Full book outline (for cross-chapter context):\n\n"
            + canonical_outline_text(outline)
        ),
        "cache_control": {"type": "ephemeral"},
    })
    sources_clause = (
        " Any new factual claims must be supported by the reference sources above."
        if sources_text else ""
    )
    system.append({
        "type": "text",
        "text": (
            "You revise existing chapters according to a user instruction. "
            "Respect the existing prose; do not rewrite passages that the "
            "instruction does not touch."
            f"{sources_clause}\n\n"
            + ANTI_ATTRIBUTION
        ),
    })
    return {"system": system, "messages": [{"role": "user", "content": user}]}


def build_chapter_messages(
    style: Style, outline: Outline, chapter: Chapter, opts: Options, sources_text: str = ""
) -> dict[str, Any]:
    beats = "\n".join(f"- {b.summary}" for b in chapter.beats)
    code = "\n".join(f"- {c}" for c in chapter.code_examples) or "(none)"
    tables = "\n".join(f"- {t}" for t in chapter.tables) or "(none)"
    diagrams = "\n".join(f"- {d}" for d in chapter.diagrams) or "(none)"
    charts = "\n".join(f"- {c}" for c in chapter.charts) or "(none)"
    images = "\n".join(f"- {i}" for i in chapter.images) or "(none)"
    ereader_clause = (
        "\n\nE-reader constraint (≈6\" screens, reflowable): code lines must be ≤60 characters; "
        "refactor or wrap rather than truncating. Tables ≤4 columns."
        if opts.ereader
        else ""
    )
    user = (
        f'Write Chapter {chapter.number}: "{chapter.title}".\n\n'
        f"Synopsis: {chapter.synopsis}\n\n"
        f"Required beats (cover all):\n{beats}\n\n"
        f"Code examples to include (runnable, fenced, language-tagged):\n{code}\n\n"
        f"Tables to include (use GitHub-style markdown tables):\n{tables}\n\n"
        f"Diagrams to include (emit each as a fenced ```mermaid``` block; "
        f"the build pipeline renders them to images):\n{diagrams}\n\n"
        f"Charts to include (emit each as a fenced ```vegalite``` block containing valid "
        f"Vega-Lite v5 JSON with inline data; the build pipeline renders them to images):\n"
        f"{charts}\n\n"
        f"Images to include (emit each as a fenced ```image``` block whose contents are a "
        f"detailed image-generation prompt; the build pipeline calls an image API):\n"
        f"{images}\n\n"
        "Math: when the topic warrants it, use `$...$` for inline math and "
        "`$$...$$` for display math (LaTeX syntax). Pandoc renders these to MathML.\n\n"
        f"Target length: ~{chapter.word_target} words "
        "(tables and diagrams substitute for prose, not in addition to it).\n"
        "Output Markdown only. Begin with `# {title}` as the H1. "
        "Do not include front-matter, commentary, or surrounding prose."
        f"{ereader_clause}"
    )
    system: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": style.guide,
            "cache_control": {"type": "ephemeral"},
        },
    ]
    if sources_text:
        system.append({
            "type": "text",
            "text": sources_text,
            "cache_control": {"type": "ephemeral"},
        })
    system.append({
        "type": "text",
        "text": (
            "Full book outline (for cross-chapter context):\n\n"
            + canonical_outline_text(outline)
        ),
        "cache_control": {"type": "ephemeral"},
    })
    sources_clause = (
        " Ground every factual claim in the reference sources above; if a claim "
        "isn't supported there, omit it. The style guide governs voice and "
        "structure only — never let it override what the sources say."
        if sources_text else ""
    )
    system.append({
        "type": "text",
        "text": (
            "You write one chapter at a time. Match the style guide exactly. "
            "Don't repeat material from other chapters; "
            "reference them by title when useful."
            f"{sources_clause}\n\n"
            + ANTI_ATTRIBUTION
        ),
    })
    return {
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
