"""Tests for the multi-provider router and schema conversion helpers."""

from __future__ import annotations

import pytest

from epubgen.errors import ConfigError
from epubgen.llm._schema import flatten_system, to_gemini_function, to_openai_tool
from epubgen.llm.router import (
    KNOWN_MODELS,
    PROVIDERS,
    normalize_model,
    parse_model,
    provider_of,
)


class TestModelIdParsing:
    def test_prefixed_id_passes_through(self):
        assert normalize_model("openai/gpt-5") == "openai/gpt-5"

    def test_legacy_anthropic_alias(self):
        assert normalize_model("claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"
        assert provider_of("claude-sonnet-4-6") == "anthropic"

    def test_unknown_bare_id_assumed_anthropic(self):
        # Future-proof: unknown bare ids fall back to anthropic prefix.
        assert provider_of("some-unreleased-model") == "anthropic"

    def test_parse_returns_provider_and_model(self):
        provider, model = parse_model("openai/gpt-5-mini")
        assert provider == "openai"
        assert model == "gpt-5-mini"

    def test_invalid_format_raises(self):
        with pytest.raises(ConfigError):
            parse_model("/missing-provider")
        with pytest.raises(ConfigError):
            parse_model("missing-model/")

    def test_openrouter_nested_id_preserved(self):
        provider, model = parse_model("openrouter/anthropic/claude-sonnet-4.5")
        assert provider == "openrouter"
        assert model == "anthropic/claude-sonnet-4.5"


class TestProviderCatalog:
    def test_known_models_includes_all_providers(self):
        provs = {m.partition("/")[0] for m in KNOWN_MODELS}
        assert {"anthropic", "openai", "google", "deepseek", "openrouter"} <= provs

    def test_providers_dict_consistent_with_known_models(self):
        flat = {m for d in PROVIDERS.values() for m in d}
        assert flat == set(KNOWN_MODELS)


class TestSchemaSanitizer:
    NULLABLE_TOOL = {
        "name": "emit",
        "description": "test",
        "input_schema": {
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string"},
                "subtitle": {"type": ["string", "null"]},
                "count": {"type": ["integer", "null"]},
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                    "additionalProperties": False,
                },
            },
        },
    }

    def test_openai_tool_strips_null_unions(self):
        tool = to_openai_tool(self.NULLABLE_TOOL)
        params = tool["function"]["parameters"]
        # Union with null reduced to base type; OpenAI strict can't handle nulls.
        assert params["properties"]["subtitle"]["type"] == "string"
        assert params["properties"]["count"]["type"] == "integer"
        # Wraps in OpenAI shape.
        assert tool["type"] == "function"
        assert tool["function"]["name"] == "emit"

    def test_gemini_function_uses_nullable_and_drops_extras(self):
        fn = to_gemini_function(self.NULLABLE_TOOL)
        sub = fn["parameters"]["properties"]["subtitle"]
        assert sub["type"] == "string"
        assert sub["nullable"] is True
        # additionalProperties dropped (Gemini OpenAPI subset doesn't accept it).
        items = fn["parameters"]["properties"]["items"]
        assert "additionalProperties" not in items


class TestSystemFlatten:
    def test_concatenates_text_blocks(self):
        blocks = [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]
        out = flatten_system(blocks)
        assert "first" in out and "second" in out

    def test_drops_cache_control(self):
        blocks = [
            {"type": "text", "text": "x", "cache_control": {"type": "ephemeral"}}
        ]
        # No exception; just text remains.
        assert flatten_system(blocks) == "x"

    def test_handles_none(self):
        assert flatten_system(None) == ""

    def test_handles_string(self):
        assert flatten_system("plain") == "plain"
