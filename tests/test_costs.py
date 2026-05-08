from dataclasses import dataclass
from pathlib import Path

from epubgen.costs import OPENAI_IMAGE_USD, Tally, rates_for, reset_tally


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


def test_record_usage_accumulates():
    t = Tally(model="claude-opus-4-7")
    t.record_usage("claude-opus-4-7", _Usage(input_tokens=1000, output_tokens=2000))
    t.record_usage("claude-opus-4-7", _Usage(input_tokens=500, output_tokens=1500))
    assert t.input_tokens == 1500
    assert t.output_tokens == 3500
    assert t.api_calls == 2


def test_total_usd_uses_per_model_rates():
    t = Tally(model="claude-opus-4-7")
    t.record_usage(
        "claude-opus-4-7",
        _Usage(
            input_tokens=1_000_000,
            output_tokens=1_000_000,
            cache_creation_input_tokens=1_000_000,
            cache_read_input_tokens=1_000_000,
        ),
    )
    r = rates_for("claude-opus-4-7")
    expected = r["in"] + r["out"] + r["cache_w"] + r["cache_r"]
    assert abs(t.total_usd - expected) < 1e-6


def test_image_cost():
    t = Tally()
    t.record_image()
    t.record_image()
    assert t.images == 2
    assert abs(t.total_usd - 2 * OPENAI_IMAGE_USD) < 1e-6


def test_unknown_model_falls_back_to_sonnet_rates():
    rates = rates_for("some-unreleased-model")
    assert rates["in"] == 3.00  # sonnet rate, the fallback default


def test_record_usage_handles_none():
    t = Tally()
    t.record_usage("claude-opus-4-7", None)
    assert t.api_calls == 0


def test_reset_tally_returns_fresh():
    t1 = reset_tally(model="claude-haiku-4-5")
    t1.record_image()
    t2 = reset_tally(model="claude-opus-4-7")
    assert t1 is not t2
    assert t2.images == 0
    assert t2.model == "claude-opus-4-7"


def test_summary_lines_includes_dollar_total():
    t = Tally(model="claude-opus-4-7")
    t.record_usage("claude-opus-4-7", _Usage(input_tokens=1000, output_tokens=2000))
    lines = t.summary_lines()
    assert any("Total:" in line and "$" in line for line in lines)
    assert any("API calls" in line for line in lines)
    assert any("estimate" in line.lower() for line in lines)


def test_estimate_book_cost_orders_by_model_tier():
    from epubgen.costs import estimate_book_cost

    haiku = estimate_book_cost("claude-haiku-4-5")
    sonnet = estimate_book_cost("claude-sonnet-4-6")
    opus = estimate_book_cost("claude-opus-4-7")
    assert haiku < sonnet < opus


def test_estimate_book_cost_scales_with_chapter_count():
    from epubgen.costs import estimate_book_cost

    short = estimate_book_cost("claude-sonnet-4-6", chapters=6)
    long = estimate_book_cost("claude-sonnet-4-6", chapters=14)
    assert long > short


def test_default_model_is_sonnet():
    from epubgen.costs import Tally
    from epubgen.schema import Options

    assert Options(topic="x", out=Path("/tmp/x.epub")).model == "claude-sonnet-4-6"
    assert Tally().model == "claude-sonnet-4-6"
