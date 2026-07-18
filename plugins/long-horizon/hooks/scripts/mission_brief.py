#!/usr/bin/env python3
"""SessionStart: inject the mission brief so a fresh session knows what is in flight.

This is the structural half of resumability (ADR-0011): missions are durable state, and this hook
is how a stateless session discovers them without a human re-brief. It emits the Claude Code
SessionStart contract — additionalContext — with a few compact lines: id, priority, progress, and
the next open step (or the blocker).

Silent by design when nothing is in flight: a brief that always speaks costs context in every
session that has nothing to do with any mission. Non-blocking and best-effort throughout — a
missing brief is a session that asks, not a session that breaks.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def find_repo(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    return None


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        event = {}

    cwd = Path(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    repo = find_repo(cwd)
    if repo is None:
        sys.exit(0)

    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
    mission_tool = plugin_root / "scripts" / "mission.py"
    if not mission_tool.is_file():
        sys.exit(0)

    missions_dir = os.environ.get("AGENTIC_OS_MISSIONS_DIR") or str(repo / "memory" / "missions")
    if not Path(missions_dir).is_dir():
        sys.exit(0)

    try:
        result = subprocess.run(
            [sys.executable, str(mission_tool), "--dir", missions_dir, "brief"],
            capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        sys.exit(0)

    brief = result.stdout.strip()
    if result.returncode != 0 or not brief:
        sys.exit(0)  # nothing in flight — silence is the right brief

    context = (
        f"{brief}\n"
        "These are durable missions (memory/missions/) resuming across sessions. To act on one: "
        "/mission show <id> for full state, advance with mission.py step-done, and update state as "
        "you go — the file, not this session, is the memory of the goal (ADR-0011)."
    )
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
