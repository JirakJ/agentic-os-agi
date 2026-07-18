#!/usr/bin/env python3
"""gate-protection: deny edits to gate/hook/baseline files unless /gate-unlock is active.

Defeats prompt injection that tries to weaken the gates by editing hooks.json,
allowlist.json, gates.json, plugin manifests, lefthook.yml or scanner baselines.
Always enforcing. Fails CLOSED on internal error.
"""
import sys

from lib import allowlists, cc, telem

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        cc.allow()
    ti = data.get("tool_input", {}) or {}
    path = str(ti.get("file_path") or ti.get("path") or "")
    if not path:
        cc.allow()
    if not allowlists.path_matches(path, "protected_gate_files"):
        cc.allow()
    if cc.unlock_active():
        telem.emit("gate_override", data.get("session_id", ""), hook="gate-protection", path=path)
        cc.allow()
    telem.emit("gate_fired", data.get("session_id", ""), hook="gate-protection",
               decision="deny", path=path)
    cc.deny(
        f"gate-protection: '{path}' is a protected guardrail file. Editing gate "
        "configuration requires explicit human approval: ask the user to run /gate-unlock "
        "(valid 10 minutes), then retry. Changes to gates also require an ADR "
        "(docs/adr/) per the governance policy."
    )

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # fail CLOSED
        cc.deny(f"gate-protection internal error (fail-closed): {e}")
