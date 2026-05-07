from __future__ import annotations

import asyncio
import shutil
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import questionary
from rich.console import Console
from rich.table import Table

from epubgen.outline import generate_outline, save_outline
from epubgen.progress import phase
from epubgen.refine import refine_description, refine_topic
from epubgen.schema import Options, Outline, RefinedTopic
from epubgen.styles import list_default_styles, load_style
from epubgen.workdir import default_workdir, ensure_workdir, slugify

_console = Console(stderr=True)

StepResult = Literal["next", "back", "cancel"]
BACK = "__back__"
CANCEL = "__cancel__"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class State:
    topic: str | None = None
    style: str | None = None
    refined: RefinedTopic | None = None
    description: str | None = None
    out_path: Path | None = None
    workdir: Path | None = None
    outline: Outline | None = None
    outline_hint: str | None = None
    ereader: bool = True

    def to_options(self) -> Options:
        assert self.topic and self.style and self.out_path and self.workdir
        return Options(
            topic=self.topic,
            style=self.style,
            out=self.out_path,
            workdir=self.workdir,
            ereader=self.ereader,
            preferred_title=self.refined.title if self.refined else None,
            preferred_subtitle=self.refined.subtitle if self.refined else None,
            description=self.description,
        )


# Steps in order, with the state fields each step "owns". Going back from step i
# clears every owned field for steps > target, so changing an upstream value
# regenerates downstream artifacts.
_STEP_FIELDS: dict[str, tuple[str, ...]] = {
    "topic": ("topic",),
    "style": ("style",),
    "title": ("refined",),
    "description": ("description",),
    "out_path": ("out_path", "workdir"),
    "outline": ("outline", "outline_hint"),
    "ereader": ("ereader",),
    "confirm": (),
}


def _invalidate_after(state: State, idx: int) -> None:
    keys = list(_STEP_FIELDS.keys())
    for key in keys[idx + 1 :]:
        for field_name in _STEP_FIELDS[key]:
            default = State.__dataclass_fields__[field_name].default
            if callable(default):  # field with default_factory
                default = None
            setattr(state, field_name, default)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wrap(text: str, *, indent: int, width: int) -> str:
    avail = max(20, width - indent)
    lines = textwrap.wrap(text, width=avail) or [text]
    pad = " " * indent
    return ("\n" + pad).join(lines)


def _term_width() -> int:
    return shutil.get_terminal_size((100, 24)).columns - 8


def _navchoices(*, allow_back: bool) -> list[questionary.Choice | questionary.Separator]:
    out: list[questionary.Choice | questionary.Separator] = [questionary.Separator("─" * 50)]
    if allow_back:
        out.append(questionary.Choice(title="←  Back", value=BACK))
    out.append(questionary.Choice(title="✕  Cancel", value=CANCEL))
    return out


def _decide(answer: object, allow_back: bool) -> StepResult | None:
    if answer is None or answer == CANCEL:
        return "cancel"
    if answer == BACK:
        return "back" if allow_back else "cancel"
    return None


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def step_topic(state: State, allow_back: bool) -> StepResult:
    answer = questionary.text("Topic:", default=state.topic or "").ask()
    if answer is None:
        return "cancel"
    if not answer.strip():
        return "cancel"
    state.topic = answer.strip()
    return "next"


def step_style(state: State, allow_back: bool) -> StepResult:
    choices: list[questionary.Choice | questionary.Separator] = [
        questionary.Choice(title=f"{name:<18} {desc}", value=name)
        for name, desc in list_default_styles()
    ]
    choices.extend(_navchoices(allow_back=allow_back))
    answer = questionary.select(
        "Style:",
        choices=choices,
        default=state.style or list_default_styles()[0][0],
    ).ask()
    decision = _decide(answer, allow_back)
    if decision is not None:
        return decision
    state.style = answer  # type: ignore[assignment]
    return "next"


