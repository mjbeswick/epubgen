from pathlib import Path

from epubgen.prompts.chapter import build_chapter_messages, canonical_outline_text
from epubgen.prompts.outline import OUTLINE_TOOL, build_outline_messages
from epubgen.schema import Beat, Chapter, Options, Outline
from epubgen.styles import load_style


def _opts(**kw):
    return Options(topic="Python perf", style="oreilly", out=Path("/tmp/x.epub"), **kw)


def _outline():
    return Outline(
        title="Python Performance",
        subtitle="A practical guide",
        topic="Python perf",
        style="oreilly",
        chapters=[
            Chapter(
                number=1,
                title="Profiling First",
                synopsis="Establish a measurement baseline before any optimization.",
                beats=[
                    Beat(summary="Why measure before optimizing"),
                    Beat(summary="cProfile vs py-spy walkthrough"),
                ],
                code_examples=["a cProfile harness", "a py-spy invocation"],
                word_target=3000,
            ),
            Chapter(
                number=2,
                title="Faster Loops",
                synopsis="Hot inner loops in Python and how to speed them up.",
                beats=[
                    Beat(summary="Why interpreter overhead matters"),
                    Beat(summary="Vectorize with numpy"),
                ],
                code_examples=["numpy vector vs python loop"],
                word_target=3000,
            ),
            Chapter(
                number=3,
                title="Native Extensions",
                synopsis="When to drop into C or Rust for hot code.",
                beats=[
                    Beat(summary="Cython vs PyO3 tradeoffs"),
                    Beat(summary="A small PyO3 example"),
                ],
                code_examples=["a tiny PyO3 module"],
                word_target=3000,
            ),
        ],
    )


def test_outline_messages_cache_only_on_style():
    style = load_style("oreilly")
    msgs = build_outline_messages(style, _opts())
    sys_blocks = msgs["system"]
    assert sys_blocks[0]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in sys_blocks[1]
    assert msgs["tool_choice"] == {"type": "tool", "name": "emit_outline"}
    assert msgs["tools"][0] is OUTLINE_TOOL
    assert all(m["role"] == "user" for m in msgs["messages"])


def test_chapter_messages_cache_breakpoints():
    style = load_style("oreilly")
    outline = _outline()
    msgs = build_chapter_messages(style, outline, outline.chapters[0], _opts())
    sys_blocks = msgs["system"]
    assert sys_blocks[0]["cache_control"] == {"type": "ephemeral"}  # style
    assert sys_blocks[1]["cache_control"] == {"type": "ephemeral"}  # outline
    assert "cache_control" not in sys_blocks[2]
    user = msgs["messages"][0]["content"]
    assert "Chapter 1" in user
    assert "Profiling First" in user
    # User message must NOT carry a cache breakpoint.
    assert isinstance(user, str)


def test_ereader_clause_only_when_ereader():
    style = load_style("oreilly")
    outline = _outline()
    plain = build_chapter_messages(style, outline, outline.chapters[0], _opts(ereader=False))
    ereader = build_chapter_messages(style, outline, outline.chapters[0], _opts(ereader=True))
    assert "≤60" not in plain["messages"][0]["content"]
    assert "≤60" in ereader["messages"][0]["content"]


def test_outline_prompt_lets_model_pick_words_when_unset():
    style = load_style("oreilly")
    msgs = build_outline_messages(style, _opts())  # words=None default
    user = msgs["messages"][0]["content"]
    assert "VARY the targets" in user
    assert "Target words per chapter: ~" not in user


def test_outline_prompt_locks_words_when_set():
    style = load_style("oreilly")
    msgs = build_outline_messages(style, _opts(words=2500))
    user = msgs["messages"][0]["content"]
    assert "~2500" in user
    assert "VARY the targets" not in user


def test_canonical_outline_is_byte_stable():
    o1 = _outline()
    o2 = _outline()
    assert canonical_outline_text(o1) == canonical_outline_text(o2)
