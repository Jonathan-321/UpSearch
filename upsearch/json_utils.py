"""Utilities for reading structured JSON from model output.

Cheap models occasionally return valid reasoning with slightly invalid JSON:
markdown fences, text before/after the object, smart quotes, invalid escapes, or
truncated URL-looking strings. Agents should not silently collapse to empty
outputs when that happens.
"""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _balanced_json_slice(text: str) -> str | None:
    """Return the first balanced JSON object/array substring, if present."""
    start = -1
    opening = ""
    for i, ch in enumerate(text):
        if ch in "{[":
            start = i
            opening = ch
            break
    if start == -1:
        return None

    closing = "}" if opening == "{" else "]"
    stack = [closing]
    in_string = False
    escape = False

    for i in range(start + 1, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack or ch != stack[-1]:
                return None
            stack.pop()
            if not stack:
                return text[start : i + 1]
    return None


def _repair_json_text(text: str) -> str:
    text = _strip_code_fences(text)
    text = text.replace("\u201c", '"').replace("\u201d", '"').replace("\u2018", "'").replace("\u2019", "'")
    text = text.replace("\ufeff", "")
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Some models emit python-style nulls/bools in otherwise JSON-looking dicts.
    text = re.sub(r"\bNone\b", "null", text)
    text = re.sub(r"\bTrue\b", "true", text)
    text = re.sub(r"\bFalse\b", "false", text)
    # Escape stray backslashes that are not valid JSON escapes.
    text = re.sub(r"\\(?![\"\\/bfnrtu])", r"\\\\", text)
    return text


def parse_model_json(text: str, default: Any) -> Any:
    """Parse a model JSON response with best-effort repair.

    Returns ``default`` instead of raising. This keeps agent failure explicit in
    validators while avoiding empty packets from one malformed character.
    """
    if not text:
        return default

    candidates = [_strip_code_fences(text)]
    sliced = _balanced_json_slice(candidates[0])
    if sliced:
        candidates.insert(0, sliced)

    for candidate in list(candidates):
        repaired = _repair_json_text(candidate)
        if repaired not in candidates:
            candidates.append(repaired)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    # Last resort: many malformed model outputs are Python-literal-ish. Use
    # literal_eval only after JSON parsing fails, never exec/eval.
    for candidate in candidates:
        try:
            return ast.literal_eval(candidate)
        except (SyntaxError, ValueError):
            continue

    return default


def parse_model_json_object(text: str, default: dict | None = None) -> dict:
    parsed = parse_model_json(text, default or {})
    return parsed if isinstance(parsed, dict) else (default or {})
