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


# Each entry: (env, label, is_llm_provider). LLM-provider keys count toward the
# "at least one provider must be set" check. Non-LLM keys are advisory only.
_PROVIDER_KEYS: list[tuple[str, str, bool]] = [
    ("ANTHROPIC_API_KEY",  "Anthropic provider",       True),
    ("OPENAI_API_KEY",     "OpenAI provider + cover image fallback", True),
    ("GOOGLE_API_KEY",     "Google Gemini provider",   True),
    ("GEMINI_API_KEY",     "Google Gemini (alt env)",  True),
    ("DEEPSEEK_API_KEY",   "DeepSeek provider",        True),
    ("OPENROUTER_API_KEY", "OpenRouter gateway",       True),
]


def _key_checks() -> list[Check]:
    out: list[Check] = []
    for env, label, _ in _PROVIDER_KEYS:
        key = os.environ.get(env)
        if not key:
            out.append(Check(env, WARN, f"not set (optional — {label})"))
        else:
            masked = f"{key[:7]}…{key[-4:]}" if len(key) > 12 else "set"
            out.append(Check(env, OK, masked))
    return out


def _llm_provider_check() -> Check:
    have = [env for env, _, is_llm in _PROVIDER_KEYS if is_llm and os.environ.get(env)]
    # Backward compat: missing ANTHROPIC_API_KEY alone (with no other keys) is fatal,
    # because that's the canonical default and existing scripts/tests rely on it.
    if not have:
        return Check(
            "ANTHROPIC_API_KEY",
            FAIL,
            "not set — need at least one provider key "
            "(Anthropic / OpenAI / Google / DeepSeek / OpenRouter)",
            fatal=True,
        )
    return Check(
        "LLM provider",
        OK,
        f"{len(have)} key(s) configured: {', '.join(have)}",
    )


def _check_pandoc() -> Check:
    path = shutil.which("pandoc")
    if not path:
        return Check(
            "pandoc",
            FAIL,
            "not on PATH (install: brew install pandoc / apt install pandoc)",
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


def _check_mmdc() -> Check:
    path = shutil.which("mmdc")
    if not path:
        return Check(
            "mmdc (mermaid-cli)",
            WARN,
            "not on PATH (optional; install: npm i -g @mermaid-js/mermaid-cli)",
        )
    return Check("mmdc (mermaid-cli)", OK, path)


def _check_vl_convert() -> Check:
    try:
        import vl_convert  # noqa: F401
    except ImportError:
        return Check(
            "vl-convert (charts)",
            WARN,
            "not installed (optional; vega-lite charts will be skipped)",
        )
    return Check("vl-convert (charts)", OK, "available")


def run_checks() -> list[Check]:
    checks: list[Check] = [_check_python(), _llm_provider_check()]
    checks.extend(_key_checks())
    checks.extend(
        [
            _check_pandoc(),
            _check_mmdc(),
            _check_vl_convert(),
            _check_kindlepreviewer(),
        ]
    )
    return checks


def fatal_checks(checks: list[Check]) -> list[Check]:
    return [c for c in checks if c.fatal and c.status == FAIL]


def format_checks(checks: list[Check]) -> str:
    width = max(len(c.name) for c in checks)
    lines = []
    for c in checks:
        lines.append(f"  {c.status} {c.name.ljust(width)}  {c.detail}")
    return "\n".join(lines)
