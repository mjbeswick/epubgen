from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

# USD per million tokens. Calibrated against real billing data 2026-05;
# verify at https://console.anthropic.com/pricing if estimates drift.
ANTHROPIC_RATES = {
    "claude-opus-4-7":   {"in": 5.00, "out": 25.00, "cache_w":  6.25, "cache_r": 0.50},
    "claude-opus-4-6":   {"in": 5.00, "out": 25.00, "cache_w":  6.25, "cache_r": 0.50},
    "claude-sonnet-4-6": {"in": 3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
    "claude-haiku-4-5":  {"in": 0.80, "out":  4.00, "cache_w":  1.00, "cache_r": 0.08},
}
_FALLBACK_RATES = ANTHROPIC_RATES["claude-sonnet-4-6"]

# OpenAI gpt-image-1 standard quality, ~1024 px.
OPENAI_IMAGE_USD = 0.04


def rates_for(model: str) -> dict[str, float]:
    return ANTHROPIC_RATES.get(model, _FALLBACK_RATES)


def estimate_book_cost(
    model: str, *, chapters: int = 12, words_per_chapter: int = 3500
) -> float:
    """Rough USD estimate for a generated book at a given model's rates.

    Calibrated against real runs (~$3 for a 10-chapter opus-4-7 book). The
    answer is approximate — chapter count and length are model-decided, and
    cache hit rates depend on prompt stability — but it's sufficient for
    comparing models in the picker.
    """
    r = rates_for(model)

    outline_in = 2_500
    outline_out = 10_000
    refine_calls = 2
    refine_in_per = 2_000
    refine_out_per = 1_500
    cache_prefix = 8_000  # style guide + outline JSON, cached after the first chapter
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
    "claude-opus-4-7": "Best quality, slowest, most expensive",
    "claude-opus-4-6": "Same family as 4-7; one rev older",
    "claude-sonnet-4-6": "Strong middle ground — good polish, ~5× cheaper than Opus",
    "claude-haiku-4-5": "Fast and cheap; rougher prose, fine for cheatsheets/refs",
}


def model_oneliner(model: str) -> str:
    return _MODEL_ONELINERS.get(model, "")


@dataclass
class Tally:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    api_calls: int = 0
    images: int = 0
    model: str = "claude-sonnet-4-6"
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
                self.model = model

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
        return [
            f"  Model:      {self.model}",
            f"  API calls:  {self.api_calls}",
            f"  Input:      {self.input_tokens:>9,} tok  ${in_usd:.4f}",
            f"  Output:     {self.output_tokens:>9,} tok  ${out_usd:.4f}",
            f"  Cache wr.:  {self.cache_creation_tokens:>9,} tok  ${cw_usd:.4f}",
            f"  Cache rd.:  {self.cache_read_tokens:>9,} tok  ${cr_usd:.4f}",
            f"  Images:     {self.images:>9}      ${img_usd:.4f}",
            f"  Total:      ${self.total_usd:.4f}",
            "  (estimate — see console.anthropic.com for actual billing)",
        ]


_tally: Tally | None = None


def get_tally() -> Tally:
    global _tally
    if _tally is None:
        _tally = Tally()
    return _tally


def reset_tally(model: str = "claude-sonnet-4-6") -> Tally:
    global _tally
    _tally = Tally(model=model)
    return _tally
