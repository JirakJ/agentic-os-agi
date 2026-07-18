#!/usr/bin/env python3
"""Capability verifier: the mission lifecycle holds end-to-end.

Drives mission.py as a black box against a temp dir: create, advance, block (reason required),
refuse dishonest completion, resume, complete, brief silence. Prints one JSON line.
"""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path


def find_tool() -> Path | None:
    for c in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        candidate = c / "plugins" / "long-horizon" / "scripts" / "mission.py"
        if candidate.is_file():
            return candidate
    return None


def main() -> int:
    tool = find_tool()
    if tool is None:
        print(json.dumps({"pass": False, "score": 0.0, "detail": "mission.py missing"})); return 0

    with tempfile.TemporaryDirectory() as raw:
        base = str(Path(raw) / "missions")

        def run(*args: str):
            return subprocess.run([sys.executable, str(tool), "--dir", base, *args],
                                  capture_output=True, text=True, timeout=20)

        checks: dict[str, bool] = {}

        created = run("new", "Verify goal", "--objective", "Two steps done.", "--steps", "one;two")
        checks["creates a mission"] = created.returncode == 0 and "m-0001" in created.stdout

        listed = run("list")
        checks["lists it active"] = "m-0001" in listed.stdout and "active" in listed.stdout

        advanced = run("step-done", "m-0001", "1", "--note", "proof")
        checks["advances a step"] = advanced.returncode == 0 and "step 1 done" in advanced.stdout

        premature = run("complete", "m-0001")
        checks["refuses completion with open steps"] = premature.returncode == 1

        blocked = run("block", "m-0001", "--on", "missing dependency")
        checks["blocks with a reason"] = blocked.returncode == 0 and "missing dependency" in blocked.stdout

        brief = run("brief")
        checks["brief surfaces the blocker"] = "BLOCKED" in brief.stdout and "missing dependency" in brief.stdout

        resumed = run("resume", "m-0001")
        checks["resumes"] = resumed.returncode == 0

        run("step-done", "m-0001", "2")
        completed = run("complete", "m-0001")
        checks["completes when all steps done"] = completed.returncode == 0 and "done" in completed.stdout

        silent = run("brief")
        checks["brief is silent when nothing is in flight"] = silent.returncode == 0 and silent.stdout.strip() == ""

        second = run("new", "Another")
        checks["ids never reused"] = "m-0002" in second.stdout

        passed, total = sum(checks.values()), len(checks)
        failed = [k for k, v in checks.items() if not v]
        print(json.dumps({"pass": passed == total, "score": round(passed / total, 4),
                          "detail": "" if passed == total else "failed: " + ", ".join(failed)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
