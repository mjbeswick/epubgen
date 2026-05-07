from __future__ import annotations

import datetime
from pathlib import Path

from epubgen.schema import Outline
from epubgen.workdir import atomic_write_text

# Generic descriptors per style — used in the colophon disclaimer so the book
# acknowledges the tradition without naming a specific publisher.
_TRADITIONS = {
    "oreilly": "practical, code-forward technical publishing",
    "manning": "scenario-driven 'in action'-style technical books",
    "pragprog": "opinionated programmer's-perspective books",
    "nostarch": "project-driven hands-on books",
    "apress": "comprehensive, reference-leaning technical manuals",
    "for-dummies": "approachable beginner's guides",
    "cheatsheet": "telegraphic quick-reference cards",
    "pocket-reference": "manual-style pocket references",
    "academic": "academic monographs",
    "penguin-classics": "literary editions of long-form prose",
}


def build_colophon_md(outline: Outline, style_name: str, *, author: str) -> str:
    tradition = _TRADITIONS.get(style_name, "general technical publishing")
    today = datetime.date.today().isoformat()
    return (
        "# About This Book\n\n"
        f"*{outline.title}* was generated with **epubgen**, an open-source tool that "
        "produces EPUB books from a topic and a style guide using a large language "
        "model.\n\n"
        f"The editorial style is drawn from the conventions of {tradition}. "
        "**This work is not produced by, affiliated with, sponsored by, or endorsed by "
        "any specific publisher, imprint, or brand.** Any resemblance to a particular "
        "publisher's titles is stylistic only.\n\n"
        f"Generated on {today}.\n\n"
        f"Author: {author}.\n"
    )


def write_colophon(outline: Outline, style_name: str, *, author: str, workdir: Path) -> Path:
    path = workdir / "colophon.md"
    atomic_write_text(path, build_colophon_md(outline, style_name, author=author))
    return path
