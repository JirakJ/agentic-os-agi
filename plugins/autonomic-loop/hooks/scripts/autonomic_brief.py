#!/usr/bin/env python3
"""SessionStart: inject the system's state so the session starts knowing, not asking.

Composes what the loop already computed — never runs anything expensive at startup:

  standing regression   the last verification found the fleet measurably worse; that outranks
                        whatever the session came to do, and the brief says so with the fix path
  verified state        one line of ground truth: aggregate, eval count, sha
  pending proposals     what the session-end pulse staged; offered once, then cleared

Instructions ride along explicitly — hooks cannot invoke a skill, but they can name the one to
apply, which is the strongest guarantee the primitives offer (ADR-0014). Missions are deliberately
absent here: long-horizon's own brief owns them, and two hooks injecting the same missions would
double-spend context. Silent when there is nothing to say.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _state import (autonomic_off, project_root, read_event,  # noqa: E402
                    read_json, state_dir)


def main() -> None:
    if autonomic_off():
        sys.exit(0)
    event = read_event()
    if project_root(event) is None:
        sys.exit(0)

    sections: list[str] = []

    verify = read_json(state_dir() / "last-verify.json")
    if verify:
        regressions = verify.get("regressions", [])
        if regressions:
            lines = "; ".join(f"{r['id']} {r['was']:.2f}→{r['now']:.2f}" for r in regressions)
            sections.append(
                f"STANDING REGRESSION (from the last verification, {verify.get('ts', '?')}): "
                f"{lines}. The fleet is measurably worse than baseline and this outranks other "
                f"work (ADR-0008). Fix forward or revert (release.py --pin), re-run "
                f"plugins/self-evolution/scripts/evalctl.py to confirm green. Apply the "
                f"self-reflection and evaluation-authoring skills as needed."
            )
        else:
            sections.append(
                f"verified state: {verify.get('evals', '?')} evals at aggregate "
                f"{verify.get('aggregate', '?')} (sha {verify.get('sha', '?')}, "
                f"{verify.get('ts', '?')}) — no standing regression."
            )

    stage_path = state_dir() / "pending-proposals.json"
    stage = read_json(stage_path)
    if stage and stage.get("proposals"):
        lines = "\n".join(f"  - [{p['kind']}] {p['title']} — {p['rationale']}"
                          for p in stage["proposals"])
        sections.append(
            "pending capability proposals (mined from recent experience at session end):\n"
            f"{lines}\n"
            "These are proposals, not authorised work: shape with the capability-proposal skill, "
            "implement via the skill-author agent, verify with the eval suite, adopt through an "
            "ADR and an atomic commit (ADR-0010). Decline freely — most proposals should be "
            "declined. Full agenda: /frontier."
        )
        try:
            stage_path.unlink()  # offered once; the frontier re-derives on demand
        except OSError:
            pass

    if not sections:
        sys.exit(0)  # nothing to say — silence is the correct brief

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "autonomic loop:\n" + "\n\n".join(sections),
        }
    }))
    sys.exit(0)


if __name__ == "__main__":
    main()
