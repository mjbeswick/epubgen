from __future__ import annotations

from typing import Any, Protocol

from epubgen.config import require_api_key
from epubgen.costs import get_tally
from epubgen.errors import ApiError
from epubgen.logsetup import get_logger

log = get_logger("anthropic_client")


class _MessagesAPI(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class AsyncLike(Protocol):
    messages: _MessagesAPI


_client: AsyncLike | None = None


def get_client() -> AsyncLike:
    global _client
    if _client is not None:
        return _client
    from anthropic import AsyncAnthropic

    _client = AsyncAnthropic(api_key=require_api_key(), max_retries=5)
    return _client


def set_client(client: AsyncLike | None) -> None:
    global _client
    _client = client


def _classify_anthropic_error(e: Exception) -> tuple[str, str | None]:
    """Return (short message, actionable hint) for common Anthropic API errors."""
    msg = str(e)
    lower = msg.lower()
    if "credit balance is too low" in lower or "credit balance" in lower:
        return (
            "Anthropic credit balance too low",
            "Top up at https://console.anthropic.com/settings/billing",
        )
    if "authentication_error" in lower or "invalid x-api-key" in lower:
        return (
            "ANTHROPIC_API_KEY rejected",
            "Verify the key at https://console.anthropic.com/settings/keys",
        )
    if "rate_limit_error" in lower or "rate limit" in lower:
        return (
            "Rate-limited by Anthropic (SDK retries already exhausted)",
            "Wait a minute, or lower --concurrency",
        )
    if "overloaded_error" in lower or "overloaded" in lower:
        return ("Anthropic API overloaded", "Try again in a few moments")
    if "permission" in lower or "forbidden" in lower:
        return (
            "Anthropic API permission denied",
            "Check that this API key has access to the requested model",
        )
    return (f"anthropic API call failed: {e}", None)


async def create_message(**kwargs: Any) -> Any:
    client = get_client()
    model = kwargs.get("model", "?")
    max_tokens = kwargs.get("max_tokens", "?")
    has_tools = "tools" in kwargs
    log.debug(
        "messages.create model=%s max_tokens=%s tools=%s sys_blocks=%d",
        model,
        max_tokens,
        has_tools,
        len(kwargs.get("system", []) or []),
    )
    try:
        resp = await client.messages.create(**kwargs)
    except Exception as e:
        short, hint = _classify_anthropic_error(e)
        log.error("anthropic call failed: %s: %s", type(e).__name__, e)
        raise ApiError(short, hint=hint) from e
    usage = getattr(resp, "usage", None)
    if usage is not None:
        log.debug(
            "usage: in=%s out=%s cache_create=%s cache_read=%s",
            getattr(usage, "input_tokens", "?"),
            getattr(usage, "output_tokens", "?"),
            getattr(usage, "cache_creation_input_tokens", "?"),
            getattr(usage, "cache_read_input_tokens", "?"),
        )
        get_tally().record_usage(model, usage)
    return resp
