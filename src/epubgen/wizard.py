from __future__ import annotations

import asyncio
import shutil
import sys
import textwrap
from pathlib import Path

import questionary
from rich.console import Console

from epubgen.refine import refine_description, refine_topic
from epubgen.schema import Options, RefinedTopic
from epubgen.styles import list_default_styles, load_style
from epubgen.workdir import default_workdir, slugify

_console = Console(stderr=True)

_SENTINEL_EDIT = "__edit__"
_SENTINEL_REGEN = "__regen__"
_SENTINEL_REGEN_HINT = "__regen_hint__"
_SENTINEL_CLEAR_HINT = "__clear_hint__"
_SENTINEL_RAW = "__raw__"


def _wrap(text: str, *, indent: int, width: int) -> str:
    """Wrap text to width, prefixing every line after the first with indent spaces."""
    avail = max(20, width - indent)
    lines = textwrap.wrap(text, width=avail) or [text]
    pad = " " * indent
    return ("\n" + pad).join(lines)


def _build_choices(
    suggestions: list[RefinedTopic], current_hint: str | None
) -> list[questionary.Choice]:
    # questionary prefixes each rendered choice with ~4 chars of cursor/marker, so
    # leave a margin to avoid the renderer truncating long lines.
    term_width = shutil.get_terminal_size((100, 24)).columns - 8
    choices: list[questionary.Choice] = []
    for s in suggestions:
        subtitle = _wrap(s.subtitle, indent=5, width=term_width)
        angle = _wrap(s.angle, indent=7, width=term_width)
        title = f"{s.title}\n     {subtitle}\n     › {angle}"
        choices.append(questionary.Choice(title=title, value=s))
    choices.append(questionary.Separator("─" * 50))
    choices.append(questionary.Choice(title="✎  Edit one of the above", value=_SENTINEL_EDIT))
    regen_label = "↻  Regenerate"
    if current_hint:
        regen_label += f"  (with hint: {current_hint!r})"
    choices.append(questionary.Choice(title=regen_label, value=_SENTINEL_REGEN))
    hint_label = "✏  Regenerate with a hint…" if not current_hint else "✏  Change the hint…"
    choices.append(questionary.Choice(title=hint_label, value=_SENTINEL_REGEN_HINT))
    if current_hint:
        choices.append(
            questionary.Choice(title="✕  Clear hint and regenerate", value=_SENTINEL_CLEAR_HINT)
        )
    choices.append(
        questionary.Choice(title="→  Use my original topic (skip refinement)", value=_SENTINEL_RAW)
    )
    return choices


def _edit_suggestion(suggestions: list[RefinedTopic]) -> RefinedTopic | None:
    pick = questionary.select(
        "Which one do you want to edit?",
        choices=[questionary.Choice(title=s.title, value=i) for i, s in enumerate(suggestions)],
    ).ask()
    if pick is None:
        return None
    base = suggestions[pick]
    title = questionary.text("Title:", default=base.title).ask()
    if title is None:
        return None
    subtitle = questionary.text("Subtitle:", default=base.subtitle).ask()
    if subtitle is None:
        return None
    return RefinedTopic(title=title, subtitle=subtitle, angle=base.angle)


def _interactive_refine(style_name: str, topic: str, model: str) -> RefinedTopic | None:
    style = load_style(style_name)
    hint: str | None = None
    while True:
        status_msg = f"Drafting framings for a {style.name} book"
        if hint:
            status_msg += f" (hint: {hint!r})"
        status_msg += "…"
        with _console.status(status_msg, spinner="dots"):
            try:
                result = asyncio.run(refine_topic(style, topic, model=model, hint=hint))
            except Exception as e:
                _console.print(f"[yellow]refinement skipped: {e}[/yellow]")
                return None

        choice = questionary.select(
            "Pick a framing:",
            choices=_build_choices(result.suggestions, hint),
        ).ask()
        if choice is None:
            return None
        if choice == _SENTINEL_RAW:
            return None
        if choice == _SENTINEL_REGEN:
            continue
        if choice == _SENTINEL_CLEAR_HINT:
            hint = None
            continue
        if choice == _SENTINEL_REGEN_HINT:
            new_hint = questionary.text(
                "Hint (e.g. 'punchier', 'less academic', 'focus on async'):",
                default=hint or "",
            ).ask()
            if new_hint is None:
                return None
            hint = new_hint.strip() or None
            continue
        if choice == _SENTINEL_EDIT:
            edited = _edit_suggestion(result.suggestions)
            if edited is not None:
                return edited
            continue
        return choice  # type: ignore[return-value]


