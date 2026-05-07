from pathlib import Path

import yaml

from epubgen.assemble import build_pandoc_extra_args, metadata_yaml
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
    args = build_pandoc_extra_args(
        metadata_file=Path("/tmp/m.yaml"),
        css=Path("/tmp/s.css"),
        cover=None,
        ereader=False,
    )
    assert "--highlight-style=pygments" in args
    assert not any("epub-cover" in a for a in args)
    assert "--toc" in args
    assert "--metadata-file=/tmp/m.yaml" in args
    assert "--mathml" in args


def test_pandoc_args_kindle_switches_highlight_and_includes_cover():
    args = build_pandoc_extra_args(
        metadata_file=Path("/tmp/m.yaml"),
        css=Path("/tmp/s.css"),
        cover=Path("/tmp/cover.svg"),
        ereader=True,
    )
    assert "--highlight-style=monochrome" in args
    assert "--epub-cover-image=/tmp/cover.svg" in args
