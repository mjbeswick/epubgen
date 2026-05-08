"""Persist wizard sessions across runs so a crash doesn't lose API-paid work.

Each session is a separate file under ``~/.cache/epubgen/sessions/`` (or
``$XDG_CACHE_HOME/epubgen/sessions/``). Multiple wizards in different terminals
get independent sessions; the resume prompt lists them all and lets the user
pick.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from epubgen.schema import Outline, RefinedTopic

if TYPE_CHECKING:
    from epubgen.wizard import State

_VERSION = 1


def _cache_root() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    return Path(base) if base else Path.home() / ".cache"


def sessions_dir() -> Path:
    return _cache_root() / "epubgen" / "sessions"


def session_path(session_id: str) -> Path:
    return sessions_dir() / f"{session_id}.json"


def _slugify(text: str | None) -> str:
    if not text:
        return "untitled"
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (s or "untitled")[:40]


def new_session_id(state: State) -> str:
    """Generate a unique session id from current state + timestamp."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    slug = _slugify(state.topic)
    base = f"{stamp}__{slug}"
    # Ensure uniqueness against any existing file (rare collision under second granularity).
    candidate = base
    n = 0
    while session_path(candidate).exists():
        n += 1
        candidate = f"{base}-{n}"
    return candidate


@dataclass
class SessionInfo:
    session_id: str
    path: Path
    mtime: float
    topic: str | None
    style: str | None
    title: str | None
    step_index: int


def list_sessions() -> list[SessionInfo]:
    d = sessions_dir()
    if not d.exists():
        return []
    out: list[SessionInfo] = []
    for path in d.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("version") != _VERSION:
                continue
            refined = data.get("refined") or {}
            out.append(
                SessionInfo(
                    session_id=path.stem,
                    path=path,
                    mtime=path.stat().st_mtime,
                    topic=data.get("topic"),
                    style=data.get("style"),
                    title=refined.get("title") if isinstance(refined, dict) else None,
                    step_index=int(data.get("step_index", 0)),
                )
            )
        except (OSError, json.JSONDecodeError, ValueError):
            continue
    out.sort(key=lambda s: s.mtime, reverse=True)
    return out


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
    from epubgen.wizard import State

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
    return state, int(data.get("step_index", 0))


def save(state: State, step_index: int, session_id: str) -> None:
    path = session_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_dump_state(state, step_index), indent=2), encoding="utf-8")
    os.replace(tmp, path)


def load(session_id: str) -> tuple[State, int] | None:
    path = session_path(session_id)
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


def clear(session_id: str) -> None:
    with contextlib.suppress(OSError):
        session_path(session_id).unlink()
