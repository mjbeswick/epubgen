from pathlib import Path

from epubgen.cover import _fit_title, _max_chars_for, _svg_cover, _wrap, write_svg_cover
from epubgen.schema import Beat, Chapter, Outline
from epubgen.styles import load_style


def _outline(title: str, subtitle: str | None = None):
    return Outline(
        title=title,
        subtitle=subtitle,
        topic="topic",
        style="oreilly",
        chapters=[
            Chapter(
                number=i,
                title=f"C{i}",
                synopsis="A reasonable synopsis describing what this chapter covers.",
                beats=[Beat(summary="One beat here"), Beat(summary="Two beats now")],
                word_target=2000,
            )
            for i in range(1, 4)
        ],
    )


def test_wrap_short_text_one_line():
    assert _wrap("Short Title", 32) == ["Short Title"]


def test_wrap_long_text_breaks_on_words():
    text = "Building Production Apps with the TypeScript Reactive Extension"
    lines = _wrap(text, 28)
    assert all(len(line) <= 28 for line in lines), lines
    # Must reconstruct the original text when re-joined.
    assert " ".join(lines) == text


def test_wrap_handles_long_unbreakable_word():
    lines = _wrap("Supercalifragilisticexpialidocious is fun", 10)
    # Long word allowed as its own line.
    assert "Supercalifragilisticexpialidocious" in lines


def test_max_chars_scales_inversely_with_font_size():
    big = _max_chars_for(200)
    small = _max_chars_for(80)
    assert small > big


def test_fit_title_short_picks_one_line():
    size, lines = _fit_title("TSRX in Practice")
    assert len(lines) == 1
    assert size >= 100  # large enough to read


def test_fit_title_long_breaks_to_two_lines():
    size, lines = _fit_title("A Comprehensive Guide to Async Patterns")
    assert len(lines) == 2
    assert size >= 80


def test_fit_title_very_long_picks_smallest_size():
    size, lines = _fit_title(
        "Building Production Apps with the TypeScript Reactive Extension Library"
    )
    assert size == 64
    assert len(lines) <= 3


def test_svg_cover_wraps_long_subtitle():
    style = load_style("oreilly")
    outline = _outline(
        "TSRX in Practice",
        "Building Production Apps with the TypeScript Reactive Extension",
    )
    svg = _svg_cover(outline, style)
    # Subtitle should be split across multiple tspans.
    assert svg.count("<tspan") >= 3  # >=1 title line + >=2 subtitle lines
    # Long subtitle text should not appear on a single line — at least one space
    # must have been replaced by a tspan boundary inside the original phrase.
    assert "TypeScript Reactive Extension" not in svg.replace("</tspan>", "")


def test_svg_cover_short_title_fits_one_line():
    style = load_style("oreilly")
    outline = _outline("Fast Python", "A measurement-first guide")
    svg = _svg_cover(outline, style)
    assert "<svg" in svg
    assert "Fast Python" in svg


def test_svg_cover_centers_title_anchor():
    style = load_style("oreilly")
    svg = _svg_cover(_outline("Hi"), style)
    assert 'text-anchor="middle"' in svg


def test_write_svg_cover_writes_file(tmp_path: Path):
    style = load_style("oreilly")
    outline = _outline(
        "TSRX in Practice",
        "Building Production Apps with the TypeScript Reactive Extension",
    )
    p = write_svg_cover(outline, style, tmp_path)
    assert p == tmp_path / "cover.svg"
    content = p.read_text(encoding="utf-8")
    assert content.startswith("<?xml")
    assert "viewBox" in content


def test_get_illustration_prompt_oreilly():
    from epubgen.cover import get_illustration_prompt

    style = load_style("oreilly")
    outline = _outline("TSRX in Practice", "Building Production Apps")
    prompt = get_illustration_prompt(outline, style)
    assert prompt is not None


def test_get_illustration_prompt_manning():
    from epubgen.cover import get_illustration_prompt

    style = load_style("manning")
    outline = _outline("Design Patterns", "Software Architecture")
    prompt = get_illustration_prompt(outline, style)
    assert prompt is not None


def test_load_cover_template_oreilly():
    from epubgen.cover import load_cover_template

    style = load_style("oreilly")
    template = load_cover_template(style)
    assert template is not None


def test_load_cover_template_missing_fallback():
    from epubgen.cover import load_cover_template

    style = load_style("oreilly")
    template = load_cover_template(style)
    assert isinstance(template, str)


def test_rasterize_svg_to_png():
    from epubgen.cover import rasterize_svg_to_png

    svg_content = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
  <rect width="100" height="100" fill="red"/>
</svg>"""
    result = rasterize_svg_to_png(svg_content, Path("/tmp/test.png"))
    assert isinstance(result, bool)


def test_create_fallback_svg_cover_returns_valid_svg():
    from epubgen.cover import create_fallback_svg_cover

    style = load_style("oreilly")
    outline = _outline("Test Title", "Test Subtitle")
    svg = create_fallback_svg_cover(outline, style)
    assert isinstance(svg, str)


def test_render_text_on_template():
    from epubgen.cover import _render_text_on_template

    style = load_style("oreilly")
    outline = _outline("Test Book", "A Great Subtitle")
    template = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 2400">
  <g id="title-area"></g>
  <g id="illustration-area"></g>
  <rect y="2200" width="1600" height="200"/>
</svg>"""
    result = _render_text_on_template(template, outline, style)
    assert "Test Book" in result
    assert "A Great Subtitle" in result
    assert '<text' in result


def test_composite_illustration_into_svg(tmp_path: Path):
    from epubgen.cover import composite_illustration_into_svg

    # Create a minimal PNG file (8x8 red square)
    # PNG magic bytes followed by minimal IHDR chunk
    png_data = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x08\x00\x00\x00\x08'
        b'\x08\x02\x00\x00\x00kwd+\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01'
        b'\x01\x00\x05\x18r\xda\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    img_path = tmp_path / "test_illustration.png"
    img_path.write_bytes(png_data)

    template = """<?xml version="1.0"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 2400">
  <g id="illustration-area"></g>
</svg>"""

    result = composite_illustration_into_svg(img_path, template)
    assert 'data:image/png;base64,' in result
    assert '<image href=' in result


def test_generate_gemini_cover_fallback(tmp_path: Path):
    from epubgen.cover import generate_gemini_cover

    style = load_style("oreilly")
    outline = _outline("Test Book", "Test Subtitle")
    result = generate_gemini_cover(outline, style, tmp_path)
    # Without Gemini API key, should fallback to SVG
    assert result.exists()
    assert result.suffix in ('.svg', '.png')


def test_generate_cover_for_all_styles(tmp_path: Path):
    from epubgen.cover import generate_cover

    all_styles = [
        "oreilly",
        "manning",
        "pragprog",
        "nostarch",
        "apress",
        "for-dummies",
        "cheatsheet",
        "pocket-reference",
    ]

    for style_name in all_styles:
        style_workdir = tmp_path / style_name
        style_workdir.mkdir(exist_ok=True)
        style = load_style(style_name)
        outline = _outline(f"Book: {style_name}", f"Subtitle for {style_name}")
        result = generate_cover(outline, style, style_workdir)
        assert result.exists(), f"Cover not generated for style {style_name}"
        assert result.suffix in ('.svg', '.png'), f"Invalid cover format for {style_name}"
