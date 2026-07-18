#!/usr/bin/env python3
"""no-placeholder: production-ready only. Deny TODO/FIXME/stub/mock/placeholder content in
non-exempt source files. Inline escape: a line containing `jj-allow-placeholder`.
Mode-gated (dry-run by default until measured FP < 2%)."""
import re
import sys

from lib import allowlists, cc, gates, telem

GATE = "no-placeholder"

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        cc.allow()
    if not gates.active(GATE):
        cc.allow()
    ti = data.get("tool_input", {}) or {}
    path = str(ti.get("file_path") or "")
    content = str(ti.get("content") or ti.get("new_string") or "")
    if not content or allowlists.path_matches(path, "placeholder_exempt_paths"):
        cc.allow()
    if "jj-allow-placeholder" in content:
        cc.allow()
    hits = allowlists.regex_hits(content, "placeholder_patterns")
    if not hits:
        cc.allow()
    sid = data.get("session_id", "")
    telem.emit("gate_fired", sid, hook=GATE,
               decision="deny" if gates.enforcing(GATE) else "advisory",
               path=path, patterns=hits[:5])
    msg = (f"placeholder content in '{path}' (matched: {', '.join(hits[:3])}). "
           "Ship the real implementation - no TODOs, stubs, mocks, or lorem ipsum. "
           "If this specific occurrence is legitimate, add a line containing "
           "`jj-allow-placeholder` next to it.")
    if gates.enforcing(GATE):
        cc.deny("no-placeholder: " + msg)
    cc.system_message("[dry-run] no-placeholder would block: " + msg)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()  # fail open (quality gate, not safety-critical)
