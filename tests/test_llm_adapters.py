"""Adapter response-parsing tests with monkeypatched SDK clients.

These don't hit real APIs — they pin the response→Anthropic-shape mapping so a
provider SDK update can't silently break the call sites that read
`resp.content[i].type` / `.text` / `.input` and `resp.usage.*`.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# OpenAI-compat adapter
# ---------------------------------------------------------------------------


class _FakeOpenAICompletions:
    def __init__(self, response: Any):
        self._response = response

    async def create(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        return self._response


class _FakeOpenAIChat:
    def __init__(self, response: Any):
        self.completions = _FakeOpenAICompletions(response)


class _FakeOpenAIClient:
    def __init__(self, response: Any):
        self.chat = _FakeOpenAIChat(response)


def _openai_text_response(text: str) -> Any:
    msg = SimpleNamespace(content=text, tool_calls=None)
    choice = SimpleNamespace(message=msg, finish_reason="stop")
    usage = SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=30,
        prompt_tokens_details=SimpleNamespace(cached_tokens=80),
    )
    return SimpleNamespace(choices=[choice], usage=usage)


def _openai_tool_response(name: str, args: dict[str, Any]) -> Any:
    tc = SimpleNamespace(
        id="call_1",
        function=SimpleNamespace(name=name, arguments=json.dumps(args)),
    )
    msg = SimpleNamespace(content=None, tool_calls=[tc])
    choice = SimpleNamespace(message=msg, finish_reason="tool_calls")
    usage = SimpleNamespace(prompt_tokens=50, completion_tokens=10)
    return SimpleNamespace(choices=[choice], usage=usage)


@pytest.mark.asyncio
async def test_openai_text_response_maps_to_text_block(monkeypatch):
    from epubgen.llm import _openai_compat

    fake = _FakeOpenAIClient(_openai_text_response("hello world"))
    monkeypatch.setattr(_openai_compat, "_client", lambda provider: fake)

    resp = await _openai_compat.create_message(
        provider="openai",
        model="gpt-5-mini",
        max_tokens=100,
        system=[{"type": "text", "text": "be brief"}],
        messages=[{"role": "user", "content": "hi"}],
    )
    assert len(resp.content) == 1
    assert resp.content[0].type == "text"
    assert resp.content[0].text == "hello world"
    assert resp.stop_reason == "end_turn"
    # cached_tokens deducted from input_tokens, surfaced as cache_read_input_tokens.
    assert resp.usage.cache_read_input_tokens == 80
    assert resp.usage.input_tokens == 40  # 120 - 80
    assert resp.usage.output_tokens == 30


@pytest.mark.asyncio
async def test_openai_tool_call_maps_to_tool_use_block(monkeypatch):
    from epubgen.llm import _openai_compat

    args = {"title": "x", "subtitle": "y"}
    fake = _FakeOpenAIClient(_openai_tool_response("emit_titles", args))
    monkeypatch.setattr(_openai_compat, "_client", lambda provider: fake)

    tool = {
        "name": "emit_titles",
        "description": "test",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    }
    resp = await _openai_compat.create_message(
        provider="openai",
        model="gpt-5-mini",
        max_tokens=100,
        messages=[{"role": "user", "content": "go"}],
        tools=[tool],
        tool_choice={"type": "tool", "name": "emit_titles"},
    )
    tool_blocks = [b for b in resp.content if b.type == "tool_use"]
    assert len(tool_blocks) == 1
    assert tool_blocks[0].name == "emit_titles"
    assert tool_blocks[0].input == args
    assert resp.stop_reason == "tool_use"
    # Verify the request shape too — tool_choice was translated.
    sent = fake.chat.completions.last_kwargs
    assert sent["tool_choice"] == {"type": "function", "function": {"name": "emit_titles"}}


@pytest.mark.asyncio
async def test_openai_uses_max_completion_tokens_for_reasoning_models(monkeypatch):
    from epubgen.llm import _openai_compat

    fake = _FakeOpenAIClient(_openai_text_response("ok"))
    monkeypatch.setattr(_openai_compat, "_client", lambda provider: fake)

    await _openai_compat.create_message(
        provider="openai",
        model="gpt-5",  # reasoning model family
        max_tokens=500,
        messages=[{"role": "user", "content": "hi"}],
    )
    sent = fake.chat.completions.last_kwargs
    assert sent.get("max_completion_tokens") == 500
    assert "max_tokens" not in sent

    # Non-reasoning model uses max_tokens.
    await _openai_compat.create_message(
        provider="deepseek",
        model="deepseek-chat",
        max_tokens=500,
        messages=[{"role": "user", "content": "hi"}],
    )
    sent = fake.chat.completions.last_kwargs
    assert sent.get("max_tokens") == 500
    assert "max_completion_tokens" not in sent


@pytest.mark.asyncio
async def test_openai_flattens_system_blocks(monkeypatch):
    from epubgen.llm import _openai_compat

    fake = _FakeOpenAIClient(_openai_text_response("ok"))
    monkeypatch.setattr(_openai_compat, "_client", lambda provider: fake)

    await _openai_compat.create_message(
        provider="openai",
        model="gpt-5-mini",
        max_tokens=100,
        system=[
            {"type": "text", "text": "block-A", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "block-B"},
        ],
        messages=[{"role": "user", "content": "hi"}],
    )
    msgs = fake.chat.completions.last_kwargs["messages"]
    assert msgs[0]["role"] == "system"
    assert "block-A" in msgs[0]["content"]
    assert "block-B" in msgs[0]["content"]