_TITLE_EDIT = "__edit__"
_TITLE_REGEN = "__regen__"
_TITLE_REGEN_HINT = "__regen_hint__"
_TITLE_CLEAR_HINT = "__clear_hint__"
_TITLE_RAW = "__raw__"


def _title_choices(
    suggestions: list[RefinedTopic], hint: str | None, allow_back: bool
) -> list[questionary.Choice | questionary.Separator]:
    width = _term_width()
    out: list[questionary.Choice | questionary.Separator] = []
    for s in suggestions:
        subtitle = _wrap(s.subtitle, indent=5, width=width)
        angle = _wrap(s.angle, indent=7, width=width)
        out.append(questionary.Choice(title=f"{s.title}\n     {subtitle}\n     › {angle}", value=s))
    out.append(questionary.Separator("─" * 50))
    out.append(questionary.Choice(title="✎  Edit one of the above", value=_TITLE_EDIT))
    regen_label = "↻  Regenerate" + (f"  (with hint: {hint!r})" if hint else "")
    out.append(questionary.Choice(title=regen_label, value=_TITLE_REGEN))
    hint_label = "✏  Regenerate with a hint…" if not hint else "✏  Change the hint…"
    out.append(questionary.Choice(title=hint_label, value=_TITLE_REGEN_HINT))
    if hint:
        out.append(
            questionary.Choice(title="✕  Clear hint and regenerate", value=_TITLE_CLEAR_HINT)
        )
    out.append(questionary.Choice(title="→  Use my original topic", value=_TITLE_RAW))
    if allow_back:
        out.append(questionary.Choice(title="←  Back", value=BACK))
    out.append(questionary.Choice(title="✕  Cancel", value=CANCEL))
    return out


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


def step_title(state: State, allow_back: bool) -> StepResult:
    assert state.topic and state.style
    style = load_style(state.style)
    hint: str | None = None
    while True:
        with phase(f"Drafting framings for a {state.style} book"):
            try:
                result = asyncio.run(
                    refine_topic(style, state.topic, model="claude-opus-4-7", hint=hint)
                )
            except Exception as e:
                _console.print(f"[yellow]refinement skipped: {e}[/yellow]")
                state.refined = None
                return "next"

        choice = questionary.select(
            "Pick a framing:",
            choices=_title_choices(result.suggestions, hint, allow_back),
        ).ask()
        decision = _decide(choice, allow_back)
        if decision is not None:
            return decision
        if choice == _TITLE_RAW:
            state.refined = None
            return "next"
        if choice == _TITLE_REGEN:
            continue
        if choice == _TITLE_CLEAR_HINT:
            hint = None
            continue
        if choice == _TITLE_REGEN_HINT:
            new_hint = questionary.text(
                "Hint (e.g. 'punchier', 'less academic', 'focus on async'):",
                default=hint or "",
            ).ask()
            if new_hint is None:
                return "cancel"
            hint = new_hint.strip() or None
            continue
        if choice == _TITLE_EDIT:
            edited = _edit_suggestion(result.suggestions)
            if edited is not None:
                state.refined = edited
                return "next"
            continue
        # An actual RefinedTopic from the choices list.
        state.refined = choice  # type: ignore[assignment]
        return "next"


_DESC_ACCEPT = "__accept__"
_DESC_EDIT = "__edit__"
_DESC_REGEN = "__regen__"
_DESC_REGEN_HINT = "__regen_hint__"
_DESC_CLEAR_HINT = "__clear_hint__"
_DESC_SKIP = "__skip__"


