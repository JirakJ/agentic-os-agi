#!/usr/bin/env python3
"""Capability verifier: the frontier ranks by evidence severity and stays empty on empty inputs.

Feeds frontier.py a controlled self-model (one weakness, one coverage gap) and a temp missions dir
with one blocked mission; asserts weakness > blocked intent > coverage gap, every item carries
evidence, and clean inputs yield an empty agenda. Prints one JSON line.
"""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path


def find_root() -> Path | None:
    for c in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (c / "plugins" / "long-horizon" / "scripts" / "frontier.py").is_file():
            return c
    return None


def main() -> int:
    root = find_root()
    if root is None:
        print(json.dumps({"pass": False, "score": 0.0, "detail": "frontier.py missing"})); return 0
    frontier = root / "plugins" / "long-horizon" / "scripts" / "frontier.py"
    mission = root / "plugins" / "long-horizon" / "scripts" / "mission.py"

    model = {
        "source": "fixture", "regressions": [],
        "measured": [
            {"capability": "weakcap", "score": 0.5, "trend": "down", "evals": ["a", "b"],
             "weak": True, "thin_evidence": False},
            {"capability": "finecap", "score": 1.0, "trend": "steady", "evals": ["c", "d"],
             "weak": False, "thin_evidence": False},
        ],
        "coverage": [
            {"plugin": "gapless", "version": "1.0.0", "components": 5, "evaluated": True},
            {"plugin": "gapped", "version": "1.0.0", "components": 4, "evaluated": False},
        ],
        "usage": [],
    }

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        model_file = tmp / "model.json"
        model_file.write_text(json.dumps(model))
        missions = tmp / "missions"
        subprocess.run([sys.executable, str(mission), "--dir", str(missions),
                        "new", "Stalled goal", "--steps", "x", "--priority", "high"],
                       capture_output=True, text=True, timeout=20)
        subprocess.run([sys.executable, str(mission), "--dir", str(missions),
                        "block", "m-0001", "--on", "missing capability"],
                       capture_output=True, text=True, timeout=20)

        result = subprocess.run([sys.executable, str(frontier), "--model", str(model_file),
                                 "--missions-dir", str(missions), "--no-mine", "--json",
                                 "--root", str(root)],
                                capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            print(json.dumps({"pass": False, "score": 0.0,
                              "detail": f"frontier failed: {result.stderr.strip()[:80]}"})); return 0
        agenda = json.loads(result.stdout)["items"]
        kinds = [item["kind"] for item in agenda]

        checks = {
            "weakness present": "weakness" in kinds,
            "blocked intent present": "blocked-intent" in kinds,
            "coverage gap present": "coverage-gap" in kinds,
            "weakness outranks blocked intent": kinds.index("weakness") < kinds.index("blocked-intent")
                if {"weakness", "blocked-intent"} <= set(kinds) else False,
            "blocked intent outranks coverage gap": kinds.index("blocked-intent") < kinds.index("coverage-gap")
                if {"blocked-intent", "coverage-gap"} <= set(kinds) else False,
            "healthy capability absent": not any("finecap" in item["id"] for item in agenda),
            "every item carries evidence": all(item.get("evidence") for item in agenda),
        }

        # clean inputs → empty agenda
        clean_model = tmp / "clean.json"
        clean_model.write_text(json.dumps({
            "source": "fixture", "regressions": [],
            "measured": [{"capability": "finecap", "score": 1.0, "trend": "steady",
                          "evals": ["c", "d"], "weak": False, "thin_evidence": False}],
            "coverage": [{"plugin": "gapless", "version": "1.0.0", "components": 5, "evaluated": True}],
            "usage": [],
        }))
        empty_missions = tmp / "none"
        empty_missions.mkdir()
        clean = subprocess.run([sys.executable, str(frontier), "--model", str(clean_model),
                                "--missions-dir", str(empty_missions), "--no-mine", "--json",
                                "--root", str(root)],
                               capture_output=True, text=True, timeout=30)
        checks["clean inputs yield an empty agenda"] = (
            clean.returncode == 0 and json.loads(clean.stdout)["items"] == [])

        passed, total = sum(checks.values()), len(checks)
        failed = [k for k, v in checks.items() if not v]
        print(json.dumps({"pass": passed == total, "score": round(passed / total, 4),
                          "detail": "" if passed == total else "failed: " + ", ".join(failed)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
