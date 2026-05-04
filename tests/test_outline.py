from pathlib import Path

import pytest

from epubgen import anthropic_client
from epubgen.errors import OutlineError
from epubgen.outline import generate_outline
from epubgen.schema import Options
from epubgen.styles import load_style
from tests.fixtures.fake_anthropic import FakeAnthropic, tool_response

VALID_PAYLOAD = {
    "title": "Python Performance",
    "subtitle": "A practical guide",
    "topic": "Python perf",
    "style": "oreilly",
    "chapters": [
        {
            "number": i,
            "title": f"Chapter {i}",
            "synopsis": "A reasonable synopsis describing what this chapter covers.",
            "beats": [
                {"summary": "First substantive beat for this chapter."},
                {"summary": "Second substantive beat for this chapter."},
            ],
            "code_examples": ["a small runnable example"],
            "word_target": 3000,
        }
        for i in range(1, 5)
    ],
}


def _opts():
    return Options(topic="Python perf", style="oreilly", out=Path("/tmp/x.epub"))


async def test_outline_validates_on_first_try():
    style = load_style("oreilly")
    fake = FakeAnthropic(handler=lambda _: tool_response(VALID_PAYLOAD))
    anthropic_client.set_client(fake)
    try:
        outline = await generate_outline(style, _opts())
        assert len(outline.chapters) == 4
        assert outline.title == "Python Performance"
        assert len(fake.messages.calls) == 1
    finally:
        anthropic_client.set_client(None)


async def test_outline_repairs_once():
    style = load_style("oreilly")
    bad = {**VALID_PAYLOAD, "chapters": VALID_PAYLOAD["chapters"][:2]}  # too few chapters
    responses = [tool_response(bad), tool_response(VALID_PAYLOAD)]
    fake = FakeAnthropic(handler=lambda _: responses.pop(0))
    anthropic_client.set_client(fake)
    try:
        outline = await generate_outline(style, _opts())
        assert len(outline.chapters) == 4
        assert len(fake.messages.calls) == 2
    finally:
        anthropic_client.set_client(None)


async def test_outline_raises_after_two_failures():
    style = load_style("oreilly")
    bad = {**VALID_PAYLOAD, "chapters": VALID_PAYLOAD["chapters"][:1]}
    fake = FakeAnthropic(handler=lambda _: tool_response(bad))
    anthropic_client.set_client(fake)
    try:
        with pytest.raises(OutlineError):
            await generate_outline(style, _opts())
        assert len(fake.messages.calls) == 2
    finally:
        anthropic_client.set_client(None)
