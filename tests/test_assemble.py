from pathlib import Path

import yaml

from epubgen.assemble import build_pandoc_args, metadata_yaml
from epubgen.schema import Beat, Chapter, Options, Outline


def _outline():
    return Outline(
        title="My Book",
        subtitle="A subtitle",
        topic="topic",
        style="oreilly",
        chapters=[
            Chapter(
                number=i,
                title=f"Chapter {i}",
                synopsis="A reasonable synopsis describing what this chapter covers.",
                beats=[Beat(summary="A beat one"), Beat(summary="A beat two")],
                word_target=3000,
            )
            for i in range(1, 4)
        ],
    )


def test_metadata_yaml_includes_user_metadata():
    opts = Options(topic="t", out=Path("/tmp/x.epub"), metadata={"isbn": "123"})
    text = metadata_yaml(_outline(), opts)
    parsed = yaml.safe_load(text)
    assert parsed["title"] == "My Book"
    assert parsed["subtitle"] == "A subtitle"
    assert parsed["isbn"] == "123"


def test_pandoc_args_default_highlight():
    args = build_pandoc_args(
        out=Path("/tmp/o.epub"),
        metadata_file=Path("/tmp/m.yaml"),
        css=Path("/tmp/s.css"),
        cover=None,
        chapter_files=[Path("/tmp/ch-01.md")],
        kindle=False,
    )
    assert "--highlight-style=pygments" in args
    assert not any("epub-cover" in a for a in args)
    assert "/tmp/ch-01.md" in args


def test_pandoc_args_kindle_switches_highlight_and_includes_cover():
    args = build_pandoc_args(
        out=Path("/tmp/o.epub"),
        metadata_file=Path("/tmp/m.yaml"),
        css=Path("/tmp/s.css"),
        cover=Path("/tmp/cover.svg"),
        chapter_files=[Path("/tmp/ch-01.md"), Path("/tmp/ch-02.md")],
        kindle=True,
    )
    assert "--highlight-style=monochrome" in args
    assert any(a == "--epub-cover-image=/tmp/cover.svg" for a in args)
    assert args[-1] == "/tmp/ch-02.md"
