from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from epubgen.images import COVER_SIZE, generate_image, is_available
from epubgen.schema import Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_text

PALETTES = {
    "oreilly": ("#003a5d", "#f4ecd8"),
    "manning": ("#2a4d3a", "#f0f4ef"),
    "pragprog": ("#a32638", "#fbeef0"),
    "nostarch": ("#111111", "#fafafa"),
    "apress": ("#1a3a6c", "#f3f5f9"),
    "for-dummies": ("#f8b400", "#000000"),
    "cheatsheet": ("#00897b", "#f0f4f3"),
    "pocket-reference": ("#5d4037", "#f5f1ec"),
    "academic": ("#222222", "#fafafa"),
    "penguin-classics": ("#ea5b3c", "#f6efde"),
}


def _svg_cover(outline: Outline, style: Style) -> str:
    fg, bg = PALETTES.get(style.name, ("#222", "#eee"))
    title = escape(outline.title)
    subtitle = escape(outline.subtitle or outline.topic)
    author = escape(outline.author)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 2400" preserveAspectRatio="xMidYMid meet">
  <rect width="1600" height="2400" fill="{bg}"/>
  <rect x="0" y="0" width="1600" height="240" fill="{fg}"/>
  <rect x="0" y="2160" width="1600" height="240" fill="{fg}"/>
  <text x="120" y="900" font-family="Georgia, serif" font-size="140" font-weight="bold" fill="{fg}">
    {title}
  </text>
  <text x="120" y="1100" font-family="Georgia, serif" font-size="64" fill="{fg}" opacity="0.75">
    {subtitle}
  </text>
  <text x="120" y="2080" font-family="Helvetica, sans-serif" font-size="56" fill="{fg}">
    {author}
  </text>
</svg>
"""


def write_svg_cover(outline: Outline, style: Style, workdir: Path) -> Path:
    path = workdir / "cover.svg"
    atomic_write_text(path, _svg_cover(outline, style))
    return path


def generate_cover(
    outline: Outline, style: Style, workdir: Path, prompt: str | None = None
) -> Path:
    if prompt is not None and is_available():
        png = workdir / "cover.png"
        if generate_image(prompt, png, size=COVER_SIZE):
            return png
    return write_svg_cover(outline, style, workdir)


def existing_cover(workdir: Path) -> Path | None:
    for ext in ("png", "jpg", "jpeg", "svg"):
        p = workdir / f"cover.{ext}"
        if p.exists():
            return p
    return None
