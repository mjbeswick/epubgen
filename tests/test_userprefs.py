import json

from epubgen import userprefs


def test_config_path_uses_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert userprefs.config_path() == tmp_path / "epubgen" / "config.json"


def test_get_default_model_no_file_uses_builtin(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert userprefs.get_default_model() == "claude-sonnet-4-6"


def test_set_and_get_default_model_round_trip(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    userprefs.set_default_model("claude-haiku-4-5")
    assert userprefs.get_default_model() == "claude-haiku-4-5"
    # Persists across "processes" — re-read from disk.
    raw = userprefs.config_path().read_text()
    assert "claude-haiku-4-5" in raw
    assert json.loads(raw)["version"] == 1


def test_set_default_model_idempotent_skips_write(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    userprefs.set_default_model("claude-opus-4-7")
    path = userprefs.config_path()
    mtime_before = path.stat().st_mtime_ns
    userprefs.set_default_model("claude-opus-4-7")  # same value
    assert path.stat().st_mtime_ns == mtime_before


def test_load_prefs_corrupt_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = userprefs.config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json")
    assert userprefs.load_prefs() == {}


def test_load_prefs_wrong_version_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    userprefs.config_path().parent.mkdir(parents=True, exist_ok=True)
    userprefs.config_path().write_text(json.dumps({"version": 999, "default_model": "x"}))
    assert userprefs.load_prefs() == {}
    # Falls back to builtin.
    assert userprefs.get_default_model() == "claude-sonnet-4-6"


def test_picker_sorts_models_by_cost_ascending():
    from epubgen.costs import ANTHROPIC_RATES, estimate_book_cost

    models_sorted = sorted(ANTHROPIC_RATES.keys(), key=estimate_book_cost)
    costs = [estimate_book_cost(m) for m in models_sorted]
    assert costs == sorted(costs)
    # Cheapest first.
    assert models_sorted[0] == "claude-haiku-4-5"
