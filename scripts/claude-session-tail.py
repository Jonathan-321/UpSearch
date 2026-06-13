#!/usr/bin/env python3
"""Read recent human/assistant text from a local Claude Code project session."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
    re.compile(r"\bwandb_v1_[A-Za-z0-9_-]{12,}\b"),
]


def redact(text: str) -> str:
    for pattern in SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def project_key(path: Path) -> str:
    return str(path.resolve()).replace("/", "-")


def text_parts(content: Any, include_tools: bool) -> list[str]:
    if isinstance(content, str):
        return [content]
    if not isinstance(content, list):
        return []

    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        item_type = item.get("type")
        if item_type == "text" and item.get("text"):
            parts.append(str(item["text"]))
        elif include_tools and item_type == "tool_use":
            parts.append(f"[tool: {item.get('name', 'unknown')}]")
    return parts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=".")
    parser.add_argument("--messages", type=int, default=12)
    parser.add_argument("--include-tools", action="store_true")
    parser.add_argument("--max-chars", type=int, default=2000)
    args = parser.parse_args()

    session_dir = Path.home() / ".claude" / "projects" / project_key(Path(args.project))
    sessions = sorted(session_dir.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)
    if not sessions:
        print(f"No Claude Code sessions found for {Path(args.project).resolve()}")
        return 1

    messages: list[tuple[str, str]] = []
    with sessions[-1].open(encoding="utf-8") as handle:
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = event.get("type")
            if role not in {"user", "assistant"}:
                continue
            content = event.get("message", {}).get("content")
            for part in text_parts(content, args.include_tools):
                cleaned = redact(part.strip())
                if cleaned:
                    messages.append((role, cleaned[: args.max_chars]))

    print(f"Session: {sessions[-1]}")
    for role, text in messages[-args.messages :]:
        print(f"\n## {role.title()}\n{text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
