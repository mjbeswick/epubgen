from __future__ import annotations

import os
from pathlib import Path
from xml.sax.saxutils import escape

from epubgen.errors import CoverError
from epubgen.schema import Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_bytes, atomic_write_text

PALETTES = {
    "oreilly": ("#003a5d", "#f4ecd8"),
    "manning": ("#2a4d3a", "#f0f4ef"),
    "pragprog": ("#a32638", "#fbeef0"),
    "nostarch": ("#111111", "#fafafa"),
    "apress": ("#1a3a6c", "#f3f5f9"),
    "for-dummies": ("#f8b400", "#000000"),
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


def _try_openai_cover(prompt: str, workdir: Path) -> Path | None:
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    try:
        client = OpenAI()
        result = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
        )
        import base64

        b64 = result.data[0].b64_json
        if not b64:
            return None
        path = workdir / "cover.png"
        atomic_write_bytes(path, base64.b64decode(b64))
        return path
    except Exception as e:
        raise CoverError(f"openai cover generation failed: {e}") from e


def generate_cover(
    outline: Outline, style: Style, workdir: Path, prompt: str | None = None
) -> Path:
    if prompt is not None:
        try:
            png = _try_openai_cover(prompt, workdir)
            if png is not None:
                return png
        except CoverError:
            # Degrade to SVG fallback rather than failing the run.
            pass
    return write_svg_cover(outline, style, workdir)


def existing_cover(workdir: Path) -> Path | None:
    for ext in ("png", "jpg", "jpeg", "svg"):
        p = workdir / f"cover.{ext}"
        if p.exists():
            return p
    return None
