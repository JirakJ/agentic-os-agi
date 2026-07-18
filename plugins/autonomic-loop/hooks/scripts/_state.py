#!/usr/bin/env python3
"""Shared state for the autonomic loop's hooks.

The loop's working state is three small files in the plugin data dir — none of it is source of
truth, all of it is rebuildable, so it lives outside git by design (ADR-0003's derived-data rule):

  state/dirty-<session>.json   what core paths this session touched (the sentinel writes it,
                               a green verification deletes it)
  state/last-verify.json       the last verified eval state: sha, ts, aggregate, regressions
  state/pending-proposals.json proposals staged by the session-end pulse for the next brief

Every hook honours the kill switch: AGENTIC_OS_AUTONOMIC=off|0|false disables the whole layer
without uninstalling anything (ADR-0014). And every hook is non-blocking on its own failure —
a broken autonomic loop must degrade to the manual system, never to a broken session.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def autonomic_off() -> bool:
    return os.environ.get("AGENTIC_OS_AUTONOMIC", "on").strip().lower() in ("off", "0", "false")


def read_event() -> dict:
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def marketplace_root(start: Path) -> Path | None:
    for candidate in [start, *start.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    return None


def project_root(event: dict) -> Path | None:
    cwd = Path(event.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    return marketplace_root(cwd)


def state_dir() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(raw) if raw else Path.home() / ".claude" / "plugins" / "data" / "autonomic-loop"
    target = base / "state"
    target.mkdir(parents=True, exist_ok=True)
    return target


def dirty_path(session_id: str) -> Path:
    safe = "".join(c for c in session_id if c.isalnum() or c in "-_")[:64] or "unknown"
    return state_dir() / f"dirty-{safe}.json"


def read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_json(path: Path, payload: dict) -> None:
    try:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")
