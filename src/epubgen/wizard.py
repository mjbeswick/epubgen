from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import questionary
from rich.console import Console

from epubgen.refine import refine_topic
from epubgen.schema import Options, RefinedTopic
from epubgen.styles import list_default_styles, load_style
from epubgen.workdir import default_workdir, slugify

_console = Console(stderr=True)

_SENTINEL_EDIT = "__edit__"
_SENTINEL_REGEN = "__regen__"
_SENTINEL_RAW = "__raw__"


def _build_choices(suggestions: list[RefinedTopic]) -> list[questionary.Choice]:
    choices: list[questionary.Choice] = []
    for s in suggestions:
        title = f"{s.title}\n     {s.subtitle}\n     › {s.angle}"
        choices.append(questionary.Choice(title=title, value=s))
    choices.append(questionary.Separator("─" * 50))
    choices.append(questionary.Choice(title="✎  Edit one of the above", value=_SENTINEL_EDIT))
    choices.append(questionary.Choice(title="↻  Regenerate", value=_SENTINEL_REGEN))
    choices.append(questionary.Choice(title="→  Use my original topic (skip refinement)",
                                      value=_SENTINEL_RAW))
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
    while True:
        with _console.status(f"Drafting framings for a {style.name} book…", spinner="dots"):
            try:
                result = asyncio.run(refine_topic(style, topic, model=model))
            except Exception as e:
                _console.print(f"[yellow]refinement skipped: {e}[/yellow]")
                return None

        choice = questionary.select(
            "Pick a framing:",
            choices=_build_choices(result.suggestions),
        ).ask()
        if choice is None:
            return None
        if choice == _SENTINEL_RAW:
            return None
        if choice == _SENTINEL_REGEN:
            continue
        if choice == _SENTINEL_EDIT:
            edited = _edit_suggestion(result.suggestions)
            if edited is not None:
                return edited
            continue
        return choice  # type: ignore[return-value]


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
    )
