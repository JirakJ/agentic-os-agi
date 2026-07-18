#!/usr/bin/env python3
"""The capability self-model: what this system can do, derived from evidence, never asserted.

Three distinct claims, never conflated (ADR-0012):
  measured   — capabilities with eval scores, trended against the committed baseline
  unmeasured — plugins present in the inventory that no eval exercises (coverage gaps)
  used       — what the audit trail shows actually gets exercised (engagement, not quality)

The model is a view: computed from the eval suite, the plugin inventory and the audit trail,
rebuildable at any time, never edited by hand. It cannot claim strength an eval contradicts, and it
must surface what is unmeasured as unmeasured — absence of evidence is itself signal.

Usage:
    selfmodel.py                     # run the eval suite live (the truth) and derive the model
    selfmodel.py --cached            # derive from the last ledger snapshot instead (faster, staler)
    selfmodel.py --scorecard FILE    # derive from a supplied evalctl --json output
    selfmodel.py --json              # machine-readable, for the frontier and agents
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

WEAK_THRESHOLD = 0.8
TREND_EPS = 1e-9


def repo_root(start: Path | None = None) -> Path:
    here = (start or Path.cwd()).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    fallback = Path(__file__).resolve()
    for candidate in fallback.parents:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    print("selfmodel: not inside a marketplace", file=sys.stderr)
    sys.exit(2)


def evalctl_path(root: Path) -> Path:
    return root / "plugins" / "self-evolution" / "scripts" / "evalctl.py"


def run_scorecard(root: Path, cached: bool) -> dict | None:
    """The current scorecard: a live suite run by default (the truth), or the last ledger
    snapshot with --cached (faster, and honest about being stale)."""
    if cached:
        import os
        candidates = []
        if os.environ.get("AGENTIC_OS_EVAL_LEDGER"):
            candidates.append(Path(os.environ["AGENTIC_OS_EVAL_LEDGER"]).expanduser())
        data = os.environ.get("CLAUDE_PLUGIN_DATA")
        if data:
            candidates.append(Path(data).parent / "self-evolution" / "evolution" / "ledger.jsonl")
        candidates.append(Path.home() / ".claude" / "plugins" / "data" / "self-evolution"
                          / "evolution" / "ledger.jsonl")
        for ledger in candidates:
            if ledger.is_file():
                lines = [l for l in ledger.read_text(encoding="utf-8").splitlines() if l.strip()]
                if lines:
                    snap = json.loads(lines[-1])
                    # ledger snapshots lack per-result detail; synthesise results from scores
                    snap.setdefault("results", [
                        {"id": eid, "capability": cap, "score": score, "pass": score >= 1.0}
                        for eid, score in snap.get("scores", {}).items()
                        for cap in [next((c for c, _ in snap.get("by_capability", {}).items()), "?")]
                    ])
                    snap["_source"] = f"ledger snapshot {snap.get('ts', '?')} (stale by design)"
                    return snap
        return None
    tool = evalctl_path(root)
    if not tool.is_file():
        return None
    try:
        result = subprocess.run([sys.executable, str(tool), "--json", "--no-ledger",
                                 "--root", str(root)],
                                capture_output=True, text=True, timeout=300)
        if result.returncode in (0, 1) and result.stdout.strip():
            card = json.loads(result.stdout)
            card["_source"] = "live suite run"
            return card
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        pass
    return None


def load_baseline(root: Path) -> dict:
    path = root / "plugins" / "self-evolution" / "evals" / "baseline.json"
    if path.is_file():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def inventory(root: Path) -> list[dict]:
    plugins = []
    for manifest_path in sorted((root / "plugins").glob("*/.claude-plugin/plugin.json")):
        plugin_dir = manifest_path.parents[1]
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        plugins.append({
            "name": manifest.get("name", plugin_dir.name),
            "version": manifest.get("version", "?"),
            "skills": len(list(plugin_dir.glob("skills/*/SKILL.md"))),
            "agents": len(list(plugin_dir.glob("agents/*.md"))),
            "commands": len(list(plugin_dir.glob("commands/*.md"))),
            "scripts": len(list(plugin_dir.glob("scripts/*.py"))),
            "hooks": len(list(plugin_dir.glob("hooks/scripts/*.py"))),
        })
    return plugins


def eval_coverage(root: Path, plugins: list[dict]) -> dict[str, bool]:
    """Which plugins does at least one eval exercise? Mechanical test: the plugin's name or path
    appears in an eval spec or its verifier source. Coarse, honest, and cheap to recompute."""
    corpus = ""
    for spec_path in (root / "plugins").glob("*/evals/*.json"):
        if spec_path.name == "baseline.json":
            continue
        corpus += spec_path.read_text(encoding="utf-8", errors="ignore")
        owner = spec_path.parents[1].name
        corpus += f" plugins/{owner} "  # a plugin shipping evals exercises itself
    for verifier in (root / "plugins").glob("*/evals/verifiers/*.py"):
        corpus += verifier.read_text(encoding="utf-8", errors="ignore")
    return {p["name"]: (f"plugins/{p['name']}" in corpus
                        or f"/{p['name']}/" in corpus
                        or f'"{p["name"]}"' in corpus)  # Path("plugins") / "name" style
            for p in plugins}


def usage(root: Path, top: int = 8) -> list[dict]:
    """Component call frequency from the audit trail — engagement, not quality."""
    import os
    from collections import Counter
    candidates = []
    if os.environ.get("AGENTIC_OS_AUDIT_DIR"):
        candidates.append(Path(os.environ["AGENTIC_OS_AUDIT_DIR"]).expanduser())
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if data:
        candidates.append(Path(data).parent / "governance-gates" / "audit")
    candidates.append(Path.home() / ".claude" / "plugins" / "data" / "governance-gates" / "audit")
    audit_dir = next((c for c in candidates if c.is_dir()), None)
    if not audit_dir:
        return []
    counts: Counter[str] = Counter()
    for path in audit_dir.glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            for component in entry.get("components", []) or []:
                counts[component] += 1
    return [{"component": c, "calls": n} for c, n in counts.most_common(top)]


def derive(root: Path, scorecard: dict | None) -> dict:
    baseline = load_baseline(root)
    base_scores = baseline.get("scores", {})
    plugins = inventory(root)
    covered = eval_coverage(root, plugins)

    capabilities: dict[str, dict] = {}
    for result in (scorecard or {}).get("results", []):
        cap = capabilities.setdefault(result["capability"], {"evals": [], "scores": []})
        cap["evals"].append(result["id"])
        cap["scores"].append(result["score"])

    measured = []
    for name, data in sorted(capabilities.items()):
        score = round(sum(data["scores"]) / len(data["scores"]), 4)
        base = [base_scores[e] for e in data["evals"] if e in base_scores]
        trend = "new"
        if base:
            delta = score - round(sum(base) / len(base), 4)
            trend = "up" if delta > TREND_EPS else "down" if delta < -TREND_EPS else "steady"
        measured.append({
            "capability": name, "score": score, "trend": trend,
            "evals": sorted(data["evals"]),
            "weak": score < WEAK_THRESHOLD,
            "thin_evidence": len(data["evals"]) == 1,
        })

    return {
        "source": (scorecard or {}).get("_source", "no scorecard available"),
        "sha": (scorecard or {}).get("sha"),
        "aggregate": (scorecard or {}).get("aggregate"),
        "measured": measured,
        "regressions": (scorecard or {}).get("regressions", []),
        "coverage": [{"plugin": p["name"], "version": p["version"],
                      "components": p["skills"] + p["agents"] + p["commands"] + p["scripts"] + p["hooks"],
                      "evaluated": covered.get(p["name"], False)} for p in plugins],
        "usage": usage(root),
    }


def render(model: dict) -> None:
    print(f"\ncapability self-model — {model['source']}"
          + (f" @ {model['sha']}" if model.get("sha") else ""))

    if not model["measured"]:
        print("\n  nothing measured yet — no scorecard. Run the eval suite; a self-model without "
              "evidence would be assertion, which is the thing ADR-0012 forbids.")
    else:
        print("\nmeasured capabilities:")
        for cap in model["measured"]:
            arrow = {"up": "↑", "down": "↓", "steady": "→", "new": "•"}[cap["trend"]]
            flags = []
            if cap["weak"]:
                flags.append("WEAK")
            if cap["thin_evidence"]:
                flags.append("thin evidence: 1 eval")
            flag_text = ("   [" + ", ".join(flags) + "]") if flags else ""
            print(f"  {arrow} {cap['score']:.2f}  {cap['capability']}"
                  f"  ({len(cap['evals'])} eval(s)){flag_text}")

    if model["regressions"]:
        print("\nactive regressions (fix before anything else):")
        for reg in model["regressions"]:
            print(f"  {reg['id']}: {reg['was']:.2f} → {reg['now']:.2f}")

    gaps = [c for c in model["coverage"] if not c["evaluated"]]
    print("\ninventory coverage:")
    for c in model["coverage"]:
        mark = "evaluated" if c["evaluated"] else "UNMEASURED"
        print(f"  {c['plugin']:<20} v{c['version']:<8} {c['components']:>3} components   {mark}")
    if gaps:
        print(f"\n  {len(gaps)} plugin(s) no eval exercises — unmeasured is not 'assumed fine'; "
              "it is where regressions hide (ADR-0008). The frontier ranks these.")

    if model["usage"]:
        print("\nmost-exercised components (audit trail — engagement, not quality):")
        for u in model["usage"]:
            print(f"  {u['component']:<40} {u['calls']}×")


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive the capability self-model from evidence.")
    parser.add_argument("--cached", action="store_true", help="use the last ledger snapshot instead of a live run")
    parser.add_argument("--scorecard", help="derive from a supplied evalctl --json output")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--root", type=Path, default=None)
    args = parser.parse_args()

    root = args.root.resolve() if args.root else repo_root()
    if args.scorecard:
        scorecard = json.loads(Path(args.scorecard).read_text(encoding="utf-8"))
        scorecard.setdefault("_source", f"supplied scorecard {args.scorecard}")
    else:
        scorecard = run_scorecard(root, args.cached)

    model = derive(root, scorecard)
    if args.as_json:
        print(json.dumps(model, indent=2))
    else:
        render(model)
    return 0


if __name__ == "__main__":
    sys.exit(main())
