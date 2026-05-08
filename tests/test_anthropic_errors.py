from epubgen.anthropic_client import _classify_anthropic_error


def test_low_credit_balance_classified():
    e = Exception(
        "Error code: 400 - {'type': 'error', 'error': {'type': "
        "'invalid_request_error', 'message': 'Your credit balance is too low'}}"
    )
    msg, hint = _classify_anthropic_error(e)
    assert "credit balance" in msg.lower()
    assert hint is not None
    assert "billing" in hint.lower()


def test_invalid_api_key_classified():
    e = Exception(
        "Error code: 401 - {'type': 'error', 'error': {'type': "
        "'authentication_error', 'message': 'invalid x-api-key'}}"
    )
    msg, hint = _classify_anthropic_error(e)
    assert "key" in msg.lower()
    assert hint is not None and "console.anthropic.com" in hint


def test_rate_limit_classified():
    e = Exception("Error code: 429 - rate_limit_error: too many requests")
    msg, hint = _classify_anthropic_error(e)
    assert "rate" in msg.lower()
    assert hint is not None and "concurrency" in hint.lower()


def test_overloaded_classified():
    e = Exception("Error code: 529 - overloaded_error")
    msg, hint = _classify_anthropic_error(e)
    assert "overloaded" in msg.lower()
    assert hint is not None


def test_unknown_error_returns_no_hint():
    e = Exception("Some unexpected network blip")
    msg, hint = _classify_anthropic_error(e)
    assert hint is None
    assert "anthropic" in msg.lower()


def test_usage_limit_classified():
    e = Exception(
        "Error code: 400 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
        "'message': 'You have reached your specified API usage limits. You will regain "
        "access on 2026-06-01 at 00:00 UTC.'}}"
    )
    msg, hint = _classify_anthropic_error(e)
    assert "usage limit" in msg.lower()
    assert "2026-06-01" in msg
    assert hint is not None
    assert "resume" in hint.lower()
