#!/usr/bin/env python3
"""PostToolUse: mark the session core-dirty when an edit lands under plugins/ or adr/.

Silent bookkeeping — this is the sensor half of verify-on-change (ADR-0014). The Stop hook reads
the marker and decides whether a verification run is owed; a session that never touched core logic
never pays for one. Always exits 0; a lost marker degrades to a skipped verification, never to a
broken edit.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _state import (autonomic_off, dirty_path, now, project_root,  # noqa: E402
                    read_event, read_json, write_json)

CORE_PREFIXES = ("plugins/", "adr/")


def main() -> None:
    if autonomic_off():
        sys.exit(0)
    event = read_event()
    session_id = event.get("session_id") or event.get("session") or ""
    if not session_id:
        sys.exit(0)

    root = project_root(event)
    if root is None:
        sys.exit(0)

    tool_input = event.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    if not raw:
        sys.exit(0)

    try:
        rel = Path(raw).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        sys.exit(0)  # outside the marketplace — not core logic
    if not rel.startswith(CORE_PREFIXES):
        sys.exit(0)

    marker = dirty_path(session_id)
    payload = read_json(marker) or {"session": session_id, "first": now(), "paths": []}
    if rel not in payload["paths"]:
        payload["paths"].append(rel)
    payload["last"] = now()
    write_json(marker, payload)
    sys.exit(0)


if __name__ == "__main__":
    main()
