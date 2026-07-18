#!/usr/bin/env python3
"""Proposal engine: turn mined signals and eval gaps into ranked capability proposals.

Fuses the experience miner's signals (ADR-0009) with the eval scorecard's regressions (ADR-0008)
into concrete, evidence-backed proposals a `skill-author` agent can implement — and that governance
will require an ADR and an atomic commit to adopt (ADR-0010). This engine proposes; it never
implements and never commits.

Priority order, because it reflects urgency:
  1. regression — an eval dropped below baseline: active harm, fix first
  2. failure    — a recurring failure mode: friction the fleet hits repeatedly
  3. workflow   — a recurring sequence: a capability gap worth encapsulating
  4. co-edit    — components always changed together: a coupling worth capturing

Each proposal is a pointer with evidence, not an implementation: the audit trail records that a
component was edited, not the edit (ADR-0009), so the proposal names the gap and the evidence and
leaves the design to the agent that reads the actual code.

Usage:
    propose.py                       # run mine + evals, emit ranked proposals
    propose.py --json                # machine-readable, for the evolution-strategist agent
    propose.py --signals FILE        # use a precomputed mine.py --json output
    propose.py --scorecard FILE      # use a precomputed evalctl.py --json output
    propose.py --top N               # cap the number of proposals (default 10)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

SLUG = re.compile(r"[^a-z0-9]+")

PLUGIN_HINTS = {
    "skill/vault": "memory-obsidian", "skill/recall": "memory-obsidian",
    "manifest/memory": "memory-obsidian",
    "hook/": "governance-gates", "skill/governance": "governance-gates",
    "skill/commit": "core-orchestration", "skill/adr": "core-orchestration",
    "skill/release": "core-orchestration", "skill/skill-authoring": "core-orchestration",
    "agent/": "core-orchestration",
}


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("propose: not inside a marketplace", file=sys.stderr)
    sys.exit(2)


def plugin_root() -> Path:
    import os
    return Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[1]))


def slugify(text: str, limit: int = 48) -> str:
    return SLUG.sub("-", text.lower()).strip("-")[:limit] or "proposal"


def guess_plugin(component: str) -> str:
    for prefix, plugin in PLUGIN_HINTS.items():
        if component.startswith(prefix):
            return plugin
    return "core-orchestration"


def run_json(script: Path, *args: str) -> dict | None:
    try:
        result = subprocess.run([sys.executable, str(script), "--json", *args],
                                capture_output=True, text=True, timeout=120)
        if result.returncode not in (0, 1):  # evalctl exits 1 on regression, still valid output
            return None
        return json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def gather(root: Path, signals_file: str | None, scorecard_file: str | None) -> tuple[dict, dict]:
    if signals_file:
        signals = json.loads(Path(signals_file).read_text(encoding="utf-8"))
    else:
        signals = run_json(plugin_root() / "scripts" / "mine.py") or {"signals": {}, "meta": {}}

    if scorecard_file:
        scorecard = json.loads(Path(scorecard_file).read_text(encoding="utf-8"))
    else:
        scorecard = run_json(plugin_root() / "scripts" / "evalctl.py", "--no-ledger") or {}
    return signals, scorecard


def proposals_from_regressions(scorecard: dict) -> list[dict]:
    out = []
    for reg in scorecard.get("regressions", []):
        cap = next((r["capability"] for r in scorecard.get("results", []) if r["id"] == reg["id"]), "?")
        out.append({
            "id": f"fix-regression-{slugify(reg['id'])}",
            "kind": "fix",
            "priority": 100 + int((reg["was"] - reg["now"]) * 100),
            "title": f"Restore the '{reg['id']}' capability ({cap})",
            "rationale": f"Eval '{reg['id']}' regressed {reg['was']:.2f} → {reg['now']:.2f} against "
                         f"baseline — an active degradation. Bisect the commits since the baseline, "
                         f"identify the change that dropped it, and either fix forward or revert "
                         f"(release.py --pin).",
            "target_plugin": None,
            "draft": f"Run `evalctl.py --eval {reg['id']}` to see the failing detail, then "
                     f"`git log` the capability's files since the baseline SHA to find the culprit.",
            "requires_adr": True,
            "evidence": reg,
        })
    return out


def proposals_from_failures(signals: dict) -> list[dict]:
    out = []
    for sig in signals.get("signals", {}).get("failures", []):
        target = sig["target"]
        out.append({
            "id": f"handle-failure-{slugify(target)}",
            "kind": "guard",
            "priority": 60 + min(sig["occurrences"], 20),
            "title": f"Handle the recurring failure: {sig['tool']} — {target}",
            "rationale": f"'{target}' failed {sig['occurrences']}× across {sig['sessions']} "
                         f"session(s). A failure the fleet hits repeatedly is friction worth "
                         f"removing — a preflight check, a clearer error, or a guard.",
            "target_plugin": "governance-gates" if "cliff" not in target else "core-orchestration",
            "draft": f"Consider a preflight or a skill that detects this condition before the "
                     f"failing call, or degrades gracefully with an actionable message.",
            "requires_adr": True,
            "evidence": sig,
        })
    return out


def proposals_from_workflows(signals: dict) -> list[dict]:
    out = []
    for sig in signals.get("signals", {}).get("workflows", []):
        seq = " → ".join(sig["pattern"])
        out.append({
            "id": f"encapsulate-{slugify('-'.join(sig['pattern']))}",
            "kind": "command",
            "priority": 30 + sig["sessions"] + len(sig["pattern"]),
            "title": f"Encapsulate the recurring sequence: {seq}",
            "rationale": f"The sequence {seq} recurred in {sig['sessions']} session(s) "
                         f"({sig['occurrences']}×). A sequence run this often by hand is a "
                         f"capability the fleet is missing — a command or skill that performs it "
                         f"in one step.",
            "target_plugin": None,
            "draft": f"Read the sessions that ran this sequence (via the audit trail) to design a "
                     f"command that captures the common case. Signals are pointers — the trail "
                     f"records the tools, not the edits, so the design comes from the code.",
            "requires_adr": True,
            "evidence": sig,
        })
    return out


def proposals_from_coedits(signals: dict) -> list[dict]:
    out = []
    for sig in signals.get("signals", {}).get("co_edits", []):
        a, b = sig["components"]
        out.append({
            "id": f"couple-{slugify(a)}-{slugify(b)}",
            "kind": "adr",
            "priority": 15 + sig["sessions"],
            "title": f"Capture the coupling: {a} + {b}",
            "rationale": f"{a} and {b} were edited together in {sig['sessions']} session(s). "
                         f"Components that always change together are coupled — either a compound "
                         f"capability spanning both, or a coupling worth documenting so the next "
                         f"editor knows to change both.",
            "target_plugin": guess_plugin(a),
            "draft": f"If the coupling is essential, a decision record capturing it prevents a "
                     f"future half-change. If it is accidental, the two may want decoupling.",
            "requires_adr": True,
            "evidence": sig,
        })
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ranked capability proposals.")
    parser.add_argument("--signals", help="precomputed mine.py --json output")
    parser.add_argument("--scorecard", help="precomputed evalctl.py --json output")
    parser.add_argument("--top", type=int, default=10, help="cap the number of proposals")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root()
    signals, scorecard = gather(root, args.signals, args.scorecard)

    proposals = (
        proposals_from_regressions(scorecard)
        + proposals_from_failures(signals)
        + proposals_from_workflows(signals)
        + proposals_from_coedits(signals)
    )
    proposals.sort(key=lambda p: p["priority"], reverse=True)
    proposals = proposals[:args.top]

    meta = {
        "sessions_analysed": signals.get("meta", {}).get("sessions_analysed", 0),
        "eval_aggregate": scorecard.get("aggregate"),
        "regressions": len(scorecard.get("regressions", [])),
        "proposal_count": len(proposals),
    }

    if args.as_json:
        print(json.dumps({"meta": meta, "proposals": proposals}, indent=2))
        return 0

    if not proposals:
        print("\nno proposals. Either the eval suite is at baseline and the audit trail shows no "
              "recurring pattern, or usage is still too light to mine (ADR-0009). Nothing to do — "
              "which, for a self-improving system, is a valid state.")
        return 0

    print(f"\n{len(proposals)} proposal(s), ranked by priority "
          f"(regressions first, then failures, workflows, couplings):\n")
    for i, p in enumerate(proposals, start=1):
        tag = {"fix": "FIX", "guard": "GUARD", "command": "CMD", "skill": "SKILL",
               "adr": "ADR", "investigation": "INVESTIGATE"}.get(p["kind"], p["kind"].upper())
        where = f"  →  {p['target_plugin']}" if p["target_plugin"] else ""
        print(f"{i}. [{tag}] {p['title']}{where}")
        print(f"   {p['rationale']}")
        print(f"   next: {p['draft']}")
        print(f"   (adoption requires an ADR and an atomic commit — this is a proposal, not a change)\n")

    print("Hand a proposal to the skill-author agent to implement, then run evalctl.py to confirm "
          "no regression before adoption (ADR-0008, ADR-0010).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
