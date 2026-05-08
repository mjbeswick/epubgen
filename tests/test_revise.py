from __future__ import annotations

from pathlib import Path

from epubgen.prompts.chapter import build_revise_messages
from epubgen.schema import Beat, Chapter, Options, Outline
from epubgen.styles import load_style


def _opts(**kw):
    return Options(topic="t", style="oreilly", out=Path("/tmp/x.epub"), **kw)


def _outline() -> Outline:
    return Outline(
        title="T", topic="t", style="oreilly",
        chapters=[
            Chapter(
                number=i, title=f"C{i}",
                synopsis="A sufficiently long synopsis for validation.",
                beats=[
                    Beat(summary="first beat summary"),
                    Beat(summary="second beat summary"),
                ],
                word_target=2500,
            )
            for i in (1, 2, 3)
        ],
    )


def test_revise_includes_current_text():
    style = load_style("oreilly")
    outline = _outline()
    msg = build_revise_messages(
        style, outline, outline.chapters[0],
        current_text="# C1\n\nexisting body\n",
        instruction="add a section on retries",
        opts=_opts(),
    )
    user = msg["messages"][0]["content"]
    assert "existing body" in user
    assert "add a section on retries" in user
    assert "<<<" in user and ">>>" in user


def test_revise_uses_three_cached_blocks_without_sources():
    style = load_style("oreilly")
    outline = _outline()
    msg = build_revise_messages(
        style, outline, outline.chapters[0],
        current_text="# C1\n", instruction="x", opts=_opts(),
    )
    cached = [b for b in msg["system"] if b.get("cache_control")]
    # style guide + outline (no sources)
    assert len(cached) == 2


def test_revise_with_sources_adds_third_cached_block():
    style = load_style("oreilly")
    outline = _outline()
    msg = build_revise_messages(
        style, outline, outline.chapters[0],
        current_text="# C1\n", instruction="x", opts=_opts(),
        sources_text="REF MATERIAL",
    )
    cached = [b for b in msg["system"] if b.get("cache_control")]
    assert len(cached) == 3
    assert any("REF MATERIAL" in b["text"] for b in msg["system"])


def test_revise_ereader_clause_only_when_enabled():
    style = load_style("oreilly")
    outline = _outline()
    on = build_revise_messages(
        style, outline, outline.chapters[0],
        current_text="# C1\n", instruction="x", opts=_opts(ereader=True),
    )["messages"][0]["content"]
    off = build_revise_messages(
        style, outline, outline.chapters[0],
        current_text="# C1\n", instruction="x", opts=_opts(ereader=False),
    )["messages"][0]["content"]
    assert "60 characters" in on
    assert "60 characters" not in off


def test_revise_user_prompt_demands_markdown_only():
    style = load_style("oreilly")
    outline = _outline()
    msg = build_revise_messages(
        style, outline, outline.chapters[0],
        current_text="# C1\n", instruction="x", opts=_opts(),
    )
    user = msg["messages"][0]["content"]
    assert "ONLY the revised chapter markdown" in user
