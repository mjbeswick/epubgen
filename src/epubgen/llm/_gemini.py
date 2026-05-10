"""Gemini adapter via google-genai SDK with explicit context caching.

Caching strategy: hash the (system text + tools) prefix; on first call create a
CachedContent and reuse its name for subsequent calls within the process. If
the prefix is below the model's minimum cacheable size the SDK raises — we
catch and fall back to no-cache (the call still succeeds, just at full price).

The cache TTL defaults to 1 hour, which comfortably covers a typical book
generation. A resumed run hours later pays the create cost on its first call.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from epubgen.costs import get_tally
from epubgen.errors import ApiError, ConfigError
from epubgen.llm._schema import flatten_system, to_gemini_function
from epubgen.llm.types import Response, TextBlock, ToolUseBlock, Usage
from epubgen.logsetup import get_logger

log = get_logger("llm.gemini")

_client: Any = None
# (model, system+tools hash) → cache resource name
_caches: dict[tuple[str, str], str] = {}
# (model, system+tools hash) → True if we already determined this prefix can't be cached
_uncacheable: set[tuple[str, str]] = set()


def _get_client() -> Any:
    global _client
    if _client is not None:
        return _client
    key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ConfigError(
            "GOOGLE_API_KEY (or GEMINI_API_KEY) not set (required for Google provider)"
        )
    try:
        from google import genai
    except ImportError as e:
        raise ConfigError(
            "google-genai package not installed. Install with: "
            "pip install 'google-genai>=0.3'"
        ) from e
    _client = genai.Client(api_key=key)
    return _client


def _prefix_hash(system_text: str, tools: list[dict[str, Any]] | None) -> str:
    h = hashlib.sha256()
    h.update(system_text.encode("utf-8"))
    if tools:
        for t in tools:
            h.update(t.get("name", "").encode("utf-8"))
    return h.hexdigest()[:16]


def _classify(e: Exception) -> tuple[str, str | None]:
    msg = str(e)
    low = msg.lower()
    if "api key" in low or "unauthenticated" in low or "permission_denied" in low:
        return ("Gemini API key rejected", "Verify GOOGLE_API_KEY / GEMINI_API_KEY")
    if "quota" in low or "resource_exhausted" in low:
        return ("Gemini quota exhausted", "Wait, or raise the quota in Google AI Studio")
    if "rate" in low and "limit" in low:
        return ("Rate-limited by Gemini", "Wait, or lower --concurrency")
    if "not found" in low and "model" in low:
        return ("Gemini model not available on your account", None)
    return (f"Gemini API call failed: {e}", None)


async def _try_create_cache(
    *, model: str, system_text: str, tools_decl: list[dict[str, Any]]
) -> str | None:
    """Best-effort cache create. Returns cache name or None if too small."""
    client = _get_client()
    try:
        from google.genai import types as gtypes

        cfg = gtypes.CreateCachedContentConfig(
            system_instruction=system_text,
            ttl="3600s",
        )
        if tools_decl:
            cfg.tools = [gtypes.Tool(function_declarations=tools_decl)]
        cached = await client.aio.caches.create(model=model, config=cfg)
        return cached.name
    except Exception as e:
        # Most common failure: prefix too small for the minimum cacheable token count.
        msg = str(e).lower()
        if "minimum" in msg or "too small" in msg or "invalid_argument" in msg:
            log.debug("gemini cache skipped (prefix too small): %s", e)
            return None
        log.debug("gemini cache create failed (continuing without cache): %s", e)
        return None


async def create_message(
    *,
    model: str,
    max_tokens: int,
    system: Any = None,
    messages: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    tool_choice: dict[str, Any] | None = None,
    **_: Any,
) -> Response:
    client = _get_client()
    try:
        from google.genai import types as gtypes
    except ImportError as e:
        raise ConfigError("google-genai not installed") from e

    system_text = flatten_system(system)
    tools_decl = [to_gemini_function(t) for t in (tools or [])]

    # Build user contents. We only have user messages (one in our pipeline).
    user_parts: list[Any] = []
    for m in messages or []:
        if m["role"] != "user":
            continue
        content = m["content"]
        if isinstance(content, list):
            for b in content:
                if b.get("type") == "text":
                    user_parts.append(gtypes.Part(text=b["text"]))
        else:
            user_parts.append(gtypes.Part(text=str(content)))

    # Attempt explicit caching — only worth it if there's a meaningful prefix.
    key = (model, _prefix_hash(system_text, tools))
    cache_name: str | None = _caches.get(key)
    if cache_name is None and key not in _uncacheable and (system_text or tools_decl):
        cache_name = await _try_create_cache(
            model=model, system_text=system_text, tools_decl=tools_decl
        )
        if cache_name:
            _caches[key] = cache_name
        else:
            _uncacheable.add(key)

    cfg_kwargs: dict[str, Any] = {"max_output_tokens": max_tokens}
    if cache_name:
        cfg_kwargs["cached_content"] = cache_name
    else:
        if system_text:
            cfg_kwargs["system_instruction"] = system_text
        if tools_decl:
            cfg_kwargs["tools"] = [gtypes.Tool(function_declarations=tools_decl)]
    if tools_decl and tool_choice and tool_choice.get("type") == "tool":
        cfg_kwargs["tool_config"] = gtypes.ToolConfig(
            function_calling_config=gtypes.FunctionCallingConfig(
                mode="ANY",
                allowed_function_names=[tool_choice["name"]],
            )
        )

    config = gtypes.GenerateContentConfig(**cfg_kwargs)
    contents = [gtypes.Content(role="user", parts=user_parts)]

    log.debug(
        "gemini.generate model=%s cache=%s tools=%s",
        model, bool(cache_name), bool(tools_decl),
    )
    try:
        resp = await client.aio.models.generate_content(
            model=model, contents=contents, config=config
        )
    except Exception as e:
        short, hint = _classify(e)
        log.debug("gemini call failed: %s: %s", type(e).__name__, e)
        raise ApiError(short, hint=hint) from e

    blocks: list[Any] = []
    candidate = resp.candidates[0] if resp.candidates else None
    finish = (getattr(candidate, "finish_reason", None) or "").upper() if candidate else ""
    parts = (candidate.content.parts if candidate and candidate.content else []) or []
    for p in parts:
        fn = getattr(p, "function_call", None)
        if fn is not None:
            blocks.append(ToolUseBlock(name=fn.name, input=dict(fn.args or {})))
        elif getattr(p, "text", None):
            blocks.append(TextBlock(text=p.text))

    stop_reason = {
        "STOP": "end_turn",
        "MAX_TOKENS": "max_tokens",
        "TOOL_CALLS": "tool_use",
    }.get(str(finish), str(finish).lower() or None)
    if any(isinstance(b, ToolUseBlock) for b in blocks):
        stop_reason = "tool_use"

    usage_obj = Usage()
    u = getattr(resp, "usage_metadata", None)
    if u is not None:
        prompt = int(getattr(u, "prompt_token_count", 0) or 0)
        cached = int(getattr(u, "cached_content_token_count", 0) or 0)
        usage_obj.input_tokens = max(0, prompt - cached)
        usage_obj.output_tokens = int(getattr(u, "candidates_token_count", 0) or 0)
        usage_obj.cache_read_input_tokens = cached

    full_id = f"google/{model}"
    get_tally().record_usage(full_id, usage_obj)

    return Response(content=blocks, stop_reason=stop_reason, usage=usage_obj)
