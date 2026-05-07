from pathlib import Path

from epubgen import wizard_state
from epubgen.schema import Beat, Chapter, Outline, RefinedTopic
from epubgen.wizard import State


def _outline():
    return Outline(
        title="Fast Python",
        topic="Python perf",
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


def test_state_path_uses_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = wizard_state.state_path()
    assert p == tmp_path / "epubgen" / "wizard.json"


def test_save_then_load_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    refined = RefinedTopic(
        title="Fast Python",
        subtitle="A measurement-first guide",
        angle="Practical, evidence-driven optimization for working developers.",
    )
    state = State(
        topic="python perf",
        style="oreilly",
        refined=refined,
        description="A description that would normally be longer than this.",
        out_path=Path("./fast-python.epub"),
        workdir=Path("./fast-python.epub.work"),
        outline=_outline(),
        outline_hint="punchier",
        ereader=False,
    )
    wizard_state.save(state, step_index=4)

    loaded = wizard_state.load()
    assert loaded is not None
    s2, idx = loaded
    assert idx == 4
    assert s2.topic == state.topic
    assert s2.style == state.style
    assert s2.refined == state.refined
    assert s2.description == state.description
    assert s2.out_path == state.out_path
    assert s2.workdir == state.workdir
    assert s2.outline == state.outline
    assert s2.outline_hint == "punchier"
    assert s2.ereader is False


def test_load_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert wizard_state.load() is None


def test_load_corrupt_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = wizard_state.state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not json")
    assert wizard_state.load() is None


def test_load_wrong_version_returns_none(monkeypatch, tmp_path):
    import json

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    p = wizard_state.state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"version": 999, "topic": "x"}))
    assert wizard_state.load() is None


def test_clear_removes_file(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    state = State(topic="x", style="oreilly")
    wizard_state.save(state, step_index=1)
    assert wizard_state.state_path().exists()
    wizard_state.clear()
    assert not wizard_state.state_path().exists()


def test_clear_is_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    wizard_state.clear()  # nothing there — must not raise
    wizard_state.clear()


def test_save_partial_state_is_loadable(monkeypatch, tmp_path):
    """A crash mid-step 1 means only topic is set; load must still succeed."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    wizard_state.save(State(topic="a topic"), step_index=1)
    loaded = wizard_state.load()
    assert loaded is not None
    s, idx = loaded
    assert s.topic == "a topic"
    assert s.style is None
    assert s.refined is None
    assert s.outline is None
    assert idx == 1