def step_description(state: State, allow_back: bool) -> StepResult:
    if state.refined is None:
        # No title to anchor a description; skip silently.
        state.description = None
        return "next"
    style = load_style(state.style)
    hint: str | None = None
    description: str | None = state.description
    while True:
        if description is None:
            with phase("Drafting description"):
                try:
                    description = asyncio.run(
                        refine_description(
                            style, state.topic, state.refined, model="claude-opus-4-7", hint=hint
                        )
                    )
                except Exception as e:
                    _console.print(f"[yellow]description skipped: {e}[/yellow]")
                    state.description = None
                    return "next"
        _console.print()
        _console.print("[bold]Description draft:[/bold]")
        _console.print(description)
        _console.print()

        choices = [
            questionary.Choice(title="✓  Accept", value=_DESC_ACCEPT),
            questionary.Choice(title="✎  Edit text", value=_DESC_EDIT),
        ]
        regen_label = "↻  Regenerate" + (f"  (with hint: {hint!r})" if hint else "")
        choices.append(questionary.Choice(title=regen_label, value=_DESC_REGEN))
        hint_label = "✏  Regenerate with a hint…" if not hint else "✏  Change the hint…"
        choices.append(questionary.Choice(title=hint_label, value=_DESC_REGEN_HINT))
        if hint:
            choices.append(
                questionary.Choice(title="✕  Clear hint and regenerate", value=_DESC_CLEAR_HINT)
            )
        choices.append(questionary.Choice(title="→  Skip (no description)", value=_DESC_SKIP))
        if allow_back:
            choices.append(questionary.Choice(title="←  Back", value=BACK))
        choices.append(questionary.Choice(title="✕  Cancel", value=CANCEL))

        choice = questionary.select("What now?", choices=choices).ask()
        decision = _decide(choice, allow_back)
        if decision is not None:
            return decision
        if choice == _DESC_ACCEPT:
            state.description = description
            return "next"
        if choice == _DESC_SKIP:
            state.description = None
            return "next"
        if choice == _DESC_EDIT:
            edited = questionary.text(
                "Edit description (Enter to keep, ESC to cancel):", default=description
            ).ask()
            if edited and edited.strip():
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
                return "cancel"
            hint = new_hint.strip() or None
            description = None
            continue


def _workdir_summary(workdir: Path) -> list[str]:
    """One-line summary of any prior-run artifacts in the workdir."""
    if not workdir.exists():
        return []
    items: list[str] = []
    for name in ("options.json", "outline.json", "colophon.md", "metadata.yaml"):
        if (workdir / name).exists():
            items.append(name)
    chapters = sorted(workdir.glob("ch-*.md"))
    if chapters:
        items.append(f"{len(chapters)} chapter(s)")
    return items


def step_out_path(state: State, allow_back: bool) -> StepResult:
    while True:
        title_for_slug = state.refined.title if state.refined else state.topic
        default_out = (
            state.out_path and str(state.out_path)
        ) or f"./{slugify(title_for_slug)}.epub"
        answer = questionary.text("Output path:", default=default_out).ask()
        if answer is None:
            return "back" if allow_back else "cancel"
        if not answer.strip():
            return "cancel"
        out_path = Path(answer.strip())
        workdir = default_workdir(out_path)

        contents = _workdir_summary(workdir)
        if not contents:
            state.out_path = out_path
            state.workdir = workdir
            return "next"

        # Stale workdir from a prior run — the pipeline's freeze_options check
        # will refuse to proceed if anything diverges, so resolve it now.
        _console.print()
        _console.print(
            f"[yellow]The workdir [bold]{workdir}[/bold] already contains: "
            f"{', '.join(contents)}[/yellow]"
        )
        _console.print(
            "[dim]Generating into a stale workdir would either overwrite or "
            "fail with an options.json mismatch.[/dim]"
        )
        _console.print()
        nav: list[questionary.Choice | questionary.Separator] = [
            questionary.Choice(
                title="🗑  Clear that workdir and start fresh here", value="clear"
            ),
            questionary.Choice(title="✎  Pick a different output path", value="retry"),
            questionary.Separator("─" * 50),
        ]
        if allow_back:
            nav.append(questionary.Choice(title="←  Back", value=BACK))
        nav.append(questionary.Choice(title="✕  Cancel", value=CANCEL))
        choice = questionary.select("What should we do?", choices=nav).ask()
        if choice is None or choice == CANCEL:
            return "cancel"
        if choice == BACK:
            return "back"
        if choice == "retry":
            # Keep the typed path as the next default so the user can edit it.
            state.out_path = out_path
            continue
        if choice == "clear":
            shutil.rmtree(workdir)
            state.out_path = out_path
            state.workdir = workdir
            return "next"


