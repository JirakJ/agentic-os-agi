#!/usr/bin/env python3
"""Capability verifier: the self-model derives calibrated claims from evidence.

Feeds selfmodel.py a controlled scorecard (one weak capability, one strong, one thin) and asserts
the derivation: weak flagged, strong not, thin evidence marked, coverage structural. Prints one
JSON line.
"""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path


def find_tool() -> Path | None:
    for c in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        candidate = c / "plugins" / "long-horizon" / "scripts" / "selfmodel.py"
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    tool = find_tool()
    if tool is None:
        print(json.dumps({"pass": False, "score": 0.0, "detail": "selfmodel.py missing"})); return 0

    scorecard = {
        "aggregate": 0.83, "sha": "fixture", "regressions": [],
        "results": [
            {"id": "weak-a", "capability": "weakcap", "pass": False, "score": 0.5, "detail": "x"},
            {"id": "weak-b", "capability": "weakcap", "pass": True, "score": 0.6, "detail": ""},
            {"id": "strong-a", "capability": "strongcap", "pass": True, "score": 1.0, "detail": ""},
            {"id": "strong-b", "capability": "strongcap", "pass": True, "score": 1.0, "detail": ""},
            {"id": "thin-a", "capability": "thincap", "pass": True, "score": 1.0, "detail": ""},
        ],
    }
    with tempfile.TemporaryDirectory() as raw:
        card = Path(raw) / "card.json"
        card.write_text(json.dumps(scorecard))
        result = subprocess.run([sys.executable, str(tool), "--scorecard", str(card), "--json"],
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            print(json.dumps({"pass": False, "score": 0.0,
                              "detail": f"selfmodel failed: {result.stderr.strip()[:80]}"})); return 0
        model = json.loads(result.stdout)

    caps = {c["capability"]: c for c in model.get("measured", [])}
    checks = {
        "weak capability flagged": caps.get("weakcap", {}).get("weak") is True,
        "weak score averaged": abs(caps.get("weakcap", {}).get("score", 0) - 0.55) < 1e-6,
        "strong capability not flagged": caps.get("strongcap", {}).get("weak") is False,
        "thin evidence marked": caps.get("thincap", {}).get("thin_evidence") is True,
        "multi-eval capability not thin": caps.get("strongcap", {}).get("thin_evidence") is False,
        "coverage reported per plugin": bool(model.get("coverage"))
            and all("plugin" in c and "evaluated" in c for c in model["coverage"]),
    }
    passed, total = sum(checks.values()), len(checks)
    failed = [k for k, v in checks.items() if not v]
    print(json.dumps({"pass": passed == total, "score": round(passed / total, 4),
                      "detail": "" if passed == total else "failed: " + ", ".join(failed)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
