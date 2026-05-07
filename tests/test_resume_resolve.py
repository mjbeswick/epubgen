import json
from pathlib import Path

import pytest
import typer

from epubgen.cli import _resolve_resume_workdir


def _make_workdir(parent: Path, name: str) -> Path:
    wd = parent / name
    wd.mkdir(parents=True)
    (wd / "options.json").write_text(json.dumps({"topic": "x", "style": "oreilly"}))
    return wd


def test_direct_workdir_with_options_json(tmp_path):
    wd = _make_workdir(tmp_path, "book.epub.work")
    assert _resolve_resume_workdir(wd) == wd


def test_epub_path_derives_workdir(tmp_path):
    _make_workdir(tmp_path, "book.epub.work")
    epub_path = tmp_path / "book.epub"
    epub_path.touch()
    assert _resolve_resume_workdir(epub_path) == tmp_path / "book.epub.work"


def test_epub_path_with_no_workdir_exits(tmp_path):
    epub_path = tmp_path / "missing.epub"
    epub_path.touch()
    with pytest.raises(typer.Exit):
        _resolve_resume_workdir(epub_path)


def test_search_dir_finds_single_candidate(tmp_path):
    wd = _make_workdir(tmp_path, "book.epub.work")
    # Pass the parent dir (e.g. cwd) — should auto-find the lone workdir.
    assert _resolve_resume_workdir(tmp_path) == wd


def test_search_dir_with_no_candidates_exits(tmp_path):
    with pytest.raises(typer.Exit):
        _resolve_resume_workdir(tmp_path)


def test_search_dir_with_multiple_non_tty_lists_and_exits(tmp_path, monkeypatch):
    _make_workdir(tmp_path, "a.epub.work")
    _make_workdir(tmp_path, "b.epub.work")
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(typer.Exit):
        _resolve_resume_workdir(tmp_path)


def test_workdir_without_options_json_searches_inside(tmp_path):
    # Pass a directory that itself has no options.json but contains a workdir.
    inner = _make_workdir(tmp_path, "book.epub.work")
    assert _resolve_resume_workdir(tmp_path) == inner
