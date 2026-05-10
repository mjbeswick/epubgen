"""Multi-provider LLM router. Call sites import `create_message` from here.

The on-the-wire shape is Anthropic-flavored: system blocks, messages, optional
tools/tool_choice. Each adapter translates that into the provider's native
shape and translates the response back into an Anthropic-flavored object the
existing call sites already know how to read.
"""

from __future__ import annotations

from epubgen.llm.router import (
    KNOWN_MODELS,
    PROVIDERS,
    create_message,
    normalize_model,
    parse_model,
    provider_of,
)

__all__ = [
    "KNOWN_MODELS",
    "PROVIDERS",
    "create_message",
    "normalize_model",
    "parse_model",
    "provider_of",
]
