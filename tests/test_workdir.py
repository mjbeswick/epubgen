import json

import pytest

from epubgen.errors import FsError
from epubgen.workdir import (
    atomic_write_text,
    chapter_path,
    default_workdir,
    ensure_workdir,
    freeze_options,
    slugify,
)


def test_slugify():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("   --  ") == "book"
    assert slugify("Python 3.12 Performance") == "python-3-12-performance"


def test_default_workdir(tmp_path):
    out = tmp_path / "book.epub"
    wd = default_workdir(out)
    assert wd.name == "book.epub.work"


def test_chapter_path_zero_pads(tmp_path):
    assert chapter_path(tmp_path, 1).name == "ch-01.md"
    assert chapter_path(tmp_path, 12).name == "ch-12.md"


def test_atomic_write_overwrites(tmp_path):
    p = tmp_path / "x.txt"
    atomic_write_text(p, "first")
    atomic_write_text(p, "second")
    assert p.read_text() == "second"


def test_freeze_options_writes_then_matches(tmp_path):
    wd = ensure_workdir(tmp_path / "wd")
    frozen = {"topic": "t", "style": "oreilly"}
    freeze_options(wd, frozen, force=False)
    # Same frozen dict on resume should not raise.
    freeze_options(wd, frozen, force=False)
    assert json.loads((wd / "options.json").read_text()) == frozen


def test_freeze_options_mismatch_raises(tmp_path):
    wd = ensure_workdir(tmp_path / "wd")
    freeze_options(wd, {"topic": "t", "style": "oreilly"}, force=False)
    with pytest.raises(FsError):
        freeze_options(wd, {"topic": "t", "style": "manning"}, force=False)


def test_freeze_options_force_overrides(tmp_path):
    wd = ensure_workdir(tmp_path / "wd")
    freeze_options(wd, {"topic": "t", "style": "oreilly"}, force=False)
    freeze_options(wd, {"topic": "t", "style": "manning"}, force=True)
    assert json.loads((wd / "options.json").read_text())["style"] == "manning"
