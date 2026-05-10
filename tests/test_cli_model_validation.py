from epubgen.cli import _validate_model


def test_known_model_normalizes_legacy_id():
    assert _validate_model("claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"


def test_known_prefixed_id_passes_through():
    assert _validate_model("openai/gpt-5-mini") == "openai/gpt-5-mini"


def test_openrouter_pass_through_unknown_tail():
    # OpenRouter accepts arbitrary vendor/model ids; we shouldn't reject these.
    out = _validate_model("openrouter/some-vendor/some-model")
    assert out == "openrouter/some-vendor/some-model"


def test_typo_warning_does_not_raise(capsys):
    # Did-you-mean is advisory; we still return the (normalized) id and let the
    # API call fail loudly if it's truly invalid.
    out = _validate_model("anthropic/claude-sonnett-4-6")
    assert out == "anthropic/claude-sonnett-4-6"
    err = capsys.readouterr().err
    assert "did you mean" in err.lower()
