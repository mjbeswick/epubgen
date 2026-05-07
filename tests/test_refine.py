from pathlib import Path

from epubgen import anthropic_client
from epubgen.prompts.description import build_description_messages
from epubgen.prompts.refine import REFINE_TOOL, build_refine_messages
from epubgen.refine import refine_description, refine_topic
from epubgen.schema import Options, RefinedTopic
from epubgen.styles import load_style
from tests.fixtures.fake_anthropic import FakeAnthropic, tool_response


def test_refine_messages_cache_on_style():
    style = load_style("oreilly")
    msgs = build_refine_messages(style, "python performance")
    assert msgs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in msgs["system"][1]
    assert msgs["tool_choice"] == {"type": "tool", "name": "emit_titles"}
    assert msgs["tools"][0] is REFINE_TOOL


def test_refine_messages_with_hint_includes_steering():
    style = load_style("oreilly")
    msgs = build_refine_messages(style, "python performance", hint="punchier")
    user = msgs["messages"][0]["content"]
    assert "punchier" in user


def test_description_messages_cache_on_style():
    style = load_style("oreilly")
    framing = RefinedTopic(
        title="Fast Python",
        subtitle="A measurement-first guide",
        angle="Practical, evidence-driven optimization for working developers.",
    )
    msgs = build_description_messages(style, "python perf", framing)
    assert msgs["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert msgs["tool_choice"] == {"type": "tool", "name": "emit_description"}
    assert "Fast Python" in msgs["messages"][0]["content"]


async def test_refine_description_returns_string():
    framing = RefinedTopic(
        title="Fast Python",
        subtitle="A measurement-first guide",
        angle="Practical, evidence-driven optimization for working developers.",
    )
    long_desc = "A solid description that easily clears the eighty character minimum. " * 2
    fake = FakeAnthropic(handler=lambda _: tool_response({"description": long_desc}))
    anthropic_client.set_client(fake)
    try:
        out = await refine_description(
            load_style("oreilly"), "python perf", framing, model="claude-opus-4-7"
        )
        assert long_desc.strip() == out
    finally:
        anthropic_client.set_client(None)


def test_wizard_wrap_breaks_long_lines():
    from epubgen.wizard import _wrap

    long_angle = (
        "A working programmer's tour of QBASIC focused on writing useful, "
        "runnable software today, file I/O, screen modes, and SUBs without nostalgia."
    )
    out = _wrap(long_angle, indent=7, width=60)
    assert "\n" in out
    for line in out.split("\n"):
        # First line has no padding; continuation lines pre-padded with 7 spaces.
        bare = line.lstrip(" ")
        assert len(bare) <= 60


def test_description_metadata_yaml_includes_description():
    from epubgen.assemble import metadata_yaml
    from epubgen.schema import Beat, Chapter, Outline

    outline = Outline(
        title="X",
        topic="t",
        style="oreilly",
        chapters=[
            Chapter(
                number=i,
                title=f"C{i}",
                synopsis="A reasonable synopsis describing what this chapter covers.",
                beats=[Beat(summary="One beat here"), Beat(summary="Second beat here")],
                word_target=2000,
            )
            for i in range(1, 4)
        ],
    )
    opts = Options(topic="t", out=Path("/tmp/x.epub"), description="A great description.")
    text = metadata_yaml(outline, opts)
    assert "description" in text
    assert "A great description" in text


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
