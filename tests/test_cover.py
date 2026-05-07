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
