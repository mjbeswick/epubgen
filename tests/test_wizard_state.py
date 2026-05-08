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


def test_sessions_dir_uses_xdg_cache_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert wizard_state.sessions_dir() == tmp_path / "epubgen" / "sessions"


def test_new_session_id_includes_topic_slug(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    sid = wizard_state.new_session_id(State(topic="My Cool Topic!"))
    assert "my-cool-topic" in sid


def test_new_session_id_unique_under_collision(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    state = State(topic="x")
    sid1 = wizard_state.new_session_id(state)
    wizard_state.save(state, 1, sid1)
    sid2 = wizard_state.new_session_id(state)
    assert sid1 != sid2


def test_save_load_round_trip(monkeypatch, tmp_path):
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
    sid = wizard_state.new_session_id(state)
    wizard_state.save(state, step_index=4, session_id=sid)

    loaded = wizard_state.load(sid)
    assert loaded is not None
    s2, idx = loaded
    assert idx == 4
    assert s2 == state


def test_load_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert wizard_state.load("nonexistent") is None


def test_list_sessions_sorts_recent_first(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    sid1 = wizard_state.new_session_id(State(topic="alpha"))
    wizard_state.save(State(topic="alpha"), 1, sid1)
    import time as _t
    _t.sleep(0.01)
    sid2 = wizard_state.new_session_id(State(topic="beta"))
    wizard_state.save(State(topic="beta"), 2, sid2)

    listed = wizard_state.list_sessions()
    assert [s.session_id for s in listed] == [sid2, sid1]
    assert listed[0].topic == "beta"


def test_list_sessions_skips_corrupt(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    d = wizard_state.sessions_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "corrupt.json").write_text("{not json")
    assert wizard_state.list_sessions() == []


def test_list_sessions_skips_wrong_version(monkeypatch, tmp_path):
    import json as _json

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    d = wizard_state.sessions_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / "old.json").write_text(_json.dumps({"version": 999, "topic": "x"}))
    assert wizard_state.list_sessions() == []


def test_clear_removes_only_specified_session(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    sid1 = wizard_state.new_session_id(State(topic="alpha"))
    wizard_state.save(State(topic="alpha"), 1, sid1)
    sid2 = wizard_state.new_session_id(State(topic="beta"))
    wizard_state.save(State(topic="beta"), 1, sid2)

    wizard_state.clear(sid1)
    assert not wizard_state.session_path(sid1).exists()
    assert wizard_state.session_path(sid2).exists()


def test_clear_idempotent(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    wizard_state.clear("nonexistent")
    wizard_state.clear("nonexistent")  # second call must not raise


def test_two_sessions_dont_clobber(monkeypatch, tmp_path):
    """Two parallel wizards must each persist their own state."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    sa = State(topic="alpha")
    sb = State(topic="beta")
    sid_a = wizard_state.new_session_id(sa)
    sid_b = wizard_state.new_session_id(sb)
    assert sid_a != sid_b
    wizard_state.save(sa, 2, sid_a)
    wizard_state.save(sb, 5, sid_b)
    la = wizard_state.load(sid_a)
    lb = wizard_state.load(sid_b)
    assert la is not None and lb is not None
    assert la[0].topic == "alpha" and la[1] == 2
    assert lb[0].topic == "beta" and lb[1] == 5
