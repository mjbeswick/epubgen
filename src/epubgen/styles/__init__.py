from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from epubgen.errors import ConfigError

REQUIRED_SECTIONS = ("## Voice", "## Structure", "## Formatting", "## Length")

DEFAULT_NAMES = (
    "oreilly",
    "manning",
    "pragprog",
    "nostarch",
    "apress",
    "for-dummies",
    "cheatsheet",
    "pocket-reference",
)
EXTRA_NAMES = ("academic", "penguin-classics")

ONELINERS = {
    "oreilly": "Pragmatic, code-forward — assumes intermediate readers.",
    "manning": "In Action — drops you into a scenario before the theory.",
    "pragprog": "Opinionated and tip-driven; treats you like a peer.",
    "nostarch": "Build something. The book is a guided project.",
    "apress": "Reference-thorough; closer to a manual.",
    "for-dummies": "Friendly, icon-heavy, zero assumed knowledge.",
    "cheatsheet": "Telegraphic cards — scan, don't read. Tables and snippets.",
    "pocket-reference": "Manual-style entries: synopsis, params, example, see-also.",
    "academic": "Formal, citation-aware, structured argumentation.",
    "penguin-classics": "Literary; long-form prose. (Off-genre for tech books.)",
}


@dataclass(frozen=True)
class Style:
    name: str
    guide: str
    css: str
    oneliner: str


def _root() -> Path:
    return Path(str(files("epubgen") / "styles"))


def _candidate_paths(name: str, ext: str) -> list[Path]:
    root = _root()
    return [root / f"{name}.{ext}", root / "extras" / f"{name}.{ext}"]


def load_style(name: str) -> Style:
    md_path = next((p for p in _candidate_paths(name, "md") if p.exists()), None)
    css_path = next((p for p in _candidate_paths(name, "css") if p.exists()), None)
    if md_path is None or css_path is None:
        raise ConfigError(f"unknown style: {name}")
    guide = md_path.read_text(encoding="utf-8")
    missing = [s for s in REQUIRED_SECTIONS if s not in guide]
    if missing:
        raise ConfigError(f"style {name!r} missing sections: {missing}")
    return Style(name=name, guide=guide, css=css_path.read_text(encoding="utf-8"),
                 oneliner=ONELINERS.get(name, ""))


def list_default_styles() -> list[tuple[str, str]]:
    return [(n, ONELINERS[n]) for n in DEFAULT_NAMES]


def list_all_styles() -> list[tuple[str, str]]:
    return [(n, ONELINERS[n]) for n in DEFAULT_NAMES + EXTRA_NAMES]
