#!/usr/bin/env python3
"""PostToolUse recorder: append-only audit trail of every tool call.

One JSON object per line, one file per day. This is the observability substrate — what the fleet
did, when, to what, and whether it worked. Feeds fleet analytics and answers the only question
that matters after an incident: what actually happened.

Deliberately records no file contents and no command output. The trail is about actions, not
payloads; a trail full of payloads is a second copy of your secrets.

Trail: ${CLAUDE_PLUGIN_DATA}/audit/YYYY-MM-DD.jsonl
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (classify, component_id, marketplace_root, plugin_data,  # noqa: E402
                  proceed, project_dir, read_event, tool_paths)

MAX_SUMMARY = 120


def summarise(event: dict) -> str | None:
    """A short, non-sensitive label for what the call did."""
    tool = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    if tool == "Bash":
        command = str(tool_input.get("command", "")).strip().splitlines()
        return (command[0][:MAX_SUMMARY] if command else None)
    if tool in {"Grep", "Glob"}:
        return str(tool_input.get("pattern", ""))[:MAX_SUMMARY]
    if tool == "Task":
        return str(tool_input.get("subagent_type", ""))[:MAX_SUMMARY]
    if tool in {"WebFetch", "WebSearch"}:
        return str(tool_input.get("url") or tool_input.get("query", ""))[:MAX_SUMMARY]
    return None


def main() -> None:
    event = read_event()
    tool = event.get("tool_name")
    if not tool:
        proceed()

    root = marketplace_root(project_dir(event))
    paths, components = [], []
    for raw in tool_paths(event):
        name = Path(raw).name
        paths.append(name)
        if root is None:
            continue
        try:
            rel = str(Path(raw).resolve().relative_to(root))
        except ValueError:
            continue
        if classify(rel):
            components.append(component_id(rel))

    response = event.get("tool_response")
    ok = True
    if isinstance(response, dict):
        ok = not (response.get("is_error") or response.get("error"))

    record = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "session": event.get("session_id"),
        "tool": tool,
        "ok": ok,
        "cwd": str(project_dir(event)),
    }
    if paths:
        record["files"] = paths[:10]
    if components:
        record["components"] = sorted(set(components))
    summary = summarise(event)
    if summary:
        record["summary"] = summary
    if event.get("tool_use_id"):
        record["tool_use_id"] = event["tool_use_id"]

    trail_dir = plugin_data() / "audit"
    trail_dir.mkdir(parents=True, exist_ok=True)
    trail = trail_dir / f"{time.strftime('%Y-%m-%d')}.jsonl"

    try:
        with trail.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # never let the trail break the work it is recording

    proceed()


if __name__ == "__main__":
    main()
