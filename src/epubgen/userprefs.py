"""Persisted user preferences (separate from per-session wizard state).

Stored at ``$XDG_CONFIG_HOME/epubgen/config.json`` (or ``~/.config/...``).
Currently just the default model; extend with care — keep the file small
and human-editable.
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

from epubgen.logsetup import get_logger

log = get_logger("userprefs")

_VERSION = 1
_BUILTIN_DEFAULT_MODEL = "claude-sonnet-4-6"


def _config_root() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    return Path(base) if base else Path.home() / ".config"


def config_path() -> Path:
    return _config_root() / "epubgen" / "config.json"


def load_prefs() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("ignoring unreadable user prefs at %s: %s", path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    if data.get("version") != _VERSION:
        return {}
    return data


def save_prefs(prefs: dict[str, Any]) -> None:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": _VERSION, **{k: v for k, v in prefs.items() if k != "version"}}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def get_default_model() -> str:
    return load_prefs().get("default_model") or _BUILTIN_DEFAULT_MODEL


def set_default_model(model: str) -> None:
    prefs = load_prefs()
    if prefs.get("default_model") == model:
        return  # no-op write avoidance
    prefs["default_model"] = model
    with contextlib.suppress(OSError):
        save_prefs(prefs)
