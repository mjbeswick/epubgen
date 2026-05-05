from __future__ import annotations

from typing import Any, Protocol

from epubgen.config import require_api_key
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
        log.error("anthropic call failed: %s: %s", type(e).__name__, e)
        raise ApiError(f"anthropic API call failed: {e}") from e
    usage = getattr(resp, "usage", None)
    if usage is not None:
        log.debug(
            "usage: in=%s out=%s cache_create=%s cache_read=%s",
            getattr(usage, "input_tokens", "?"),
            getattr(usage, "output_tokens", "?"),
            getattr(usage, "cache_creation_input_tokens", "?"),
            getattr(usage, "cache_read_input_tokens", "?"),
        )
    return resp
