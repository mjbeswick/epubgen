from __future__ import annotations

import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from rich.console import Console

_console = Console(stderr=True)


def is_tty() -> bool:
    return sys.stderr.isatty()


@contextmanager
def phase(label: str) -> Any:
    """Show a spinner labelled with `label` while the block runs.

    On non-TTY: prints a plain start/done line to stderr.
    Rich's status renders to stderr and survives concurrent log output.
    """
    t0 = time.monotonic()
    if not is_tty():
        print(f"⏵ {label}…", file=sys.stderr, flush=True)
        try:
            yield
        finally:
            elapsed = time.monotonic() - t0
            print(f"✓ {label} ({elapsed:.1f}s)", file=sys.stderr, flush=True)
        return
    with _console.status(f"[cyan]{label}…[/cyan]", spinner="dots") as status:
        try:
            yield status
        finally:
            elapsed = time.monotonic() - t0
            _console.print(f"[green]✓[/green] {label} [dim]({elapsed:.1f}s)[/dim]")


@dataclass
class _PlainProgress:
    total: int

    def update(self, n: int, status: str, stats: dict[str, int] | None) -> None:
        words = ""
        if stats:
            words = f" ({stats.get('output_tokens', 0)} out tok)"
        print(f"[ch {n:02d}] {status}{words}", file=sys.stderr, flush=True)


@contextmanager
def progress(total: int) -> Any:
    """Per-chapter progress bar (used during the chapter-generation pool)."""
    if not is_tty():
        yield _PlainProgress(total)
        return
    try:
        from rich.progress import (
            BarColumn,
            Progress,
            TextColumn,
            TimeElapsedColumn,
        )
    except ImportError:
        yield _PlainProgress(total)
        return

    p = Progress(
        TextColumn("[bold cyan]chapters"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=_console,
        transient=False,
    )
    task_id = p.add_task("chapters", total=total)

    class _RichProgress:
        def update(self, n: int, status: str, stats: dict[str, int] | None) -> None:
            if status in ("done", "skip"):
                p.advance(task_id, 1)
            p.console.log(f"[ch {n:02d}] {status}")

    p.start()
    try:
        yield _RichProgress()
    finally:
        p.stop()


@contextmanager
def figure_progress(total: int, label: str = "figures") -> Any:
    """Progress bar for sequential figure rendering (mermaid/charts/images)."""
    if total == 0 or not is_tty():
        class _Noop:
            def advance(self, note: str = "") -> None:
                pass

        yield _Noop()
        return
    try:
        from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
    except ImportError:
        class _Noop2:
            def advance(self, _: str = "") -> None:
                pass

        yield _Noop2()
        return

    p = Progress(
        TextColumn(f"[bold cyan]{label}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TextColumn("{task.fields[note]}"),
        TimeElapsedColumn(),
        console=_console,
        transient=True,
    )
    task_id = p.add_task(label, total=total, note="")

    class _Bar:
        def advance(self, note: str = "") -> None:
            p.update(task_id, advance=1, note=note)

    p.start()
    try:
        yield _Bar()
    finally:
        p.stop()
