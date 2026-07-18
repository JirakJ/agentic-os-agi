#!/usr/bin/env python3
"""ship-gate: lockstep releases. On git commit/push inside a repo that carries a plugin
marketplace, verify plugin.json versions == marketplace.json entries == VERSION, and the
CHANGELOG mentions the current version. Mode-gated (dry-run by default)."""
import json
import pathlib
import re
import sys

from lib import cc, gates, gitutil, telem

GATE = "ship-gate"

def _drift(root: pathlib.Path) -> list[str]:
    problems: list[str] = []
    mp = root / ".claude-plugin" / "marketplace.json"
    if not mp.exists():
        return problems
    try:
        market = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as e:
        return [f"marketplace.json unreadable: {e}"]
    version_file = root / "VERSION"
    dist_version = version_file.read_text().strip() if version_file.exists() else None
    entries = {p.get("name"): p.get("version") for p in market.get("plugins", [])}
    for name, mv in entries.items():
        pj = root / "plugins" / str(name) / ".claude-plugin" / "plugin.json"
        if not pj.exists():
            problems.append(f"{name}: plugin.json missing")
            continue
        try:
            pv = json.loads(pj.read_text(encoding="utf-8")).get("version")
        except Exception as e:
            problems.append(f"{name}: plugin.json unreadable: {e}")
            continue
        if pv != mv:
            problems.append(f"{name}: plugin.json {pv} != marketplace {mv}")
        if dist_version and pv != dist_version:
            problems.append(f"{name}: plugin.json {pv} != VERSION {dist_version}")
    if dist_version:
        ch = root / "CHANGELOG.md"
        if ch.exists() and f"[{dist_version}]" not in ch.read_text(encoding="utf-8"):
            problems.append(f"CHANGELOG.md has no entry for [{dist_version}]")
    return problems

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") != "Bash" or not gates.active(GATE):
        cc.allow()
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    if not re.search(r"\bgit(\s+-C\s+\S+)?\s+(commit|push)\b", cmd):
        cc.allow()
    root = gitutil.toplevel(data.get("cwd"))
    if not root:
        cc.allow()
    problems = _drift(pathlib.Path(root))
    if not problems:
        cc.allow()
    sid = data.get("session_id", "")
    telem.emit("gate_fired", sid, hook=GATE,
               decision="deny" if gates.enforcing(GATE) else "advisory", problems=problems[:5])
    msg = ("release lockstep drift: " + "; ".join(problems[:6]) +
           ". Bump plugin.json + marketplace.json + VERSION + CHANGELOG in one atomic "
           "commit (scripts/release.sh does this).")
    if gates.enforcing(GATE):
        cc.deny("ship-gate: " + msg)
    cc.system_message("[dry-run] ship-gate: " + msg)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
