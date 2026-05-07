from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeBlock:
    type: str
    text: str | None = None
    input: dict[str, Any] | None = None


@dataclass
class FakeUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    usage: FakeUsage = field(default_factory=FakeUsage)
    stop_reason: str = "end_turn"


@dataclass
class FakeMessages:
    handler: Callable[[dict[str, Any]], FakeResponse]
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create(self, **kwargs: Any) -> FakeResponse:
        self.calls.append(kwargs)
        return self.handler(kwargs)


class FakeAnthropic:
    def __init__(self, handler: Callable[[dict[str, Any]], FakeResponse]) -> None:
        self.messages = FakeMessages(handler=handler)


def text_response(text: str, *, cache_read: int = 0, cache_create: int = 0) -> FakeResponse:
    return FakeResponse(
        content=[FakeBlock(type="text", text=text)],
        usage=FakeUsage(
            output_tokens=len(text) // 4,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_create,
        ),
    )


def tool_response(payload: dict[str, Any]) -> FakeResponse:
    return FakeResponse(content=[FakeBlock(type="tool_use", input=payload)])
