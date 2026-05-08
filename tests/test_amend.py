from __future__ import annotations

import json
from pathlib import Path

import pytest

from epubgen import amend
from epubgen.errors import ConfigError, FsError
from epubgen.schema import Beat, Chapter, Outline


def _ch(n: int, title: str = "C") -> Chapter:
    return Chapter(
        number=n, title=f"{title}{n}",
        synopsis="A long-enough synopsis for validation.",
        beats=[Beat(summary="first beat summary"), Beat(summary="second beat summary")],
        word_target=2500,
    )


def _outline(n_chapters: int = 3) -> Outline:
    return Outline(
        title="T", topic="t", style="oreilly",
        chapters=[_ch(i) for i in range(1, n_chapters + 1)],
    )


def _setup(tmp_path: Path, n: int = 3) -> tuple[Path, Outline]:
    outline = _outline(n)
    (tmp_path / "outline.json").write_text(outline.model_dump_json())
    (tmp_path / "options.json").write_text(json.dumps({
        "topic": "t", "style": "oreilly", "model": "claude-sonnet-4-6",
        "ereader": True, "author": "x",
    }))
    for i in range(1, n + 1):
        (tmp_path / f"ch-{i:02d}.md").write_text(f"# C{i}\n\nbody{i}\n")
    return tmp_path, outline


def test_load_workdir(tmp_path: Path):
    wd, _ = _setup(tmp_path)
    outline, frozen = amend.load_workdir(wd)
    assert len(outline.chapters) == 3
    assert frozen["topic"] == "t"


def test_load_workdir_missing(tmp_path: Path):
    with pytest.raises(FsError):
        amend.load_workdir(tmp_path)


def test_archive_moves_with_timestamp(tmp_path: Path):
    src = tmp_path / "thing.md"
    src.write_text("hi")
    dest = amend.archive(tmp_path, src)
    assert not src.exists()
    assert dest.exists()
    assert dest.parent.name == ".archive"
    assert dest.read_text() == "hi"


def test_archive_missing_no_op(tmp_path: Path):
    missing = tmp_path / "nope.md"
    result = amend.archive(tmp_path, missing)
    assert result == missing


def test_remove_chapter(tmp_path: Path):
    wd, outline = _setup(tmp_path, 4)
    new_outline = amend.remove_chapter(wd, outline, 2)
    assert [c.number for c in new_outline.chapters] == [1, 2, 3]
    assert [c.title for c in new_outline.chapters] == ["C1", "C3", "C4"]
    # ch-02.md should now be the old ch-03 content.
    assert (wd / "ch-02.md").read_text() == "# C3\n\nbody3\n"
    assert (wd / "ch-03.md").read_text() == "# C4\n\nbody4\n"
    assert not (wd / "ch-04.md").exists()


def test_remove_missing_chapter(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    with pytest.raises(ConfigError):
        amend.remove_chapter(wd, outline, 99)


def test_reorder_forward(tmp_path: Path):
    wd, outline = _setup(tmp_path, 4)
    new_outline = amend.reorder_chapter(wd, outline, frm=2, to=4)
    assert [c.title for c in new_outline.chapters] == ["C1", "C3", "C4", "C2"]
    assert (wd / "ch-04.md").read_text() == "# C2\n\nbody2\n"
    assert (wd / "ch-02.md").read_text() == "# C3\n\nbody3\n"


def test_reorder_backward(tmp_path: Path):
    wd, outline = _setup(tmp_path, 4)
    new_outline = amend.reorder_chapter(wd, outline, frm=4, to=1)
    assert [c.title for c in new_outline.chapters] == ["C4", "C1", "C2", "C3"]
    assert (wd / "ch-01.md").read_text() == "# C4\n\nbody4\n"


def test_reorder_noop(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    new_outline = amend.reorder_chapter(wd, outline, frm=2, to=2)
    assert [c.title for c in new_outline.chapters] == ["C1", "C2", "C3"]


def test_reorder_out_of_range(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    with pytest.raises(ConfigError):
        amend.reorder_chapter(wd, outline, frm=1, to=99)


def test_insert_chapter_middle(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    new_ch = _ch(99, title="NEW")
    new_outline = amend.insert_chapter(wd, outline, position=2, chapter=new_ch)
    assert [c.number for c in new_outline.chapters] == [1, 2, 3, 4]
    titles = [c.title for c in new_outline.chapters]
    assert titles == ["C1", "NEW99", "C2", "C3"]
    # Caller writes the new chapter file. Existing files should be shifted:
    assert (wd / "ch-03.md").read_text() == "# C2\n\nbody2\n"
    assert (wd / "ch-04.md").read_text() == "# C3\n\nbody3\n"
    # Slot for new chapter should be empty (caller responsibility).
    assert not (wd / "ch-02.md").exists()


def test_insert_at_end(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    new_ch = _ch(99, title="END")
    new_outline = amend.insert_chapter(wd, outline, position=4, chapter=new_ch)
    assert [c.number for c in new_outline.chapters] == [1, 2, 3, 4]
    # No shift needed; existing files unchanged.
    assert (wd / "ch-01.md").read_text() == "# C1\n\nbody1\n"
    assert (wd / "ch-03.md").read_text() == "# C3\n\nbody3\n"


def test_insert_position_out_of_range(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    with pytest.raises(ConfigError):
        amend.insert_chapter(wd, outline, position=99, chapter=_ch(99))


def test_renormalize_idempotent(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    out1 = amend.renormalize(wd, outline)
    out2 = amend.renormalize(wd, out1)
    assert [c.number for c in out2.chapters] == [1, 2, 3]


def test_retitle_title_only():
    o = _outline(3)
    new = amend.retitle(o, title="NEW")
    assert new.title == "NEW"
    assert new.subtitle == o.subtitle


def test_retitle_subtitle_set():
    o = _outline(3)
    new = amend.retitle(o, subtitle="hello")
    assert new.subtitle == "hello"


def test_retitle_subtitle_clear():
    o = _outline(3).model_copy(update={"subtitle": "x"})
    new = amend.retitle(o, subtitle=None)
    assert new.subtitle is None


def test_retitle_keep_subtitle_when_omitted():
    o = _outline(3).model_copy(update={"subtitle": "keep"})
    new = amend.retitle(o, title="NEW")
    assert new.subtitle == "keep"
    assert new.title == "NEW"


def test_save_writes_outline(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    outline2 = outline.model_copy(update={"title": "Renamed"})
    amend.save(wd, outline2)
    reloaded = amend.load_workdir(wd)[0]
    assert reloaded.title == "Renamed"


def test_save_writes_frozen(tmp_path: Path):
    wd, outline = _setup(tmp_path, 3)
    amend.save(wd, outline, frozen={"topic": "new", "style": "oreilly"})
    assert json.loads((wd / "options.json").read_text())["topic"] == "new"
