"""Claude Code hook I/O helpers. Stdlib only. Never eval or shell-interpolate tool input."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

MAX_OUT = 9500  # stay under the 10k hook output cap

def home_dir() -> Path:
    d = Path(os.environ.get("JJ_HOME", str(Path.home() / ".jj-agentic-os")))
    d.mkdir(parents=True, exist_ok=True)
    return d

def read_input() -> dict[str, Any]:
    """Parse hook stdin JSON. Malformed input returns {} (callers decide fail-open/closed)."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except Exception:
        return {}

def _cap(s: str) -> str:
    return s if len(s) <= MAX_OUT else s[: MAX_OUT - 20] + "\n...[truncated]"

def allow() -> None:
    sys.exit(0)

def deny(reason: str) -> None:
    """PreToolUse hard deny via JSON on exit 0 (JSON channel; exit 2 would discard it)."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _cap(reason),
        }
    }))
    sys.exit(0)

def ask(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": _cap(reason),
        }
    }))
    sys.exit(0)

def post_block(reason: str) -> None:
    """PostToolUse: cannot undo, but decision=block feeds the reason back to Claude."""
    print(json.dumps({"decision": "block", "reason": _cap(reason)}))
    sys.exit(0)

def system_message(msg: str) -> None:
    print(json.dumps({"systemMessage": _cap(msg)}))
    sys.exit(0)

def pretool_context(ctx: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": _cap(ctx)}
    }))
    sys.exit(0)

def plain(text: str) -> None:
    """SessionStart / UserPromptSubmit inject plain stdout into context."""
    print(_cap(text))
    sys.exit(0)

def unlock_active(ttl_s: int = 600) -> bool:
    """Human override marker created by /gate-unlock. 10-minute TTL."""
    m = home_dir() / "gate-unlock"
    try:
        return m.exists() and (time.time() - m.stat().st_mtime) < ttl_s
    except OSError:
        return False
