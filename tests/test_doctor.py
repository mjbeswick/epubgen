
from epubgen.doctor import (
    FAIL,
    OK,
    WARN,
    fatal_checks,
    format_checks,
    run_checks,
)


def test_run_checks_returns_expected_names(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake-test-key-1234567890")
    checks = run_checks()
    names = [c.name for c in checks]
    assert "python ≥ 3.12" in names
    assert "ANTHROPIC_API_KEY" in names
    assert "pandoc" in names
    assert "kindlepreviewer" in names
    assert "OPENAI_API_KEY" in names


def test_missing_anthropic_key_is_fatal(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    checks = run_checks()
    fatal = fatal_checks(checks)
    assert any(c.name == "ANTHROPIC_API_KEY" and c.status == FAIL for c in fatal)


def test_missing_kindlepreviewer_is_warn_not_fatal(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.setenv("PATH", "/nonexistent")
    checks = run_checks()
    kp = next(c for c in checks if c.name == "kindlepreviewer")
    assert kp.status == WARN
    assert not kp.fatal


def test_format_checks_renders_status_glyphs(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    out = format_checks(run_checks())
    assert OK in out or FAIL in out
    assert "python" in out
