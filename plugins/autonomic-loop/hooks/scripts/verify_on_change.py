#!/usr/bin/env python3
"""Stop: a core-dirty session runs the eval suite before it is allowed to finish.

The structural half of ADR-0008, made self-triggering (ADR-0014): verification no longer depends
on anyone remembering /evals. If this session edited core logic, the capability suite runs here.

  green      → the dirty marker clears, the verified state is recorded, the stop proceeds silently
  regression → the stop is BLOCKED with the failing capabilities and the fix path; a turn does not
               get to end with the fleet measurably worse and nobody told
  broken     → a suite that cannot run after a core change is itself a finding — blocked too

Loop protection mirrors the commit gate: `stop_hook_active` means we already blocked once this
turn; blocking again would spin, so the second attempt passes and the standing state is left for
the session-start brief to surface. Clean sessions never pay: no dirty marker, no run, no output.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _state import (autonomic_off, dirty_path, now, project_root,  # noqa: E402
                    read_event, read_json, state_dir, write_json)

SUITE_TIMEOUT = 240


def stop_block(reason: str) -> None:
    json.dump({"decision": "block", "reason": reason}, sys.stdout)
    sys.exit(0)


def evalctl(root: Path) -> Path | None:
    candidate = root / "plugins" / "self-evolution" / "scripts" / "evalctl.py"
    return candidate if candidate.is_file() else None


def run_suite(root: Path, tool: Path) -> tuple[int, dict | None, str]:
    env = {**os.environ}
    # This hook runs with CLAUDE_PLUGIN_ROOT pointing at autonomic-loop; the harness needs its
    # own root for baseline resolution — a hard override, not a default (found by live test).
    env["CLAUDE_PLUGIN_ROOT"] = str(root / "plugins" / "self-evolution")
    try:
        result = subprocess.run(
            [sys.executable, str(tool), "--json", "--no-ledger", "--root", str(root)],
            capture_output=True, text=True, timeout=SUITE_TIMEOUT, env=env, cwd=root,
        )
    except subprocess.TimeoutExpired:
        return 3, None, "the eval suite timed out"
    except (OSError, subprocess.SubprocessError) as exc:
        return 3, None, f"the eval suite failed to launch: {exc}"
    card = None
    if result.stdout.strip():
        try:
            card = json.loads(result.stdout)
        except json.JSONDecodeError:
            card = None
    return result.returncode, card, (result.stderr or "").strip()


def record_verify(card: dict) -> None:
    write_json(state_dir() / "last-verify.json", {
        "ts": now(),
        "sha": card.get("sha"),
        "aggregate": card.get("aggregate"),
        "regressions": card.get("regressions", []),
        "evals": len(card.get("results", [])),
    })


def main() -> None:
    if autonomic_off():
        sys.exit(0)
    event = read_event()
    session_id = event.get("session_id") or event.get("session") or ""
    if not session_id:
        sys.exit(0)

    marker = dirty_path(session_id)
    if not marker.is_file():
        sys.exit(0)  # clean session — no verification owed, no cost paid

    if event.get("stop_hook_active"):
        sys.exit(0)  # already blocked once this turn; spinning helps nobody (ADR-0014)

    root = project_root(event)
    if root is None:
        sys.exit(0)
    tool = evalctl(root)
    if tool is None:
        sys.exit(0)  # capability layer absent — the policy layer degrades to silence

    dirty = read_json(marker) or {}
    touched = ", ".join(dirty.get("paths", [])[:6]) or "core paths"

    code, card, stderr = run_suite(root, tool)

    if card is None or code in (2, 3):
        detail = stderr.splitlines()[-1] if stderr else "no output"
        stop_block(
            f"This session changed core logic ({touched}) and the capability eval suite cannot "
            f"run: {detail}. A suite broken by a core change is itself a regression (ADR-0008). "
            f"Fix the suite (python3 plugins/self-evolution/scripts/evalctl.py), or revert the "
            f"change, before finishing."
        )

    record_verify(card)
    regressions = card.get("regressions", [])
    failing = [r for r in card.get("results", []) if not r.get("pass")]
    # A failing eval blocks even with no baseline to regress against: a core change that
    # breaks a capability is bad regardless of bookkeeping.
    if code == 1 or regressions or failing:
        lines = "; ".join(f"{r['id']} {r['was']:.2f}→{r['now']:.2f}" for r in regressions) \
            or "no baseline delta — but the suite has failures"
        failing_detail = "; ".join(f"{r['id']}: {r.get('detail') or 'failed'}" for r in failing[:3])
        stop_block(
            f"This session changed core logic ({touched}) and the capability suite now shows "
            f"regression against baseline: {lines}. "
            + (f"Failing detail: {failing_detail}. " if failing_detail else "")
            + "A turn does not end with the fleet measurably worse (ADR-0008, ADR-0014). Fix "
              "forward, or revert the offending change (release.py --pin), then re-run "
              "evalctl to confirm green. If the drop is intended, re-baseline deliberately "
              "(evalctl --set-baseline) and say so in the commit."
        )

    # green: the change is verified — clear the debt and finish quietly
    try:
        marker.unlink()
    except OSError:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
