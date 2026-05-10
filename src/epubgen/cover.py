from __future__ import annotations

import logging
from pathlib import Path
from xml.sax.saxutils import escape

from epubgen.images import COVER_SIZE, generate_image, is_available
from epubgen.schema import Outline
from epubgen.styles import Style
from epubgen.workdir import atomic_write_text

# Use context-mode for Gemini integration
HAS_GOOGLE_GENAI = False
try:
    from google import genai

    HAS_GOOGLE_GENAI = True
except ImportError:
    pass

logger = logging.getLogger(__name__)

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
    """Generate a cover using the new template-based approach with fallbacks.

    1. Try to use style-specific SVG template with Gemini image generation
    2. Fallback to OpenAI image generation if available
    3. Fallback to basic SVG cover
    """
    # Try the new template-based approach first
    try:
        return generate_gemini_cover(outline, style, workdir, prompt=prompt)
    except Exception as e:
        logger.warning("template-based cover generation failed: %s; falling back to OpenAI", e)

    # Fallback to OpenAI-based approach
    if prompt is not None and is_available():
        png = workdir / "cover.png"
        if generate_image(prompt, png, size=COVER_SIZE):
            return png

    # Final fallback to basic SVG
    return write_svg_cover(outline, style, workdir)


def existing_cover(workdir: Path) -> Path | None:
    for ext in ("png", "jpg", "jpeg", "svg"):
        p = workdir / f"cover.{ext}"
        if p.exists():
            return p
    return None


def get_illustration_prompt(outline: Outline, style: Style) -> str:
    """Generate an illustration prompt based on the outline and style."""
    # Extract the "## Cover Illustration Voice" section from the style guide
    style_content = style.guide
    if "## Cover Illustration Voice" in style_content:
        start = style_content.index("## Cover Illustration Voice") + len(
            "## Cover Illustration Voice"
        )
        # Find the next ## section or end of file
        next_section = style_content.find("\n## ", start)
        if next_section == -1:
            voice = style_content[start:].strip()
        else:
            voice = style_content[start:next_section].strip()
        # Replace [TOPIC] placeholder with the actual topic
        voice = voice.replace("[TOPIC]", outline.topic)
        return voice
    else:
        # Fallback: generic prompt if no voice is defined
        return f"Illustration for a book about {outline.topic}, in professional style"


def load_cover_template(style: Style) -> str:
    """Load SVG template for the given style, with fallback."""
    from importlib.resources import files

    try:
        # Try to load style-specific template
        styles_dir = Path(str(files("epubgen") / "styles"))
        template_path = styles_dir / f"{style.name}-cover.svg"
        if template_path.exists():
            return template_path.read_text(encoding="utf-8")
    except (AttributeError, FileNotFoundError, Exception):
        pass
    # Fallback to a simple generated SVG
    from epubgen.schema import Beat, Chapter

    return _svg_cover(
        Outline(
            title="[TITLE]",
            subtitle="[SUBTITLE]",
            topic="[TOPIC]",
            style=style.name,
            chapters=[
                Chapter(
                    number=i,
                    title=f"Chapter {i}",
                    synopsis="This is a placeholder chapter.",
                    beats=[
                        Beat(summary="First beat"),
                        Beat(summary="Second beat"),
                    ],
                    word_target=1000,
                )
                for i in range(1, 4)
            ],
        ),
        style,
    )


def create_fallback_svg_cover(outline: Outline, style: Style) -> str:
    """Create a fallback SVG cover when illustration generation fails."""
    return _svg_cover(outline, style)


def composite_illustration_into_svg(
    illustration_path: Path, template_svg: str
) -> str:
    """Composite a raster illustration into an SVG template.

    For now, this appends the image as a raster element into the template.
    """
    if not illustration_path.exists():
        logger.warning(f"Illustration not found: {illustration_path}")
        return template_svg

    # Embed the illustration as a base64 PNG in the SVG
    import base64

    image_data = illustration_path.read_bytes()
    b64_data = base64.b64encode(image_data).decode("ascii")
    mime_type = "image/png"

    # Find the illustration placeholder and replace it
    if '<g id="illustration-area"' in template_svg:
        # Insert image before the closing </g>
        image_elem = f'<image href="data:{mime_type};base64,{b64_data}" width="1024" height="1024" x="288" y="588"/>'
        template_svg = template_svg.replace(
            '<g id="illustration-area">',
            f'<g id="illustration-area">{image_elem}',
        )
    return template_svg


