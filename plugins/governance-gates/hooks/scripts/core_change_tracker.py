#!/usr/bin/env python3
"""PostToolUse recorder: remember which core components this session touched.

The Stop gate needs to know what changed, but by then the tool payloads are gone. This writes a
per-session ledger the gate reads back. Non-blocking by construction — bookkeeping must never
interrupt work.

Ledger: ${CLAUDE_PLUGIN_DATA}/sessions/<session_id>.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _lib import (classify, component_id, marketplace_root, plugin_data,  # noqa: E402
                  proceed, project_dir, read_event, tool_paths)


def main() -> None:
    event = read_event()
    if event.get("tool_name") not in {"Write", "Edit", "MultiEdit", "NotebookEdit"}:
        proceed()

    root = marketplace_root(project_dir(event))
    if root is None:
        proceed()

    touched: dict[str, dict] = {}
    for raw in tool_paths(event):
        try:
            rel = str(Path(raw).resolve().relative_to(root))
        except ValueError:
            continue
        kind = classify(rel)
        if not kind:
            continue
        cid = component_id(rel)
        entry = touched.setdefault(cid, {"kind": kind, "paths": [], "last_touched": time.time()})
        if rel not in entry["paths"]:
            entry["paths"].append(rel)

    if not touched:
        proceed()

    session_id = event.get("session_id") or "unknown"
    ledger_dir = plugin_data() / "sessions"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    ledger = ledger_dir / f"{session_id}.json"

    try:
        state = json.loads(ledger.read_text(encoding="utf-8")) if ledger.is_file() else {}
    except (json.JSONDecodeError, OSError):
        state = {}

    components = state.setdefault("components", {})
    for cid, entry in touched.items():
        existing = components.setdefault(cid, {"kind": entry["kind"], "paths": []})
        existing["last_touched"] = entry["last_touched"]
        for path in entry["paths"]:
            if path not in existing["paths"]:
                existing["paths"].append(path)

    state["session_id"] = session_id
    state["root"] = str(root)
    state["updated"] = time.time()

    try:
        ledger.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError:
        pass  # a ledger we cannot write is a gate that stays quiet, not a session that breaks

    proceed()


if __name__ == "__main__":
    main()
