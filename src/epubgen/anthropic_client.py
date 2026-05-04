from __future__ import annotations

from typing import Any, Protocol

from epubgen.config import require_api_key
from epubgen.errors import ApiError


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
    try:
        return await client.messages.create(**kwargs)
    except Exception as e:
        # SDK has already retried transient errors; anything reaching here is terminal.
        raise ApiError(f"anthropic API call failed: {e}") from e
