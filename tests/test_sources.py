from __future__ import annotations

from pathlib import Path

import pytest

from epubgen.errors import ConfigError
from epubgen.prompts.chapter import build_chapter_messages
from epubgen.prompts.outline import build_outline_messages
from epubgen.schema import Beat, Chapter, Options, Outline
from epubgen.sources import build_bundle, freeze_digest, load_sources
from epubgen.styles import load_style


def _opts(**kw):
    return Options(topic="t", style="oreilly", out=Path("/tmp/x.epub"), **kw)


def _outline():
    return Outline(
        title="T", topic="t", style="oreilly",
        chapters=[
            Chapter(
                number=i, title=f"C{i}",
                synopsis="A sufficiently long synopsis for validation.",
                beats=[Beat(summary="first beat summary"), Beat(summary="second beat summary")],
                word_target=3000,
            )
            for i in (1, 2, 3)
        ],
    )


def test_load_sources_text_file(tmp_path: Path):
    p = tmp_path / "notes.md"
    p.write_text("# Notes\n\nimportant fact: pi ≈ 3.14")
    loaded = load_sources([p])
    assert len(loaded) == 1
    assert loaded[0].path == p
    assert "important fact" in loaded[0].text
    assert len(loaded[0].sha256) == 64


def test_load_sources_dir(tmp_path: Path):
    (tmp_path / "a.md").write_text("alpha")
    (tmp_path / "b.txt").write_text("beta")
    (tmp_path / ".hidden").write_text("nope")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "c.md").write_text("gamma")
    loaded = load_sources([tmp_path])
    names = {s.path.name for s in loaded}
    assert names == {"a.md", "b.txt", "c.md"}


def test_load_sources_dedup(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("hi")
    loaded = load_sources([p, p, tmp_path])
    assert len(loaded) == 1


def test_load_sources_missing(tmp_path: Path):
    with pytest.raises(ConfigError):
        load_sources([tmp_path / "nope.md"])


def test_build_bundle_empty():
    assert build_bundle([]) == ""


def test_build_bundle_includes_filenames(tmp_path: Path):
    (tmp_path / "a.md").write_text("ALPHA")
    (tmp_path / "b.md").write_text("BETA")
    bundle = build_bundle(load_sources([tmp_path]))
    assert "SOURCE: a.md" in bundle
    assert "SOURCE: b.md" in bundle
    assert "ALPHA" in bundle and "BETA" in bundle


def test_freeze_digest_stable(tmp_path: Path):
    p = tmp_path / "x.md"
    p.write_text("hello")
    d1 = freeze_digest(load_sources([p]))
    d2 = freeze_digest(load_sources([p]))
    assert d1 == d2
    p.write_text("hello world")
    d3 = freeze_digest(load_sources([p]))
    assert d1 != d3


def test_outline_prompt_threads_sources():
    style = load_style("oreilly")
    msg = build_outline_messages(style, _opts(), sources_text="REF MATERIAL")
    texts = [b["text"] for b in msg["system"]]
    assert any("REF MATERIAL" in t for t in texts)
    # The third (instruction) block should mention sources are authoritative.
    assert any("authoritative" in t for t in texts)


def test_outline_prompt_no_sources():
    style = load_style("oreilly")
    msg = build_outline_messages(style, _opts())
    # 2 system blocks when no sources: style guide + instructions.
    assert len(msg["system"]) == 2


def test_chapter_prompt_threads_sources():
    style = load_style("oreilly")
    outline = _outline()
    msg = build_chapter_messages(
        style, outline, outline.chapters[0], _opts(), sources_text="REF MATERIAL"
    )
    texts = [b["text"] for b in msg["system"]]
    assert any("REF MATERIAL" in t for t in texts)
    # cache_control should be on style guide, sources, AND outline blocks.
    cached = [b for b in msg["system"] if b.get("cache_control")]
    assert len(cached) == 3


def test_chapter_prompt_no_sources():
    style = load_style("oreilly")
    outline = _outline()
    msg = build_chapter_messages(style, outline, outline.chapters[0], _opts())
    # 3 blocks: style guide, outline, instructions.
    assert len(msg["system"]) == 3


def test_freeze_dict_includes_source_digest():
    opts = _opts()
    opts.source_digest = [{"name": "a.md", "sha256": "abc"}]
    assert opts.freeze_dict()["source_digest"] == [{"name": "a.md", "sha256": "abc"}]
