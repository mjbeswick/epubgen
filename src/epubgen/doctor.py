from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass

OK = "✓"
WARN = "!"
FAIL = "✗"


@dataclass
class Check:
    name: str
    status: str  # OK / WARN / FAIL
    detail: str
    fatal: bool = False


def _check_python() -> Check:
    major, minor = sys.version_info[:2]
    if (major, minor) < (3, 12):
        return Check(
            "python ≥ 3.12",
            FAIL,
            f"running on {major}.{minor}",
            fatal=True,
        )
    return Check("python ≥ 3.12", OK, f"{major}.{minor}.{sys.version_info.micro}")


def _check_anthropic_key() -> Check:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return Check("ANTHROPIC_API_KEY", FAIL, "not set", fatal=True)
    masked = f"{key[:7]}…{key[-4:]}" if len(key) > 12 else "set"
    return Check("ANTHROPIC_API_KEY", OK, masked)


def _check_pandoc() -> Check:
    path = shutil.which("pandoc")
    if not path:
        return Check(
            "pandoc",
            FAIL,
            "not on PATH (try: brew install pandoc)",
            fatal=True,
        )
    return Check("pandoc", OK, path)


def _check_kindlepreviewer() -> Check:
    path = shutil.which("kindlepreviewer")
    if not path:
        return Check(
            "kindlepreviewer",
            WARN,
            "not on PATH (optional; needed only for .azw3 output)",
        )
    return Check("kindlepreviewer", OK, path)


def _check_openai_key() -> Check:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        return Check(
            "OPENAI_API_KEY",
            WARN,
            "not set (optional; SVG cover fallback will be used)",
        )
    return Check("OPENAI_API_KEY", OK, "set")


def run_checks() -> list[Check]:
    return [
        _check_python(),
        _check_anthropic_key(),
        _check_pandoc(),
        _check_kindlepreviewer(),
        _check_openai_key(),
    ]


def fatal_checks(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.fatal and c.status == FAIL]


def format_checks(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = []
    for c in checks:
        lines.append(f"  {c.status} {c.name.ljust(width)}  {c.detail}")
    return "\n".join(lines)
