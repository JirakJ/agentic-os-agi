#!/usr/bin/env python3
"""context-bridge (SubagentStop): surface subagent-produced repo changes so the parent
regains awareness. Stop-family hooks discard hookSpecificOutput, so we use systemMessage
(user-visible) + telemetry, and never block here."""
from lib import cc, gitutil, telem

def main() -> None:
    data = cc.read_input()
    changes = gitutil.status_porcelain(data.get("cwd")).strip()
    if not changes:
        cc.allow()
    telem.emit("subagent_changes", data.get("session_id", ""),
               files=[l.split()[-1] for l in changes.splitlines()[:20]])
    cc.system_message("context-bridge: subagent left these repo changes:\n" + changes[:2000])

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
