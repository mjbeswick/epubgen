from pathlib import Path

from epubgen.wizard import _workdir_summary


def test_summary_empty_for_missing_dir(tmp_path: Path):
    assert _workdir_summary(tmp_path / "does-not-exist") == []


def test_summary_empty_for_empty_dir(tmp_path: Path):
    (tmp_path / "wd").mkdir()
    assert _workdir_summary(tmp_path / "wd") == []


def test_summary_lists_known_files(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "options.json").write_text("{}")
    (wd / "outline.json").write_text("{}")
    items = _workdir_summary(wd)
    assert "options.json" in items
    assert "outline.json" in items


def test_summary_counts_chapters(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    for i in range(1, 4):
        (wd / f"ch-{i:02d}.md").write_text(f"# C{i}")
    items = _workdir_summary(wd)
    assert "3 chapter(s)" in items


def test_summary_omits_unrelated_files(tmp_path: Path):
    wd = tmp_path / "wd"
    wd.mkdir()
    (wd / "random.txt").write_text("x")
    assert _workdir_summary(wd) == []
