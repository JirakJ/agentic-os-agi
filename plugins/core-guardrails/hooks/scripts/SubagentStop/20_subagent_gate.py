#!/usr/bin/env python3
"""subagent-gate (SubagentStop): enforce non-negotiables before a subagent's result folds
back - no secret files touched, no protected gate files modified. decision=block forces
the subagent to fix its output. Mode-gated."""
import json

from lib import allowlists, cc, gates, gitutil, telem

GATE = "subagent-gate"

def main() -> None:
    data = cc.read_input()
    if not gates.active(GATE):
        cc.allow()
    changes = gitutil.status_porcelain(data.get("cwd")).strip()
    if not changes:
        cc.allow()
    bad: list[str] = []
    for line in changes.splitlines():
        path = line[3:].strip().strip('"')
        if allowlists.path_matches(path, "secret_paths") or \
           allowlists.path_matches(path, "protected_gate_files"):
            bad.append(path)
    if not bad:
        cc.allow()
    sid = data.get("session_id", "")
    telem.emit("gate_fired", sid, hook=GATE,
               decision="block" if gates.enforcing(GATE) else "advisory", paths=bad[:10])
    msg = ("subagent-gate: the subagent modified protected or secret paths: "
           + ", ".join(bad[:6]) + ". Revert those changes before finishing.")
    if gates.enforcing(GATE) and not cc.unlock_active():
        print(json.dumps({"decision": "block", "reason": msg[:9000]}))
        raise SystemExit(0)
    cc.system_message("[dry-run] " + msg)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
