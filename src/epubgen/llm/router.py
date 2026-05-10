from __future__ import annotations

from typing import Any

from epubgen.errors import ConfigError

# Catalog of supported models. Keep this list in sync with costs.RATES.
# Each entry: provider/model id and a one-liner.
PROVIDERS: dict[str, dict[str, str]] = {
    "anthropic": {
        "anthropic/claude-opus-4-7":   "Best Anthropic prose — slowest, most expensive",
        "anthropic/claude-opus-4-6":   "Same family as 4-7; one rev older",
        "anthropic/claude-sonnet-4-6": "Strong middle ground — good polish, ~5× cheaper than Opus",
        "anthropic/claude-haiku-4-5":  "Fast and cheap; rougher prose",
    },
    "openai": {
        "openai/gpt-5":      "OpenAI flagship — strong instruction following",
        "openai/gpt-5-mini": "Cheaper GPT-5; good drafting workhorse",
        "openai/gpt-5-nano": "Cheapest OpenAI; fine for refs/cheatsheets",
    },
    "google": {
        "google/gemini-2.5-pro":   "Strong Gemini — long context, good quality",
        "google/gemini-2.5-flash": "Cheapest credible option for bulk drafting",
    },
    "deepseek": {
        "deepseek/deepseek-chat":     "DeepSeek V3.2 — strong cost/quality ratio",
        "deepseek/deepseek-reasoner": "DeepSeek R1 — reasoning model; slower",
    },
    "openrouter": {
        # OpenRouter is a gateway — users pass any model id after the slash.
        # We seed a few popular ones; the picker accepts arbitrary tail.
        "openrouter/anthropic/claude-sonnet-4.5":      "via OpenRouter",
        "openrouter/openai/gpt-5":                     "via OpenRouter",
        "openrouter/google/gemini-2.5-flash":          "via OpenRouter",
        "openrouter/deepseek/deepseek-chat":           "via OpenRouter",
        "openrouter/meta-llama/llama-3.3-70b-instruct":"via OpenRouter (open-weights)",
    },
}

KNOWN_MODELS: list[str] = [m for d in PROVIDERS.values() for m in d]

# Bare ids (no provider/) we accept for back-compat. Maps to provider/full-id.
_LEGACY_ALIASES: dict[str, str] = {
    name.split("/", 1)[1]: name
    for name in PROVIDERS["anthropic"]
}


def normalize_model(model_id: str) -> str:
    """Apply legacy alias rules. `claude-sonnet-4-6` → `anthropic/claude-sonnet-4-6`."""
    if "/" in model_id:
        return model_id
    if model_id in _LEGACY_ALIASES:
        return _LEGACY_ALIASES[model_id]
    # Unknown bare id — assume Anthropic to preserve old behavior.
    return f"anthropic/{model_id}"


def parse_model(model_id: str) -> tuple[str, str]:
    """Split `provider/model` into (provider, model)."""
    full = normalize_model(model_id)
    provider, _, model = full.partition("/")
    if not provider or not model:
        raise ConfigError(f"invalid model id: {model_id!r} (expected `provider/model`)")
    return provider, model


def provider_of(model_id: str) -> str:
    return parse_model(model_id)[0]


async def create_message(*, model: str, max_tokens: int, **kwargs: Any) -> Any:
    """Dispatch to the provider adapter. Returns an Anthropic-shaped response."""
    provider, native_model = parse_model(model)
    if provider == "anthropic":
        from epubgen.anthropic_client import create_message as anthropic_create

        return await anthropic_create(model=native_model, max_tokens=max_tokens, **kwargs)
    if provider in {"openai", "deepseek", "openrouter"}:
        from epubgen.llm._openai_compat import create_message as oc_create

        return await oc_create(
            provider=provider, model=native_model, max_tokens=max_tokens, **kwargs
        )
    if provider == "google":
        from epubgen.llm._gemini import create_message as gemini_create

        return await gemini_create(model=native_model, max_tokens=max_tokens, **kwargs)
    raise ConfigError(f"unsupported provider: {provider!r}")
