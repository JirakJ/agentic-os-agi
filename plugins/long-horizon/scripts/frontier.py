#!/usr/bin/env python3
"""The learning frontier: what this system should learn next, ordered by evidence (ADR-0013).

Fuses three evidence streams into one ranked agenda:
  weakness       — capabilities scoring below threshold, and active regressions (self-model)
  blocked intent — missions stuck on a missing capability (mission state)
  coverage gap   — plugins present but unmeasured (self-model)
  friction       — recurring failures from the experience miner (audit trail)

Severity order is fixed and reflects real urgency: measured harm first, stalled committed work
second, places regressions can hide third, repeated cost fourth. The frontier owns no state — it is
a reader of its inputs, recomputable at any time, and every item carries the evidence that put it
there. Vision does not come from the frontier; a human supplies it by creating a mission, which then
surfaces here through the blocked-intent stream.

The frontier feeds the evolution loop; it does not bypass its gates. A frontier item still becomes
a proposal, an implementation, an eval run, and a governed adoption (ADR-0008, ADR-0010).

Usage:
    frontier.py                       # derive live (runs the eval suite via the self-model)
    frontier.py --model FILE          # use a precomputed selfmodel --json output
    frontier.py --missions-dir PATH   # missions location (default: <repo>/memory/missions)
    frontier.py --json                # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission as mission_mod  # noqa: E402  (same-plugin module)
import selfmodel as selfmodel_mod  # noqa: E402

WEAK_THRESHOLD = float(os.environ.get("AGENTIC_OS_WEAK_THRESHOLD", "0.8"))
PRIORITY_BONUS = {"high": 10, "normal": 5, "low": 0}


def repo_root() -> Path:
    return selfmodel_mod.repo_root()


def mined_failures(root: Path) -> list[dict]:
    miner = root / "plugins" / "self-evolution" / "scripts" / "mine.py"
    if not miner.is_file():
        return []
    try:
        result = subprocess.run([sys.executable, str(miner), "--json", "--root", str(root)],
                                capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout).get("signals", {}).get("failures", [])
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return []


def build_agenda(model: dict, missions: list, failures: list[dict]) -> list[dict]:
    agenda: list[dict] = []

    # 1 — weakness: regressions and below-threshold capabilities. Measured, active harm.
    for reg in model.get("regressions", []):
        agenda.append({
            "id": f"regression-{reg['id']}", "kind": "weakness",
            "priority": 100 + int((reg["was"] - reg["now"]) * 100),
            "title": f"Fix the regression in '{reg['id']}'",
            "evidence": f"eval {reg['id']} dropped {reg['was']:.2f} → {reg['now']:.2f} vs baseline",
            "action": "Bisect since the baseline SHA; fix forward or revert (release.py --pin). "
                      "This outranks everything: it is quantified, shipped harm.",
        })
    for cap in model.get("measured", []):
        if cap.get("weak") and not any(cap["capability"] in a["id"] for a in agenda):
            agenda.append({
                "id": f"weak-{cap['capability']}", "kind": "weakness",
                "priority": 100 + int((WEAK_THRESHOLD - cap["score"]) * 50),
                "title": f"Strengthen the weak '{cap['capability']}' capability",
                "evidence": f"capability scores {cap['score']:.2f}, below the {WEAK_THRESHOLD} "
                            f"threshold ({len(cap['evals'])} eval(s))",
                "action": "Read the failing evals' detail; the capability is measurably bad at "
                          "something it claims to do.",
            })

    # 2 — blocked intent: committed work is stalled, and the stall is attributable.
    for m in missions:
        if m.status == "blocked":
            agenda.append({
                "id": f"unblock-{m.id}", "kind": "blocked-intent",
                "priority": 80 + PRIORITY_BONUS.get(m.priority, 0),
                "title": f"Unblock mission {m.id}: {m.title}",
                "evidence": f"blocked on: {m.blocked_on} (priority {m.priority}, {m.progress} steps done)",
                "action": "Resolve the blocker or re-plan the mission around it; stalled intent "
                          "is review capacity already committed and not paying off.",
            })

    # 3 — coverage gaps: unmeasured is where regressions hide (ADR-0008).
    for cov in model.get("coverage", []):
        if not cov.get("evaluated"):
            agenda.append({
                "id": f"cover-{cov['plugin']}", "kind": "coverage-gap",
                "priority": 60 + min(cov.get("components", 0), 15),
                "title": f"Add capability evals for '{cov['plugin']}'",
                "evidence": f"{cov['components']} component(s), no eval exercises any of them",
                "action": "Author evals with deterministic verifiers (evaluation-authoring skill); "
                          "a gap in coverage is a gap in safety.",
            })
    for cap in model.get("measured", []):
        if cap.get("thin_evidence") and not cap.get("weak"):
            agenda.append({
                "id": f"thin-{cap['capability']}", "kind": "coverage-gap",
                "priority": 55,
                "title": f"Deepen the evidence for '{cap['capability']}'",
                "evidence": f"the capability rests on a single eval ({cap['evals'][0]})",
                "action": "One eval is one angle; add an eval covering a different dimension of "
                          "the capability so a partial degradation has somewhere to show.",
            })

    # 4 — friction: repeated cost, but the fleet still functions.
    for sig in failures:
        agenda.append({
            "id": f"friction-{mission_mod.re.sub(r'[^a-z0-9]+', '-', sig['target'].lower())[:40]}",
            "kind": "friction",
            "priority": 40 + min(sig.get("occurrences", 0), 15),
            "title": f"Remove the recurring failure: {sig['tool']} — {sig['target']}",
            "evidence": f"failed {sig['occurrences']}× across {sig['sessions']} session(s)",
            "action": "A preflight, a guard, or a clearer failure; the evolution loop can draft it "
                      "(/evolve).",
        })

    agenda.sort(key=lambda item: item["priority"], reverse=True)
    return agenda


def render(agenda: list[dict], model: dict) -> None:
    print(f"\nlearning frontier — derived from {model.get('source', '?')}")
    if not agenda:
        print("\n  the frontier is empty: nothing measured is weak, no mission is blocked, every "
              "plugin is evaluated, and no failure recurs. For a self-directing system that is the "
              "goal state, not a malfunction — vision enters as a new mission, not a frontier item.")
        return
    print(f"\n{len(agenda)} item(s), by evidence severity "
          "(weakness > blocked intent > coverage gap > friction):\n")
    labels = {"weakness": "WEAK", "blocked-intent": "BLOCKED", "coverage-gap": "COVER", "friction": "FRICTION"}
    for i, item in enumerate(agenda, start=1):
        print(f"{i}. [{labels[item['kind']]}] {item['title']}")
        print(f"   evidence: {item['evidence']}")
        print(f"   action:   {item['action']}\n")
    print("Every item still passes the loop's gates: proposal → implementation → eval run → "
          "governed adoption (ADR-0010). The frontier orders; it does not authorise.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive the evidence-ordered learning frontier.")
    parser.add_argument("--model", help="precomputed selfmodel --json output")
    parser.add_argument("--missions-dir", help="missions dir (default: <repo>/memory/missions)")
    parser.add_argument("--no-mine", action="store_true", help="skip the experience miner")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root()

    if args.model:
        model = json.loads(Path(args.model).read_text(encoding="utf-8"))
    else:
        scorecard = selfmodel_mod.run_scorecard(root, cached=False)
        model = selfmodel_mod.derive(root, scorecard)

    base = mission_mod.missions_dir(args.missions_dir)
    missions = mission_mod.load_all(base)
    failures = [] if args.no_mine else mined_failures(root)

    agenda = build_agenda(model, missions, failures)

    if args.as_json:
        print(json.dumps({
            "source": model.get("source"),
            "items": agenda,
            "counts": {kind: sum(1 for a in agenda if a["kind"] == kind)
                       for kind in ("weakness", "blocked-intent", "coverage-gap", "friction")},
        }, indent=2))
    else:
        render(agenda, model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
