#!/usr/bin/env python3
"""i18n-complete: when a locale JSON is edited, verify key parity across sibling locales.
Advisory (systemMessage) in dryrun; decision=block in enforce."""
import json
import pathlib
import sys

from lib import allowlists, cc, gates, telem

GATE = "i18n-complete"

def _flat(d: dict, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    for k, v in d.items():
        kk = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            keys |= _flat(v, kk)
        else:
            keys.add(kk)
    return keys

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit") or not gates.active(GATE):
        cc.allow()
    path = str((data.get("tool_input") or {}).get("file_path") or "")
    if not path or not allowlists.path_matches(path, "i18n_paths"):
        cc.allow()
    p = pathlib.Path(path)
    if not p.exists():
        cc.allow()
    try:
        mine = _flat(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        cc.allow()
    missing: dict[str, list[str]] = {}
    for sib in sorted(p.parent.glob("*.json")):
        if sib == p:
            continue
        try:
            theirs = _flat(json.loads(sib.read_text(encoding="utf-8")))
        except Exception:
            continue
        gap = sorted(mine - theirs)
        if gap:
            missing[sib.name] = gap[:10]
    if not missing:
        cc.allow()
    sid = data.get("session_id", "")
    telem.emit("gate_fired", sid, hook=GATE,
               decision="block" if gates.enforcing(GATE) else "advisory", missing=list(missing))
    msg = "i18n-complete: locale key parity broken - " + "; ".join(
        f"{f} missing {', '.join(k)}" for f, k in list(missing.items())[:4])
    if gates.enforcing(GATE):
        cc.post_block(msg + ". Add the keys to every locale before continuing.")
    cc.system_message(msg)

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
