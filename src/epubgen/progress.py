from __future__ import annotations

import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


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
    if not sys.stderr.isatty():
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
        TextColumn("[bold]chapters"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
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
