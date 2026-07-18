#!/usr/bin/env python3
"""skill-usage-logger: observe-only telemetry of Skill/Task usage (feeds skill-forge
pruning decisions and the context-budget guard)."""
from lib import cc, telem

def main() -> None:
    data = cc.read_input()
    tool = data.get("tool_name", "")
    if tool not in ("Skill", "Task"):
        cc.allow()
    ti = data.get("tool_input", {}) or {}
    name = str(ti.get("skill") or ti.get("name") or ti.get("subagent_type") or "unknown")
    telem.emit("skill_used", data.get("session_id", ""), tool=tool, name=name)
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
