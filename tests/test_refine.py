from pathlib import Path

from epubgen import anthropic_client
from epubgen.prompts.refine import REFINE_TOOL, build_refine_messages
from epubgen.refine import refine_topic
from epubgen.schema import Options
from epubgen.styles import load_style
from tests.fixtures.fake_anthropic import FakeAnthropic, tool_response


def test_refine_messages_cache_on_style():
    style = load_style("oreilly")
    msgs = build_refine_messages(style, "python performance")
    assert msgs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in msgs["system"][1]
    assert msgs["tool_choice"] == {"type": "tool", "name": "emit_titles"}
    assert msgs["tools"][0] is REFINE_TOOL


async def test_refine_returns_three():
    payload = {
        "suggestions": [
            {
                "title": f"Title {i}",
                "subtitle": f"A clarifying subtitle number {i}",
                "angle": f"What makes framing {i} different from the others.",
            }
            for i in range(1, 4)
        ]
    }
    fake = FakeAnthropic(handler=lambda _: tool_response(payload))
    anthropic_client.set_client(fake)
    try:
        out = await refine_topic(load_style("oreilly"), "python perf", model="claude-opus-4-7")
        assert len(out.suggestions) == 3
        assert out.suggestions[0].title == "Title 1"
    finally:
        anthropic_client.set_client(None)


def test_preferred_title_threads_into_outline_prompt():
    from epubgen.prompts.outline import build_outline_messages

    style = load_style("oreilly")
    opts = Options(
        topic="python perf",
        style="oreilly",
        out=Path("/tmp/x.epub"),
        preferred_title="Fast Python",
        preferred_subtitle="A measurement-first guide",
    )
    msgs = build_outline_messages(style, opts)
    user = msgs["messages"][0]["content"]
    assert "Fast Python" in user
    assert "A measurement-first guide" in user
