
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


def test_missing_all_provider_keys_is_fatal(monkeypatch):
    for env in (
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
        "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)
    checks = run_checks()
    fatal = fatal_checks(checks)
    assert any(c.status == FAIL for c in fatal)


def test_alt_provider_key_satisfies(monkeypatch):
    """If OpenAI key is set but Anthropic is missing, that's fine — not fatal."""
    for env in (
        "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "GEMINI_API_KEY",
        "DEEPSEEK_API_KEY", "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    checks = run_checks()
    assert not fatal_checks(checks)


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
