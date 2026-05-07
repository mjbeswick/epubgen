"""Persist wizard state across runs so a crash doesn't lose API-paid work.

State is stored at ``~/.cache/epubgen/wizard.json`` (or ``$XDG_CACHE_HOME``
equivalent). Saved after each successful step; cleared on successful
completion or explicit cancel.
"""

from __future__ import annotations

import contextlib
import json
import os
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from epubgen.schema import Outline, RefinedTopic

if TYPE_CHECKING:
    from epubgen.wizard import State

_VERSION = 1


def state_path() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    root = Path(base) if base else Path.home() / ".cache"
    return root / "epubgen" / "wizard.json"


def _dump_state(state: State, step_index: int) -> dict[str, Any]:
    return {
        "version": _VERSION,
        "step_index": step_index,
        "topic": state.topic,
        "style": state.style,
        "refined": state.refined.model_dump() if state.refined else None,
        "description": state.description,
        "out_path": str(state.out_path) if state.out_path else None,
        "workdir": str(state.workdir) if state.workdir else None,
        "outline": state.outline.model_dump() if state.outline else None,
        "outline_hint": state.outline_hint,
        "ereader": state.ereader,
    }


def _load_state(data: dict[str, Any]) -> tuple[State, int]:
    from epubgen.wizard import State  # avoid circular import

    refined_raw = data.get("refined")
    outline_raw = data.get("outline")
    out_path = data.get("out_path")
    workdir = data.get("workdir")

    state = State(
        topic=data.get("topic"),
        style=data.get("style"),
        refined=RefinedTopic.model_validate(refined_raw) if refined_raw else None,
        description=data.get("description"),
        out_path=Path(out_path) if out_path else None,
        workdir=Path(workdir) if workdir else None,
        outline=Outline.model_validate(outline_raw) if outline_raw else None,
        outline_hint=data.get("outline_hint"),
        ereader=bool(data.get("ereader", True)),
    )
    # Ensure State is still a dataclass shape (sanity).
    assert is_dataclass(state), "wizard.State must remain a dataclass"
    _ = fields(state)
    _ = asdict  # imported for future use; quiets ruff
    return state, int(data.get("step_index", 0))


def save(state: State, step_index: int) -> None:
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_dump_state(state, step_index), indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load() -> tuple[State, int] | None:
    path = state_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if data.get("version") != _VERSION:
        return None
    try:
        return _load_state(data)
    except Exception:
        return None


def clear() -> None:
    path = state_path()
    with contextlib.suppress(OSError):
        path.unlink()
