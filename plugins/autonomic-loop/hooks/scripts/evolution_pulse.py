#!/usr/bin/env python3
"""SessionEnd: mine the session's experience and stage ranked proposals for the next brief.

The expensive sensing happens after the human has left (ADR-0014): the miner reads the audit trail,
the proposal engine fuses it with the last verified eval state, and the top proposals land in a
staging file the session-start brief injects. Consumption clears the stage — a proposal is offered
once, not nagged forever.

Reuses the last-verify scorecard when one exists so the pulse does not re-run the eval suite; a
session that changed core logic already paid for its run at Stop. Non-blocking and silent
throughout: a failed pulse is a thinner next brief, never a broken session end.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _state import (autonomic_off, now, project_root, read_event,  # noqa: E402
                    read_json, state_dir, write_json)

STAGE_LIMIT = 3
PULSE_TIMEOUT = 120


def main() -> None:
    if autonomic_off():
        sys.exit(0)
    event = read_event()
    root = project_root(event)
    if root is None:
        sys.exit(0)

    propose = root / "plugins" / "self-evolution" / "scripts" / "propose.py"
    mine = root / "plugins" / "self-evolution" / "scripts" / "mine.py"
    if not propose.is_file() or not mine.is_file():
        sys.exit(0)

    env = {**os.environ}
    env["CLAUDE_PLUGIN_ROOT"] = str(root / "plugins" / "self-evolution")  # hard override; hooks run with their own plugin root

    try:
        mined = subprocess.run([sys.executable, str(mine), "--json", "--root", str(root)],
                               capture_output=True, text=True, timeout=PULSE_TIMEOUT, env=env)
        if mined.returncode != 0 or not mined.stdout.strip():
            sys.exit(0)

        with tempfile.TemporaryDirectory() as raw:
            tmp = Path(raw)
            signals_file = tmp / "signals.json"
            signals_file.write_text(mined.stdout, encoding="utf-8")

            args = [sys.executable, str(propose), "--signals", str(signals_file),
                    "--json", "--root", str(root), "--top", str(STAGE_LIMIT)]
            last_verify = read_json(state_dir() / "last-verify.json")
            if last_verify is not None:
                # reuse the verified state instead of re-running the suite at session end
                scorecard_file = tmp / "scorecard.json"
                scorecard_file.write_text(json.dumps({
                    "aggregate": last_verify.get("aggregate"),
                    "regressions": last_verify.get("regressions", []),
                    "results": [],
                }), encoding="utf-8")
                args += ["--scorecard", str(scorecard_file)]

            proposed = subprocess.run(args, capture_output=True, text=True,
                                      timeout=PULSE_TIMEOUT, env=env)
    except (OSError, subprocess.SubprocessError):
        sys.exit(0)

    stage = state_dir() / "pending-proposals.json"
    proposals = []
    if proposed.returncode == 0 and proposed.stdout.strip():
        try:
            proposals = json.loads(proposed.stdout).get("proposals", [])[:STAGE_LIMIT]
        except json.JSONDecodeError:
            proposals = []

    if proposals:
        write_json(stage, {"staged": now(), "proposals": [
            {"id": p["id"], "kind": p["kind"], "title": p["title"],
             "rationale": p["rationale"]} for p in proposals]})
    else:
        try:
            stage.unlink()  # nothing worth proposing — an empty stage, not a stale one
        except OSError:
            pass
    sys.exit(0)


if __name__ == "__main__":
    main()
