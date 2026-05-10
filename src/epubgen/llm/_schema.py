"""JSON-schema sanitizers for non-Anthropic providers.

Anthropic accepts JSON Schema draft 2020-12 directly, including `type: [X, "null"]`
union types. OpenAI strict mode and Gemini's OpenAPI 3.0 subset don't — they need
`type: X` + `nullable: true` (Gemini) or just no nulls (OpenAI strict). They also
reject some keywords entirely.

We rewrite the schema once per call; tool definitions stay in their authored form.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Keywords that Gemini's OpenAPI 3 dialect doesn't accept on object schemas.
_GEMINI_DROP = frozenset({"additionalProperties", "$schema", "definitions", "$defs"})


def _sanitize(node: Any, *, dialect: str) -> Any:
    if isinstance(node, list):
        return [_sanitize(n, dialect=dialect) for n in node]
    if not isinstance(node, dict):
        return node
    out: dict[str, Any] = {}
    typ = node.get("type")
    # Union with null → nullable + base type.
    if isinstance(typ, list):
        non_null = [t for t in typ if t != "null"]
        if "null" in typ and len(non_null) == 1:
            out["type"] = non_null[0]
            if dialect == "gemini":
                out["nullable"] = True
            # OpenAI strict mode forbids nullable; we just drop the null branch
            # (the model treats absent values fine since these fields are optional
            # via `required` lists, not via null). For OpenAI non-strict, leave it.
        elif non_null:
            # Multi-type union without null — pick the first; not common in our schemas.
            out["type"] = non_null[0]
    elif typ is not None:
        out["type"] = typ
    for k, v in node.items():
        if k == "type":
            continue
        if dialect == "gemini" and k in _GEMINI_DROP:
            continue
        if k in {"properties"} and isinstance(v, dict):
            out[k] = {pk: _sanitize(pv, dialect=dialect) for pk, pv in v.items()}
        elif k == "items" or isinstance(v, (dict, list)):
            out[k] = _sanitize(v, dialect=dialect)
        else:
            out[k] = v
    return out


def to_openai_tool(tool: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool → OpenAI function tool."""
    schema = _sanitize(deepcopy(tool["input_schema"]), dialect="openai")
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": schema,
        },
    }


def to_gemini_function(tool: dict[str, Any]) -> dict[str, Any]:
    """Anthropic tool → Gemini function_declaration."""
    schema = _sanitize(deepcopy(tool["input_schema"]), dialect="gemini")
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "parameters": schema,
    }


def flatten_system(system: list[dict[str, Any]] | str | None) -> str:
    """Concatenate Anthropic-style system blocks into a single string.

    Drops `cache_control` (auto-cache handles prefix caching on most providers).
    """
    if system is None:
        return ""
    if isinstance(system, str):
        return system
    parts = [b.get("text", "") for b in system if isinstance(b, dict)]
    return "\n\n".join(p for p in parts if p)
