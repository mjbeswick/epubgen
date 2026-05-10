"""OpenAI-compatible adapter. Covers OpenAI, DeepSeek, OpenRouter.

Talks the OpenAI Chat Completions protocol. Tool calls are mapped to
Anthropic-shaped `tool_use` blocks so call sites don't need to know the
difference. Auto prefix caching is provider-side; we don't cache_control.
"""

from __future__ import annotations

import json
import os
from typing import Any

from epubgen.costs import get_tally
from epubgen.errors import ApiError, ConfigError
from epubgen.llm._schema import flatten_system, to_openai_tool
from epubgen.llm.types import Response, TextBlock, ToolUseBlock, Usage
from epubgen.logsetup import get_logger

log = get_logger("llm.openai_compat")

# Provider → (env var, base URL). None base = default OpenAI.
_PROVIDERS: dict[str, tuple[str, str | None]] = {
    "openai": ("OPENAI_API_KEY", None),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
}

_clients: dict[str, Any] = {}


def _client(provider: str) -> Any:
    if provider in _clients:
        return _clients[provider]
    env, base = _PROVIDERS[provider]
    key = os.environ.get(env)
    if not key:
        raise ConfigError(f"{env} not set (required for provider {provider!r})")
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise ConfigError(
            "openai package not installed. Install with: uv tool install --editable . "
            "or pip install 'openai>=1.30'"
        ) from e
    kw: dict[str, Any] = {"api_key": key, "max_retries": 5}
    if base is not None:
        kw["base_url"] = base
    _clients[provider] = AsyncOpenAI(**kw)
    return _clients[provider]


def _is_reasoning(model: str) -> bool:
    """Models that use `max_completion_tokens` instead of `max_tokens`."""
    m = model.lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4")) or "reasoner" in m


def _convert_messages(
    system: Any, messages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sys_text = flatten_system(system)
    if sys_text:
        out.append({"role": "system", "content": sys_text})
    for m in messages:
        role = m["role"]
        content = m["content"]
        # Anthropic accepts list-of-blocks; OpenAI wants a string for plain text.
        if isinstance(content, list):
            text_parts = [b.get("text", "") for b in content if b.get("type") == "text"]
            content = "\n\n".join(p for p in text_parts if p)
        out.append({"role": role, "content": content})
    return out


def _classify(e: Exception, provider: str) -> tuple[str, str | None]:
    msg = str(e)
    low = msg.lower()
    if "authentication" in low or "401" in msg or "invalid api key" in low:
        return (
            f"{provider} API key rejected",
            f"Verify the value of {_PROVIDERS[provider][0]}",
        )
    if "insufficient" in low or "quota" in low or "balance" in low:
        return (f"{provider} quota / balance exhausted", "Top up at the provider console")
    if "rate" in low and "limit" in low:
        return (f"Rate-limited by {provider}", "Wait, or lower --concurrency")
    if "model" in low and ("not found" in low or "does not exist" in low):
        return (f"{provider}: model not available on your account", None)
    return (f"{provider} API call failed: {e}", None)


async def create_message(
    *,
    provider: str,
    model: str,
    max_tokens: int,
    system: Any = None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    **_: Any,
) -> Response:
    client = _client(provider)
    payload_messages = _convert_messages(system, messages or [])
    body: dict[str, Any] = {
        "model": model,
        "messages": payload_messages,
    }
    # Token cap parameter name varies by model family.
    body["max_completion_tokens" if _is_reasoning(model) else "max_tokens"] = max_tokens

    if tools:
        body["tools"] = [to_openai_tool(t) for t in tools]
        if tool_choice and tool_choice.get("type") == "tool":
            body["tool_choice"] = {
                "type": "function",
                "function": {"name": tool_choice["name"]},
            }
        elif tool_choice and tool_choice.get("type") == "any":
            body["tool_choice"] = "required"

    log.debug(
        "%s.chat.completions model=%s msgs=%d tools=%s",
        provider, model, len(payload_messages), bool(tools),
    )
    try:
        resp = await client.chat.completions.create(**body)
    except Exception as e:
        short, hint = _classify(e, provider)
        log.debug("%s call failed: %s: %s", provider, type(e).__name__, e)
        raise ApiError(short, hint=hint) from e

    choice = resp.choices[0]
    msg = choice.message
    blocks: list[Any] = []
    text = (msg.content or "").strip()
    if text:
        blocks.append(TextBlock(text=text))
    for tc in (msg.tool_calls or []) if hasattr(msg, "tool_calls") else []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        blocks.append(ToolUseBlock(name=tc.function.name, input=args, id=tc.id or ""))

    finish = (choice.finish_reason or "").lower()
    stop_reason = {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
    }.get(finish, finish or None)

    usage_obj = Usage()
    u = getattr(resp, "usage", None)
    if u is not None:
        usage_obj.input_tokens = int(getattr(u, "prompt_tokens", 0) or 0)
        usage_obj.output_tokens = int(getattr(u, "completion_tokens", 0) or 0)
        # OpenAI exposes `prompt_tokens_details.cached_tokens`; DeepSeek uses
        # `prompt_cache_hit_tokens`; OpenRouter passes through where available.
        details = getattr(u, "prompt_tokens_details", None)
        cached = int(getattr(details, "cached_tokens", 0) or 0) if details else 0
        if not cached:
            cached = int(getattr(u, "prompt_cache_hit_tokens", 0) or 0)
        usage_obj.cache_read_input_tokens = cached
        usage_obj.input_tokens -= cached  # bill the cache rate, not the input rate

    full_id = f"{provider}/{model}"
    get_tally().record_usage(full_id, usage_obj)

    return Response(content=blocks, stop_reason=stop_reason, usage=usage_obj)
