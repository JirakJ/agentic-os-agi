#!/usr/bin/env python3
"""Inspect the autonomic loop: what state the layer holds and what fires when.

The loop's four reflexes (ADR-0014) and the state each one reads or writes:

  PostToolUse  change_sentinel   writes  state/dirty-<session>.json  (core edits mark debt)
  Stop         verify_on_change  reads dirty, runs the suite, blocks on regression,
                                 writes  state/last-verify.json
  SessionEnd   evolution_pulse   writes  state/pending-proposals.json (mined, staged once)
  SessionStart autonomic_brief   reads last-verify + pending, injects, consumes the stage

Usage:
    autonomic.py            # human-readable status
    autonomic.py --json     # machine-readable

Kill switch: AGENTIC_OS_AUTONOMIC=off silences every reflex without uninstalling anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hooks" / "scripts"))
from _state import autonomic_off, read_json, state_dir  # noqa: E402


def collect() -> dict:
    base = state_dir()
    dirty = []
    for marker in sorted(base.glob("dirty-*.json")):
        payload = read_json(marker) or {}
        dirty.append({
            "session": payload.get("session", marker.stem.replace("dirty-", "")),
            "paths": payload.get("paths", []),
            "since": payload.get("first"),
        })
    return {
        "enabled": not autonomic_off(),
        "state_dir": str(base),
        "dirty_sessions": dirty,
        "last_verify": read_json(base / "last-verify.json"),
        "pending_proposals": read_json(base / "pending-proposals.json"),
    }


def render(status: dict) -> None:
    print(f"\nautonomic loop — {'ENABLED' if status['enabled'] else 'OFF (AGENTIC_OS_AUTONOMIC)'}")
    print(f"state: {status['state_dir']}\n")

    verify = status["last_verify"]
    if verify:
        regressions = verify.get("regressions", [])
        mark = f"{len(regressions)} STANDING REGRESSION(S)" if regressions else "no standing regression"
        print(f"last verification: {verify.get('evals', '?')} evals, aggregate "
              f"{verify.get('aggregate', '?')} @ {verify.get('sha', '?')} ({verify.get('ts', '?')}) — {mark}")
        for reg in regressions:
            print(f"    {reg['id']}: {reg['was']:.2f} → {reg['now']:.2f}")
    else:
        print("last verification: none yet — the Stop reflex runs it after the first core change")

    if status["dirty_sessions"]:
        print("\nunverified core debt (sessions that changed core logic, not yet verified green):")
        for entry in status["dirty_sessions"]:
            paths = ", ".join(entry["paths"][:4]) + ("…" if len(entry["paths"]) > 4 else "")
            print(f"    {entry['session']}: {paths}  (since {entry['since']})")
    else:
        print("\nno unverified core debt.")

    pending = status["pending_proposals"]
    if pending and pending.get("proposals"):
        print(f"\nstaged proposals (offered at the next session start, then cleared):")
        for p in pending["proposals"]:
            print(f"    [{p['kind']}] {p['title']}")
    else:
        print("\nno staged proposals.")

    print("\nreflexes: PostToolUse→sentinel · Stop→verify (blocks on regression) · "
          "SessionEnd→pulse · SessionStart→brief   kill switch: AGENTIC_OS_AUTONOMIC=off")


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect the autonomic loop's state.")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    status = collect()
    if args.as_json:
        print(json.dumps(status, indent=2))
    else:
        render(status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
