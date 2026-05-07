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

    def update(
        self, n: int, status: str, stats: dict[str, int] | None, title: str = ""
    ) -> None:
        words = ""
        if stats:
            words = f" ({stats.get('output_tokens', 0)} out tok)"
        suffix = f": {title}" if title and status in ("queued", "start") else ""
        print(f"[ch {n:02d}] {status}{suffix}{words}", file=sys.stderr, flush=True)


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


@contextmanager
def progress(total: int) -> Any:
    """Chapter-generation progress: overall bar + a live sub-task per running chapter."""
    if not is_tty():
        yield _PlainProgress(total)
        return
    try:
        from rich.progress import (
            BarColumn,
            Progress,
            SpinnerColumn,
            TextColumn,
            TimeElapsedColumn,
        )
    except ImportError:
        yield _PlainProgress(total)
        return

    p = Progress(
        SpinnerColumn(style="cyan"),
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        TimeElapsedColumn(),
        console=_console,
        transient=False,
        refresh_per_second=8,
    )
    overall = p.add_task("[bold cyan]chapters", total=total)
    sub: dict[int, int] = {}

    class _RichProgress:
        def update(
            self, n: int, status: str, stats: dict[str, int] | None, title: str = ""
        ) -> None:
            if status == "queued":
                # Implicit in TTY mode — running chapters appear as sub-tasks; the
                # rest are queued by definition. No log line needed.
                return
            if status == "start":
                if n not in sub:
                    label = f"  ch {n:02d}  {_truncate(title, 50)}"
                    sub[n] = p.add_task(label, total=None, start=True)
            elif status in ("done", "skip"):
                if n in sub:
                    p.remove_task(sub.pop(n))
                p.advance(overall, 1)
                tail = ""
                if stats and stats.get("output_tokens"):
                    tail = f" ({stats['output_tokens']} tok)"
                p.console.log(f"✓ ch {n:02d} {status}{tail}")

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
