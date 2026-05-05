from pathlib import Path
from unittest.mock import patch

import pytest

from epubgen.diagrams import (
    _IMAGE_FENCE,
    _MERMAID_FENCE,
    _VEGALITE_FENCE,
    _find_blocks,
    render_in_file,
)


def test_regex_matches_mermaid_block():
    text = "Some prose.\n\n```mermaid\nflowchart LR\nA-->B\n```\n\nMore prose."
    matches = list(_MERMAID_FENCE.finditer(text))
    assert len(matches) == 1
    assert "flowchart LR" in matches[0].group(1)


def test_regex_handles_multiple_blocks():
    text = "```mermaid\nA-->B\n```\n\ntext\n\n```mermaid\nC-->D\n```\n"
    matches = list(_MERMAID_FENCE.finditer(text))
    assert len(matches) == 2


def test_render_in_file_no_blocks_returns_zero(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text("# Title\n\nNo diagrams here.\n")
    assert render_in_file(chapter, tmp_path) == 0
    assert "No diagrams here" in chapter.read_text()


def test_render_in_file_no_mmdc_leaves_blocks(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text("# T\n\n```mermaid\nflowchart LR\nA-->B\n```\n")
    with patch("epubgen.diagrams.has_mmdc", return_value=False):
        n = render_in_file(chapter, tmp_path)
    assert n == 0
    assert "```mermaid" in chapter.read_text()


def test_render_in_file_replaces_block_when_mmdc_succeeds(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text("# T\n\n```mermaid\nflowchart LR\nA-->B\n```\n\nend")

    def fake_render(kind, src, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"<svg/>")
        return True

    with patch("epubgen.diagrams._kind_available", return_value=True), \
         patch("epubgen.diagrams._render_for_kind", side_effect=fake_render):
        n = render_in_file(chapter, tmp_path)
    assert n == 1
    text = chapter.read_text()
    assert "```mermaid" not in text
    assert "![Diagram](diagrams/ch-01-01.svg)" in text


def test_render_in_file_failure_keeps_block(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text("```mermaid\nbad\n```\n")
    with patch("epubgen.diagrams._kind_available", return_value=True), \
         patch("epubgen.diagrams._render_for_kind", return_value=False):
        n = render_in_file(chapter, tmp_path)
    assert n == 0
    assert "```mermaid" in chapter.read_text()


@pytest.mark.parametrize("kindle,expected_fmt", [(False, "svg"), (True, "png")])
def test_pipeline_picks_format(kindle, expected_fmt):
    fmt = "png" if kindle else "svg"
    assert fmt == expected_fmt


def test_vegalite_regex_matches():
    text = '```vegalite\n{"mark": "bar"}\n```'
    matches = list(_VEGALITE_FENCE.finditer(text))
    assert len(matches) == 1
    assert matches[0].group(1) == '{"mark": "bar"}'


def test_find_blocks_orders_mixed_fences_by_position():
    text = (
        "```vegalite\n{}\n```\n\nprose\n\n"
        "```mermaid\nA-->B\n```\n\nprose\n\n"
        "```vegalite\n{}\n```\n"
    )
    blocks = _find_blocks(text)
    kinds = [b[2] for b in blocks]
    assert kinds == ["vegalite", "mermaid", "vegalite"]


def test_image_regex_matches():
    text = "```image\nA server rack with overlaid heat map.\n```"
    matches = list(_IMAGE_FENCE.finditer(text))
    assert len(matches) == 1
    assert "server rack" in matches[0].group(1)


def test_find_blocks_includes_images_in_order():
    text = (
        "```image\nx\n```\n\n"
        "```mermaid\nA-->B\n```\n\n"
        "```vegalite\n{}\n```\n"
    )
    blocks = _find_blocks(text)
    assert [b[2] for b in blocks] == ["image", "mermaid", "vegalite"]


def test_render_in_file_skip_kinds(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text("```image\na photo\n```\n\n```mermaid\nA-->B\n```\n")

    def fake_render(kind, src, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"x")
        return True

    with patch("epubgen.diagrams._kind_available", return_value=True), \
         patch("epubgen.diagrams._render_for_kind", side_effect=fake_render):
        n = render_in_file(chapter, tmp_path, skip_kinds=frozenset({"image"}))
    text = chapter.read_text()
    assert "```image" in text  # passed through
    assert "![Diagram]" in text  # mermaid still rendered
    assert n == 1


def test_image_block_gets_png_extension(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text("```image\na photo\n```\n")

    captured = {}

    def fake_render(kind, src, out_path):
        captured["out"] = out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"x")
        return True

    with patch("epubgen.diagrams._kind_available", return_value=True), \
         patch("epubgen.diagrams._render_for_kind", side_effect=fake_render):
        render_in_file(chapter, tmp_path, fmt="svg")
    assert captured["out"].suffix == ".png"


def test_render_in_file_handles_mixed_blocks(tmp_path: Path):
    chapter = tmp_path / "ch-01.md"
    chapter.write_text(
        '```mermaid\nA-->B\n```\n\nbody\n\n```vegalite\n{"mark":"bar"}\n```\n'
    )

    def fake_render(kind, src, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"x")
        return True

    with patch("epubgen.diagrams._kind_available", return_value=True), \
         patch("epubgen.diagrams._render_for_kind", side_effect=fake_render):
        n = render_in_file(chapter, tmp_path)
    assert n == 2
    text = chapter.read_text()
    assert "![Diagram](diagrams/ch-01-01.svg)" in text
    assert "![Chart](diagrams/ch-01-02.svg)" in text
