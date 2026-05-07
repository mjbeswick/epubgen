from pathlib import Path

from epubgen.colophon import build_colophon_md, write_colophon
from epubgen.schema import Beat, Chapter, Outline


def _outline():
    return Outline(
        title="The Art of Doing Things",
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


def test_colophon_includes_disclaimer_and_book_title():
    md = build_colophon_md(_outline(), "oreilly", author="Mike")
    assert "The Art of Doing Things" in md
    assert "Mike" in md
    assert "not produced by, affiliated with" in md
    # Generic tradition descriptor, no publisher names.
    assert "code-forward" in md
    assert "O'Reilly" not in md
    assert "OReilly" not in md


def test_colophon_for_unknown_style_uses_fallback():
    md = build_colophon_md(_outline(), "made-up-style", author="x")
    assert "general technical publishing" in md


def test_write_colophon_creates_file(tmp_path: Path):
    p = write_colophon(_outline(), "oreilly", author="x", workdir=tmp_path)
    assert p == tmp_path / "colophon.md"
    assert p.read_text(encoding="utf-8").startswith("# About This Book")


def test_anti_attribution_used_in_every_relevant_prompt():
    from epubgen.prompts.chapter import build_chapter_messages
    from epubgen.prompts.description import build_description_messages
    from epubgen.prompts.outline import build_outline_messages
    from epubgen.prompts.refine import build_refine_messages
    from epubgen.schema import Options, RefinedTopic
    from epubgen.styles import load_style

    style = load_style("oreilly")
    opts = Options(topic="t", style="oreilly", out=Path("/tmp/x.epub"))
    outline = _outline()
    framing = RefinedTopic(
        title="A Title",
        subtitle="a clarifying subtitle",
        angle="distinguishing this framing from the others meaningfully.",
    )

    msgs_o = build_outline_messages(style, opts)
    msgs_c = build_chapter_messages(style, outline, outline.chapters[0], opts)
    msgs_r = build_refine_messages(style, "topic")
    msgs_d = build_description_messages(style, "topic", framing)

    cases = [
        ("outline", msgs_o),
        ("chapter", msgs_c),
        ("refine", msgs_r),
        ("desc", msgs_d),
    ]
    for label, m in cases:
        text = " ".join(b["text"] for b in m["system"])
        assert "Do NOT name" in text, f"{label} missing anti-attribution clause"
