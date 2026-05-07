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


CANVAS_W = 1600
CANVAS_H = 2400
SIDE_PAD = 140  # left/right padding inside the inner area
INNER_W = CANVAS_W - 2 * SIDE_PAD


def _wrap(text: str, max_chars: int) -> list[str]:
    """Greedy word wrap. Single words longer than max_chars get their own line."""
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip() if cur else w
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


_TITLE_SIZES = (220, 180, 150, 120, 96, 80, 64)


def _max_chars_for(font_size: int, *, ratio: float = 0.55) -> int:
    """Approximate characters that fit on one line given a Georgia-ish font size."""
    return max(8, int(INNER_W / (font_size * ratio)))


def _fit_title(title: str) -> tuple[int, list[str]]:
    """Pick the largest title size that fits in one line; else fewest lines."""
    best: tuple[int, list[str]] | None = None
    for size in _TITLE_SIZES:
        lines = _wrap(title, _max_chars_for(size, ratio=0.55))
        if best is None or len(lines) < len(best[1]):
            best = (size, lines)
        if best[1] == lines and len(lines) == 1:
            return best
    assert best is not None
    return best


def _build_tspans(
    lines: list[str], *, x: int, line_height: float, first_dy: float = 0.0
) -> str:
    out = []
    for i, line in enumerate(lines):
        dy = first_dy if i == 0 else line_height
        out.append(f'<tspan x="{x}" dy="{dy:.0f}">{escape(line)}</tspan>')
    return "".join(out)


def _svg_cover(outline: Outline, style: Style) -> str:
    fg, bg = PALETTES.get(style.name, ("#222", "#eee"))
    title = outline.title
    subtitle = outline.subtitle or outline.topic
    author = outline.author

    title_size, title_lines = _fit_title(title)

    subtitle_size = 56
    subtitle_lines = _wrap(subtitle, _max_chars_for(subtitle_size, ratio=0.50))[:3]

    cx = CANVAS_W // 2
    title_lh = title_size * 1.1
    subtitle_lh = subtitle_size * 1.3

    # Stack vertically centered around y=1080.
    title_block_h = len(title_lines) * title_lh
    subtitle_block_h = len(subtitle_lines) * subtitle_lh
    rule_gap = 60

    total_h = title_block_h + rule_gap + subtitle_block_h
    block_top = (CANVAS_H - total_h) / 2 - 100  # bias slightly above center

    title_baseline = block_top + title_size * 0.85
    subtitle_baseline = (
        block_top + title_block_h + rule_gap + subtitle_size * 0.85
    )
    rule_y = block_top + title_block_h + rule_gap / 2
    rule_w = 240

    title_tspans = _build_tspans(title_lines, x=cx, line_height=title_lh)
    subtitle_tspans = _build_tspans(subtitle_lines, x=cx, line_height=subtitle_lh)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg"
     viewBox="0 0 {CANVAS_W} {CANVAS_H}"
     preserveAspectRatio="xMidYMid meet">
  <rect width="{CANVAS_W}" height="{CANVAS_H}" fill="{bg}"/>
  <rect x="0" y="0" width="{CANVAS_W}" height="200" fill="{fg}"/>
  <rect x="0" y="{CANVAS_H - 200}" width="{CANVAS_W}" height="200" fill="{fg}"/>
  <text x="{cx}" y="{title_baseline:.0f}" text-anchor="middle"
        font-family="Georgia, 'Times New Roman', serif"
        font-size="{title_size}" font-weight="bold" fill="{fg}">{title_tspans}</text>
  <line x1="{cx - rule_w // 2}" y1="{rule_y:.0f}"
        x2="{cx + rule_w // 2}" y2="{rule_y:.0f}"
        stroke="{fg}" stroke-width="3" opacity="0.55"/>
  <text x="{cx}" y="{subtitle_baseline:.0f}" text-anchor="middle"
        font-family="Georgia, 'Times New Roman', serif"
        font-size="{subtitle_size}" fill="{fg}"
        opacity="0.78">{subtitle_tspans}</text>
  <text x="{cx}" y="{CANVAS_H - 250}" text-anchor="middle"
        font-family="'Helvetica Neue', Helvetica, Arial, sans-serif"
        font-size="44" fill="{fg}" opacity="0.55"
        letter-spacing="6">{escape(author).upper()}</text>
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
