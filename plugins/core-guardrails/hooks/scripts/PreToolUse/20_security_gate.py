#!/usr/bin/env python3
"""security-gate: deny secret-path access and destructive shell commands.

Always enforcing; fails CLOSED. Covers Read/Edit/Write on secret paths, destructive Bash
patterns, cross-boundary writes (Employer/client-confidential folders), and cat/grep of secret
files inside Bash commands.
"""
import re
import sys

from lib import allowlists, cc, telem

_SECRET_IN_BASH = re.compile(
    r"(cat|less|more|head|tail|grep|cp|scp|base64)\s+[^|;&]*"
    r"(\.env\b|\.pem\b|id_rsa|id_ed25519|\.aws/credentials|\.netrc|settings\.local\.json)",
    re.IGNORECASE,
)

def main() -> None:
    data = cc.read_input()
    tool = data.get("tool_name", "")
    ti = data.get("tool_input", {}) or {}
    sid = data.get("session_id", "")

    if tool in ("Read", "Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = str(ti.get("file_path") or ti.get("path") or "")
        if path and allowlists.path_matches(path, "secret_paths"):
            telem.emit("gate_fired", sid, hook="security-gate", decision="deny",
                       kind="secret_path", path=path)
            cc.deny(f"security-gate: access to secret file '{path}' is denied. "
                    "Secrets are read via the OS keychain or environment, never by the agent.")
        if path and allowlists.path_matches(path, "confidential_boundary_deny") and tool != "Read":
            telem.emit("gate_fired", sid, hook="security-gate", decision="deny",
                       kind="boundary", path=path)
            cc.deny(f"security-gate: writing into a confidential boundary folder "
                    f"('{path}') is denied. Day-job / client-confidential content must stay "
                    "in its dedicated vault and remote.")
        cc.allow()

    if tool == "Bash":
        cmd = str(ti.get("command", ""))
        hits = allowlists.regex_hits(cmd, "destructive_bash")
        if hits:
            telem.emit("gate_fired", sid, hook="security-gate", decision="deny",
                       kind="destructive_bash", patterns=hits)
            cc.deny("security-gate: destructive command denied "
                    f"(matched: {', '.join(hits[:3])}). If this is genuinely intended, the "
                    "human must run it manually or /gate-unlock first.")
        if _SECRET_IN_BASH.search(cmd) and not cc.unlock_active():
            telem.emit("gate_fired", sid, hook="security-gate", decision="deny",
                       kind="secret_via_bash")
            cc.deny("security-gate: shell access to secret material denied. "
                    "Use keychain/env indirection; /gate-unlock for a human-approved exception.")
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # fail CLOSED
        cc.deny(f"security-gate internal error (fail-closed): {e}")
