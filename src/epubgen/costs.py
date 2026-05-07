from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Any

# USD per million tokens. Update if Anthropic changes pricing.
ANTHROPIC_RATES = {
    "claude-opus-4-7":  {"in": 15.00, "out": 75.00, "cache_w": 18.75, "cache_r": 1.50},
    "claude-opus-4-6":  {"in": 15.00, "out": 75.00, "cache_w": 18.75, "cache_r": 1.50},
    "claude-sonnet-4-6":{"in":  3.00, "out": 15.00, "cache_w":  3.75, "cache_r": 0.30},
    "claude-haiku-4-5": {"in":  0.80, "out":  4.00, "cache_w":  1.00, "cache_r": 0.08},
}
_FALLBACK_RATES = ANTHROPIC_RATES["claude-opus-4-7"]

# OpenAI gpt-image-1 standard quality, ~1024 px.
OPENAI_IMAGE_USD = 0.04


def rates_for(model: str) -> dict[str, float]:
    return ANTHROPIC_RATES.get(model, _FALLBACK_RATES)


@dataclass
class Tally:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    api_calls: int = 0
    images: int = 0
    model: str = "claude-opus-4-7"
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
        ]


_tally: Tally | None = None


def get_tally() -> Tally:
    global _tally
    if _tally is None:
        _tally = Tally()
    return _tally


def reset_tally(model: str = "claude-opus-4-7") -> Tally:
    global _tally
    _tally = Tally(model=model)
    return _tally
