"""Merge multiple sub-hook outputs into one hook response.

Reads NUL-separated chunks on stdin. Env HOOK_EVENT selects the merge strategy:
SessionStart/UserPromptSubmit outputs are plain text -> concatenated; everything else is
JSON -> systemMessage strings joined, first hookSpecificOutput wins (denies short-circuit
in the dispatcher before reaching this point).
"""
from __future__ import annotations

import json
import os
import sys

def main() -> None:
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    chunks = [c.strip() for c in raw.split("\x00") if c.strip()]
    if not chunks:
        return
    event = os.environ.get("HOOK_EVENT", "")
    if event in ("SessionStart", "UserPromptSubmit"):
        print("\n\n".join(chunks))
        return
    msgs: list[str] = []
    hso = None
    decision = None
    reason_parts: list[str] = []
    for c in chunks:
        try:
            obj = json.loads(c)
        except Exception:
            msgs.append(c)
            continue
        if "systemMessage" in obj:
            msgs.append(str(obj["systemMessage"]))
        if hso is None and "hookSpecificOutput" in obj:
            hso = obj["hookSpecificOutput"]
        if obj.get("decision") == "block":
            decision = "block"
            if obj.get("reason"):
                reason_parts.append(str(obj["reason"]))
    out: dict = {}
    if decision:
        out["decision"] = "block"
        out["reason"] = "\n".join(reason_parts)[:9500]
    if hso:
        out["hookSpecificOutput"] = hso
    if msgs:
        out["systemMessage"] = "\n".join(msgs)[:9500]
    if out:
        print(json.dumps(out))

if __name__ == "__main__":
    main()
