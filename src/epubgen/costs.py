from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

# USD per million tokens. Verified against published pricing 2026-05; see provider
# pricing pages for the source of truth.
# Anthropic: https://docs.anthropic.com/en/docs/about-claude/pricing
# OpenAI:    https://openai.com/api/pricing/
# Google:    https://ai.google.dev/gemini-api/docs/pricing
# DeepSeek:  https://api-docs.deepseek.com/quick_start/pricing
# OpenRouter pass-through pricing varies — we use indicative numbers.
RATES: dict[str, dict[str, float]] = {
    # Anthropic — explicit cache_control breakpoints; cache_w/cache_r match Anthropic semantics.
    "anthropic/claude-opus-4-7":   {"in": 5.00, "out": 25.00, "cache_w":  6.25, "cache_r": 0.50},
    "anthropic/claude-opus-4-6":   {"in": 5.00, "out": 25.00, "cache_w":  6.25, "cache_r": 0.50},
    "anthropic/claude-sonnet-4-6": {"in": 3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
    "anthropic/claude-haiku-4-5":  {"in": 0.80, "out":  4.00, "cache_w":  1.00, "cache_r": 0.08},
    # OpenAI — auto prefix caching; cache_w == in (no separate write fee), cache_r ~= 50% of in.
    "openai/gpt-5":      {"in": 1.25, "out": 10.00, "cache_w": 1.25, "cache_r": 0.125},
    "openai/gpt-5-mini": {"in": 0.25, "out":  2.00, "cache_w": 0.25, "cache_r": 0.025},
    "openai/gpt-5-nano": {"in": 0.05, "out":  0.40, "cache_w": 0.05, "cache_r": 0.005},
    # Google Gemini — explicit caches.create; cache_w stored on a per-token-hour basis but we
    # roll the create cost into cache_w as a one-shot approximation.
    "google/gemini-2.5-pro":   {"in": 1.25, "out": 10.00, "cache_w": 1.25, "cache_r": 0.31},
    "google/gemini-2.5-flash": {"in": 0.30, "out":  2.50, "cache_w": 0.30, "cache_r": 0.075},
    # DeepSeek — auto prefix caching; cache_r ~= 10% of input rate.
    "deepseek/deepseek-chat":     {"in": 0.27, "out": 1.10, "cache_w": 0.27, "cache_r": 0.07},
    "deepseek/deepseek-reasoner": {"in": 0.55, "out": 2.19, "cache_w": 0.55, "cache_r": 0.14},
    # OpenRouter — billed pass-through; figures here are indicative for the seeded models only.
    "openrouter/anthropic/claude-sonnet-4.5": {"in": 3.00, "out": 15.00, "cache_w": 3.75, "cache_r": 0.30},  # noqa: E501
    "openrouter/openai/gpt-5": {"in": 1.25, "out": 10.00, "cache_w": 1.25, "cache_r": 0.125},
    "openrouter/google/gemini-2.5-flash": {"in": 0.30, "out": 2.50, "cache_w": 0.30, "cache_r": 0.075},  # noqa: E501
    "openrouter/deepseek/deepseek-chat": {"in": 0.27, "out": 1.10, "cache_w": 0.27, "cache_r": 0.07},  # noqa: E501
    "openrouter/meta-llama/llama-3.3-70b-instruct": {"in": 0.13, "out": 0.40, "cache_w": 0.13, "cache_r": 0.13},  # noqa: E501
}

_FALLBACK_RATES = RATES["anthropic/claude-sonnet-4-6"]

# Back-compat alias used by older tests.
ANTHROPIC_RATES = {
    k.removeprefix("anthropic/"): v
    for k, v in RATES.items()
    if k.startswith("anthropic/")
}

# OpenAI gpt-image-1 standard quality, ~1024 px.
OPENAI_IMAGE_USD = 0.04


def _normalize(model: str) -> str:
    if "/" in model:
        return model
    # Bare legacy id → assume Anthropic.
    return f"anthropic/{model}"


def rates_for(model: str) -> dict[str, float]:
    return RATES.get(_normalize(model), _FALLBACK_RATES)


def estimate_book_cost(
    model: str, *, chapters: int = 12, words_per_chapter: int = 3500
) -> float:
    """Rough USD estimate for a generated book at a given model's rates."""
    r = rates_for(model)

    outline_in = 2_500
    outline_out = 10_000
    refine_calls = 2
    refine_in_per = 2_000
    refine_out_per = 1_500
    cache_prefix = 8_000
    chapter_fresh_in_per = 700
    chapter_out_per = int(words_per_chapter * 1.3)

    input_tok = outline_in + refine_calls * refine_in_per + chapter_fresh_in_per * chapters
    output_tok = outline_out + refine_calls * refine_out_per + chapter_out_per * chapters
    cache_create = cache_prefix
    cache_read = cache_prefix * max(0, chapters - 1)

    return (
        input_tok * r["in"]
        + output_tok * r["out"]
        + cache_create * r["cache_w"]
        + cache_read * r["cache_r"]
    ) / 1_000_000


_MODEL_ONELINERS = {
    "anthropic/claude-opus-4-7": "Best Anthropic prose — slowest, most expensive",
    "anthropic/claude-opus-4-6": "Same family as 4-7; one rev older",
    "anthropic/claude-sonnet-4-6": "Strong middle ground — good polish, ~5× cheaper than Opus",
    "anthropic/claude-haiku-4-5": "Fast and cheap; rougher prose",
    "openai/gpt-5":      "OpenAI flagship — strong instruction following",
    "openai/gpt-5-mini": "Cheaper GPT-5; good drafting workhorse",
    "openai/gpt-5-nano": "Cheapest OpenAI; fine for refs/cheatsheets",
    "google/gemini-2.5-pro":   "Strong Gemini — long context, good quality",
    "google/gemini-2.5-flash": "Cheapest credible option for bulk drafting",
    "deepseek/deepseek-chat":     "DeepSeek V3.2 — strong cost/quality ratio",
    "deepseek/deepseek-reasoner": "DeepSeek R1 — reasoning model; slower",
}


def model_oneliner(model: str) -> str:
    return _MODEL_ONELINERS.get(_normalize(model), "via OpenRouter / pass-through")


@dataclass
class Tally:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    api_calls: int = 0
    images: int = 0
    model: str = "anthropic/claude-sonnet-4-6"
    _lock: Lock = field(default_factory=Lock, repr=False)

    def record_usage(self, model: str, usage: Any) -> None:
        if usage is None:
            return
        i = int(getattr(usage, "input_tokens", 0) or 0)
        o = int(getattr(usage, "output_tokens", 0) or 0)
        cc = int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        cr = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        with self._lock:
            self.api_calls += 1
            self.input_tokens += i
            self.output_tokens += o
            self.cache_creation_tokens += cc
            self.cache_read_tokens += cr
            if model:
                self.model = _normalize(model)

    def record_image(self) -> None:
        with self._lock:
            self.images += 1

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    @property
    def total_usd(self) -> float:
        r = rates_for(self.model)
        usd = (
            self.input_tokens * r["in"]
            + self.output_tokens * r["out"]
            + self.cache_creation_tokens * r["cache_w"]
            + self.cache_read_tokens * r["cache_r"]
        ) / 1_000_000
        usd += self.images * OPENAI_IMAGE_USD
        return usd

    def summary_lines(self) -> list[str]:
        r = rates_for(self.model)
        in_usd = self.input_tokens * r["in"] / 1_000_000
        out_usd = self.output_tokens * r["out"] / 1_000_000
        cw_usd = self.cache_creation_tokens * r["cache_w"] / 1_000_000
        cr_usd = self.cache_read_tokens * r["cache_r"] / 1_000_000
        img_usd = self.images * OPENAI_IMAGE_USD
        provider = self.model.partition("/")[0] or "?"
        return [
            f"  Model:      {self.model}",
            f"  Provider:   {provider}",
            f"  API calls:  {self.api_calls}",
            f"  Input:      {self.input_tokens:>9,} tok  ${in_usd:.4f}",
            f"  Output:     {self.output_tokens:>9,} tok  ${out_usd:.4f}",
            f"  Cache wr.:  {self.cache_creation_tokens:>9,} tok  ${cw_usd:.4f}",
            f"  Cache rd.:  {self.cache_read_tokens:>9,} tok  ${cr_usd:.4f}",
            f"  Images:     {self.images:>9}      ${img_usd:.4f}",
            f"  Total:      ${self.total_usd:.4f}",
            "  (estimate — see provider console for actual billing)",
        ]


_tally: Tally | None = None


def get_tally() -> Tally:
    global _tally
    if _tally is None:
        _tally = Tally()
    return _tally


def reset_tally(model: str = "anthropic/claude-sonnet-4-6") -> Tally:
    global _tally
    _tally = Tally(model=_normalize(model))
    return _tally