def rasterize_svg_to_png(svg_content: str, output_path: Path) -> bool:
    """Rasterize an SVG string to a PNG file.

    Returns True if successful, False otherwise.
    """
    try:
        import io
        from PIL import Image

        # Try using cairosvg if available
        try:
            import cairosvg

            png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))
            output_path.write_bytes(png_bytes)
            return True
        except ImportError:
            pass

        # Fallback: use a simple approach with PIL if possible
        # This is a simplified version that might not handle all SVG features
        logger.warning(
            "cairosvg not available; PNG rasterization may produce low-quality results"
        )

        # For now, return False if cairosvg is not available
        # (Full SVG-to-PNG conversion requires specialized libs)
        return False
    except Exception as e:
        logger.error(f"Failed to rasterize SVG: {e}")
        return False


def _render_text_on_template(
    template_svg: str, outline: Outline, style: Style
) -> str:
    """Add title, subtitle, and author text to an SVG template."""
    svg = template_svg

    # Inject title text (if template has a title-area group)
    title = f'<text x="400" y="900" font-family="Georgia, serif" font-size="72" fill="#003a5d" font-weight="bold">{escape(outline.title)}</text>'
    if '<g id="title-area"' in svg:
        svg = svg.replace('<g id="title-area"', f'<g id="title-area">{title}')

    # Inject subtitle text
    subtitle = outline.subtitle or outline.topic
    subtitle_text = f'<text x="400" y="1100" font-family="Georgia, serif" font-size="44" fill="#003a5d" opacity="0.8">{escape(subtitle)}</text>'
    if '<g id="title-area"' in svg:
        svg = svg.replace('</g>', f'{subtitle_text}</g>', 1)  # Close the title-area group

    # Inject author text in footer
    author_text = f'<text x="1500" y="2320" text-anchor="end" font-family="Arial, sans-serif" font-size="36" fill="#f4ecd8">{escape(outline.author).upper()}</text>'
    if '<rect' in svg and 'y="2200"' in svg:
        # Insert before closing svg tag
        svg = svg.replace('</svg>', f'{author_text}</svg>')

    return svg


def generate_gemini_cover(
    outline: Outline, style: Style, workdir: Path, prompt: str | None = None
) -> Path:
    """Generate a cover illustration via Gemini and composite it into the template.

    Falls back to a simple SVG cover if generation fails.

    Workflow:
    1. Try to load style-specific SVG template
    2. Generate illustration via Gemini (if available) or placeholder
    3. Composite illustration into template
    4. Render title/subtitle/author text onto the composite
    5. Rasterize SVG to PNG (if cairosvg available)
    6. Fallback to SVG if PNG generation fails
    """
    if prompt is None:
        prompt = get_illustration_prompt(outline, style)

    # Load style-specific template (will fallback to generated SVG if not found)
    template_svg = load_cover_template(style)

    # Add text to template
    template_with_text = _render_text_on_template(template_svg, outline, style)

    # Generate illustration via Gemini if available
    if HAS_GOOGLE_GENAI and __import__("os").environ.get("GOOGLE_API_KEY"):
        illustration_path = workdir / "cover-illustration.png"
        if _generate_image_via_gemini(prompt, illustration_path):
            template_with_text = composite_illustration_into_svg(illustration_path, template_with_text)

    # Try to rasterize to PNG
    png_path = workdir / "cover.png"
    if rasterize_svg_to_png(template_with_text, png_path):
        return png_path

    # Fallback to SVG
    svg_path = workdir / "cover.svg"
    atomic_write_text(svg_path, template_with_text)
    return svg_path


def _generate_image_via_gemini(prompt: str, output_path: Path) -> bool:
    """Generate an image via Google Gemini 2.0 API.

    Returns True on success, False on any failure.
    """
    if not HAS_GOOGLE_GENAI:
        logger.warning("google-genai not installed; skipping Gemini image generation")
        return False

    try:
        import os

        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GOOGLE_API_KEY/GEMINI_API_KEY not set; skipping image generation")
            return False

        client = genai.Client(api_key=api_key)

        # Call Gemini 2.0 image generation (requires gemini-2.0-flash-001 or later)
        response = client.models.generate_images(
            model="gemini-2.0-flash-001",
            prompt=prompt,
            config={
                "candidate_count": 1,
                "safety_settings": [{"category": "HARM_CATEGORY_UNSPECIFIED", "threshold": "BLOCK_NONE"}],
                "generation_config": {"width": 1024, "height": 1024},
            },
        )

        if response.images:
            image_data = response.images[0]._image_bytes
            output_path.write_bytes(image_data)
            logger.info("Gemini image generated: %s", output_path)
            return True
        else:
            logger.warning("Gemini returned no images for prompt: %r", prompt[:80])
            return False

    except Exception as e:
        logger.warning("Gemini image generation failed: %s", e)
        return False