_TOC_ACCEPT = "__accept__"
_TOC_REGEN = "__regen__"
_TOC_REGEN_HINT = "__regen_hint__"
_TOC_CLEAR_HINT = "__clear_hint__"


def _render_toc(outline: Outline) -> None:
    table = Table(
        title=f"[bold]{outline.title}[/bold]"
        + (f" — [italic]{outline.subtitle}[/italic]" if outline.subtitle else ""),
        title_justify="left",
        show_lines=False,
    )
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Title", style="bold")
    table.add_column("Beats", justify="right")
    table.add_column("Code/Tbl/Dia/Cht/Img", justify="right", style="dim")
    table.add_column("~Words", justify="right")
    for ch in outline.chapters:
        counts = (
            f"{len(ch.code_examples)}/{len(ch.tables)}/"
            f"{len(ch.diagrams)}/{len(ch.charts)}/{len(ch.images)}"
        )
        table.add_row(
            str(ch.number),
            ch.title,
            str(len(ch.beats)),
            counts,
            str(ch.word_target),
        )
    _console.print()
    _console.print(table)
    _console.print()


def step_outline(state: State, allow_back: bool) -> StepResult:
    assert state.topic and state.style and state.workdir
    style = load_style(state.style)
    opts = state.to_options()

    def _gen() -> Outline:
        return asyncio.run(generate_outline(style, opts, hint=state.outline_hint))

    if state.outline is None:
        try:
            with phase("Generating outline"):
                state.outline = _gen()
        except Exception as e:
            _console.print(f"[red]outline generation failed: {e}[/red]")
            return "back" if allow_back else "cancel"

    while True:
        _render_toc(state.outline)

        choices: list[questionary.Choice | questionary.Separator] = [
            questionary.Choice(title="✓  Accept and write chapters", value=_TOC_ACCEPT),
        ]
        regen_label = "↻  Regenerate"
        if state.outline_hint:
            regen_label += f"  (with hint: {state.outline_hint!r})"
        choices.append(questionary.Choice(title=regen_label, value=_TOC_REGEN))
        hint_label = (
            "✏  Regenerate with a hint…" if not state.outline_hint else "✏  Change the hint…"
        )
        choices.append(questionary.Choice(title=hint_label, value=_TOC_REGEN_HINT))
        if state.outline_hint:
            choices.append(
                questionary.Choice(title="✕  Clear hint and regenerate", value=_TOC_CLEAR_HINT)
            )
        choices.extend(_navchoices(allow_back=allow_back))

        choice = questionary.select("Table of contents:", choices=choices).ask()
        decision = _decide(choice, allow_back)
        if decision is not None:
            return decision
        if choice == _TOC_ACCEPT:
            ensure_workdir(state.workdir)
            save_outline(state.workdir / "outline.json", state.outline)
            return "next"
        if choice == _TOC_CLEAR_HINT:
            state.outline_hint = None
        elif choice == _TOC_REGEN_HINT:
            new_hint = questionary.text(
                "Hint (e.g. 'fewer chapters', 'add a chapter on testing', "
                "'less theory more code'):",
                default=state.outline_hint or "",
            ).ask()
            if new_hint is None:
                return "cancel"
            state.outline_hint = new_hint.strip() or None
        # Regenerate.
        try:
            with phase("Regenerating outline"):
                state.outline = _gen()
        except Exception as e:
            _console.print(f"[red]regeneration failed: {e}[/red]")
            continue