_DESC_ACCEPT = "__accept__"
_DESC_EDIT = "__edit__"
_DESC_REGEN = "__regen__"
_DESC_REGEN_HINT = "__regen_hint__"
_DESC_CLEAR_HINT = "__clear_hint__"
_DESC_SKIP = "__skip__"


def _interactive_description(
    style_name: str, topic: str, framing: RefinedTopic, model: str
) -> str | None:
    style = load_style(style_name)
    hint: str | None = None
    description: str | None = None
    while True:
        if description is None:
            status_msg = f"Drafting a description for {framing.title!r}"
            if hint:
                status_msg += f" (hint: {hint!r})"
            status_msg += "…"
            with _console.status(status_msg, spinner="dots"):
                try:
                    description = asyncio.run(
                        refine_description(style, topic, framing, model=model, hint=hint)
                    )
                except Exception as e:
                    _console.print(f"[yellow]description skipped: {e}[/yellow]")
                    return None
        _console.print()
        _console.print("[bold]Description draft:[/bold]")
        _console.print(description)
        _console.print()

        choices = [
            questionary.Choice(title="✓  Accept", value=_DESC_ACCEPT),
            questionary.Choice(title="✎  Edit text", value=_DESC_EDIT),
        ]
        regen_label = "↻  Regenerate"
        if hint:
            regen_label += f"  (with hint: {hint!r})"
        choices.append(questionary.Choice(title=regen_label, value=_DESC_REGEN))
        hint_label = "✏  Regenerate with a hint…" if not hint else "✏  Change the hint…"
        choices.append(questionary.Choice(title=hint_label, value=_DESC_REGEN_HINT))
        if hint:
            choices.append(
                questionary.Choice(title="✕  Clear hint and regenerate", value=_DESC_CLEAR_HINT)
            )
        choices.append(questionary.Choice(title="→  Skip (no description)", value=_DESC_SKIP))

        choice = questionary.select("What now?", choices=choices).ask()
        if choice is None:
            return None
        if choice == _DESC_ACCEPT:
            return description
        if choice == _DESC_SKIP:
            return None
        if choice == _DESC_EDIT:
            edited = questionary.text(
                "Edit description (Enter to keep, ESC to cancel):", default=description
            ).ask()
            if edited is not None and edited.strip():
                description = edited.strip()
            continue
        if choice == _DESC_CLEAR_HINT:
            hint = None
            description = None
            continue
        if choice == _DESC_REGEN:
            description = None
            continue
        if choice == _DESC_REGEN_HINT:
            new_hint = questionary.text(
                "Hint (e.g. 'shorter', 'more enthusiastic', 'mention performance'):",
                default=hint or "",
            ).ask()
            if new_hint is None:
                return description
            hint = new_hint.strip() or None
            description = None
            continue


def run_wizard() -> Options | None:
    if not sys.stdin.isatty():
        return None

    topic = questionary.text("Topic:").ask()
    if not topic:
        return None

    style = questionary.select(
        "Style:",
        choices=[
            questionary.Choice(title=f"{name:<18} {desc}", value=name)
            for name, desc in list_default_styles()
        ],
    ).ask()
    if not style:
        return None

    refined = _interactive_refine(style, topic, model="claude-opus-4-7")

    description: str | None = None
    if refined is not None:
        description = _interactive_description(
            style, topic, refined, model="claude-opus-4-7"
        )

    length = questionary.select(
        "Target length:",
        choices=[
            questionary.Choice(title="Short    (6 ch / 2500 wpc)", value=(6, 2500)),
            questionary.Choice(title="Standard (10 ch / 3000 wpc)", value=(10, 3000)),
            questionary.Choice(title="Long     (16 ch / 3500 wpc)", value=(16, 3500)),
        ],
    ).ask()
    if not length:
        return None
    chapters, words = length

    kindle = questionary.confirm("Optimize for Kindle?", default=True).ask()
    if kindle is None:
        return None

    title_for_slug = refined.title if refined else topic
    default_out = f"./{slugify(title_for_slug)}.epub"
    out = questionary.text("Output path:", default=default_out).ask()
    if not out:
        return None

    out_path = Path(out)
    return Options(
        topic=topic,
        style=style,
        out=out_path,
        workdir=default_workdir(out_path),
        chapters=chapters,
        words=words,
        kindle=bool(kindle),
        preferred_title=refined.title if refined else None,
        preferred_subtitle=refined.subtitle if refined else None,
        description=description,
    )
