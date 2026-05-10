"""Anthropic-shaped response objects used by non-Anthropic adapters.

The existing call sites read `resp.content[i].type`, `.text`, `.input`, plus
`resp.stop_reason` and `resp.usage.{input_tokens,output_tokens,
cache_creation_input_tokens,cache_read_input_tokens}`. We mimic that surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TextBlock:
    text: str
    type: str = "text"


@dataclass
class ToolUseBlock:
    name: str
    input: dict[str, Any]
    id: str = ""
    type: str = "tool_use"


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


@dataclass
class Response:
    content: list[Any] = field(default_factory=list)
    stop_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
