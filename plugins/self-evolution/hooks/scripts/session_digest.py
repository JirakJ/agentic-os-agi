#!/usr/bin/env python3
"""SessionEnd: append a compact session digest to the experience buffer.

Reads governance-gates' audit trail for the session that just ended and writes a one-line digest —
tool count, components touched, failures, span. This is the loop's "sense" step closing
automatically: it precomputes each session's shape so the miner and reflection have a per-session
record without rescanning the whole trail (ADR-0009).

It records only what the trail already holds — actions, components, success flags, never payloads
(ADR-0006) — so the digest inherits the trail's privacy property by construction.

Non-blocking and best-effort: a missing digest is a slightly thinner experience buffer, not a
broken session. If the trail cannot be found or read, this exits cleanly and writes nothing.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def read_event() -> dict:
    try:
        return json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return {}


def resolve_audit_dir() -> Path | None:
    candidates: list[Path] = []
    if os.environ.get("AGENTIC_OS_AUDIT_DIR"):
        candidates.append(Path(os.environ["AGENTIC_OS_AUDIT_DIR"]).expanduser())
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if data:
        candidates.append(Path(data).parent / "governance-gates" / "audit")
        candidates.append(Path(data) / "audit")
    candidates.append(Path.home() / ".claude" / "plugins" / "data" / "governance-gates" / "audit")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return None


def digest_dir() -> Path:
    raw = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(raw) if raw else Path.home() / ".claude" / "plugins" / "data" / "self-evolution"
    target = base / "evolution"
    target.mkdir(parents=True, exist_ok=True)
    return target


def main() -> None:
    event = read_event()
    session_id = event.get("session_id") or event.get("session")
    if not session_id:
        sys.exit(0)

    audit_dir = resolve_audit_dir()
    if not audit_dir:
        sys.exit(0)

    tools: list[str] = []
    components: set[str] = set()
    failures = 0
    timestamps: list[str] = []

    try:
        for path in sorted(audit_dir.glob("*.jsonl")):
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("session") != session_id:
                    continue
                if entry.get("tool"):
                    tools.append(entry["tool"])
                for comp in entry.get("components", []) or []:
                    components.add(comp)
                if entry.get("ok") is False:
                    failures += 1
                if entry.get("ts"):
                    timestamps.append(entry["ts"])
    except OSError:
        sys.exit(0)

    if not tools:
        sys.exit(0)  # nothing happened this session that the trail recorded

    digest = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "session": session_id,
        "tool_calls": len(tools),
        "distinct_tools": sorted(set(tools)),
        "components": sorted(components),
        "failures": failures,
        "span": [min(timestamps), max(timestamps)] if timestamps else None,
    }

    try:
        with (digest_dir() / "session-digests.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(digest) + "\n")
    except OSError:
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