def step_ereader(state: State, allow_back: bool) -> StepResult:
    choices: list[questionary.Choice | questionary.Separator] = [
        questionary.Choice(
            title="Yes — tune for ~6\" e-readers (Kindle / Kobo / KOReader / Pocketbook)",
            value=True,
        ),
        questionary.Choice(
            title="No — standard EPUB (tablet / desktop / iBooks / Calibre)",
            value=False,
        ),
    ]
    choices.extend(_navchoices(allow_back=allow_back))
    answer = questionary.select(
        "Optimize for an e-reader?",
        choices=choices,
        default=state.ereader,
    ).ask()
    decision = _decide(answer, allow_back)
    if decision is not None:
        return decision
    state.ereader = bool(answer)
    return "next"


def step_confirm(state: State, allow_back: bool) -> StepResult:
    title = state.refined.title if state.refined else state.topic
    chapters = len(state.outline.chapters) if state.outline else "?"
    summary = (
        f"[bold]Title:[/bold] {title}\n"
        f"[bold]Style:[/bold] {state.style}\n"
        f"[bold]Chapters:[/bold] {chapters}\n"
        f"[bold]E-reader tuned:[/bold] {'yes' if state.ereader else 'no'}\n"
        f"[bold]Output:[/bold] {state.out_path}"
    )
    _console.print()
    _console.print(summary)
    _console.print()
    choices: list[questionary.Choice | questionary.Separator] = [
        questionary.Choice(title="✓  Generate the book", value="go"),
    ]
    choices.extend(_navchoices(allow_back=allow_back))
    answer = questionary.select("Ready?", choices=choices).ask()
    decision = _decide(answer, allow_back)
    if decision is not None:
        return decision
    return "next"


# ---------------------------------------------------------------------------
# Step machine
# ---------------------------------------------------------------------------


_STEPS: list[tuple[str, callable]] = [
    ("topic", step_topic),
    ("style", step_style),
    ("title", step_title),
    ("description", step_description),
    ("out_path", step_out_path),
    ("outline", step_outline),
    ("ereader", step_ereader),
    ("confirm", step_confirm),
]


def _resume_summary(state: State, step_idx: int) -> str:
    parts: list[str] = []
    if state.topic:
        parts.append(f"topic: {state.topic!r}")
    if state.style:
        parts.append(f"style: {state.style}")
    if state.refined:
        parts.append(f"title: {state.refined.title!r}")
    body = " · ".join(parts) if parts else "(no choices yet)"
    next_step = _STEPS[step_idx][0] if step_idx < len(_STEPS) else "complete"
    return f"{body}\n  next step: {next_step}"


def _maybe_resume() -> tuple[State, int]:
    from epubgen import wizard_state

    saved = wizard_state.load()
    if saved is None:
        return State(), 0
    state, step_idx = saved
    _console.print()
    _console.print("[bold cyan]Found a previous wizard session:[/bold cyan]")
    _console.print(f"  {_resume_summary(state, step_idx)}")
    _console.print()
    answer = questionary.select(
        "Resume?",
        choices=[
            questionary.Choice(title="✓  Resume from where I left off", value="resume"),
            questionary.Choice(title="✕  Start fresh (discard previous)", value="fresh"),
        ],
    ).ask()
    if answer == "resume":
        return state, step_idx
    wizard_state.clear()
    return State(), 0


def run_wizard() -> Options | None:
    from epubgen import wizard_state

    if not sys.stdin.isatty():
        return None
    state, i = _maybe_resume()
    while 0 <= i < len(_STEPS):
        _name, step = _STEPS[i]
        result = step(state, allow_back=(i > 0))
        if result == "next":
            i += 1
            wizard_state.save(state, i)
        elif result == "back":
            _invalidate_after(state, i - 1)
            i = max(0, i - 1)
            wizard_state.save(state, i)
        elif result == "cancel":
            wizard_state.clear()
            return None
    wizard_state.clear()
    return state.to_options()


# Kept as a public helper for the `generate --refine` path (wraps step_title only).
def _interactive_refine(style_name: str, topic: str, model: str) -> RefinedTopic | None:
    state = State(topic=topic, style=style_name)
    res = step_title(state, allow_back=False)
    if res != "next":
        return None
    return state.refined
