import contextlib
import shutil
import zipfile
from pathlib import Path

import pytest

from epubgen import anthropic_client, pipeline
from epubgen.schema import Options
from tests.fixtures.fake_anthropic import FakeAnthropic, text_response, tool_response
from tests.test_outline import VALID_PAYLOAD


def _has_pandoc() -> bool:
    return shutil.which("pandoc") is not None


def _handler(req):
    if "tools" in req:
        return tool_response(VALID_PAYLOAD)
    user = req["messages"][-1]["content"]
    # Crude chapter extraction.
    n = 1
    for piece in user.split():
        if piece.startswith("Chapter") or piece.startswith('"Chapter'):
            with contextlib.suppress(ValueError):
                n = int(piece.strip('":').split()[-1])
    return text_response(
        f"# Chapter {n}\n\nLorem ipsum chapter body.\n\n"
        "```python\nprint('hi')\n```\n",
        cache_read=200,
    )


@pytest.mark.skipif(not _has_pandoc(), reason="pandoc not installed")
def test_end_to_end_produces_valid_epub(tmp_path: Path):
    out = tmp_path / "book.epub"
    workdir = tmp_path / "work"
    opts = Options(
        topic="Python perf",
        style="oreilly",
        out=out,
        workdir=workdir,
        chapters=4,
        words=2500,
    )
    fake = FakeAnthropic(handler=_handler)
    anthropic_client.set_client(fake)
    try:
        pipeline.run(opts)
    finally:
        anthropic_client.set_client(None)

    assert out.exists()
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "mimetype" in names
        assert any(n.endswith("container.xml") for n in names)
        assert any(n.endswith(".opf") for n in names)
        # nav doc present
        assert any("nav" in n.lower() for n in names)
    # Resume idempotency: re-running should not regenerate chapters.
    chapters_before = sorted((workdir).glob("ch-*.md"))
    fake2 = FakeAnthropic(handler=_handler)
    anthropic_client.set_client(fake2)
    try:
        pipeline.run(opts)
    finally:
        anthropic_client.set_client(None)
    chapters_after = sorted((workdir).glob("ch-*.md"))
    assert chapters_before == chapters_after
    # No new chapter generation calls (only outline reused from disk too).
    assert len(fake2.messages.calls) == 0


def test_cover_svg_fallback(tmp_path: Path):
    from epubgen.cover import write_svg_cover
    from epubgen.schema import Beat, Chapter, Outline
    from epubgen.styles import load_style

    outline = Outline(
        title="X",
        topic="t",
        style="oreilly",
        chapters=[
            Chapter(
                number=i,
                title=f"C{i}",
                synopsis="A reasonable synopsis describing what this chapter covers.",
                beats=[Beat(summary="One beat here"), Beat(summary="Second beat here")],
                word_target=2000,
            )
            for i in range(1, 4)
        ],
    )
    style = load_style("oreilly")
    p = write_svg_cover(outline, style, tmp_path)
    assert p.exists()
    assert p.read_text().startswith("<?xml")
