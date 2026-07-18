#!/usr/bin/env python3
"""Capability verifier: the ADR lifecycle holds end-to-end.

Builds a throwaway marketplace, creates a record, supersedes it, and asserts the supersession chain
is consistent on both ends. Prints one JSON line: {"pass", "score", "detail"}.

This is a functional test of the `governance` capability as a black box — it drives adr_new.py
exactly as a caller would, so a regression in the tool shows up as a failed eval, which is the
signal the self-improvement loop gates on (ADR-0008).
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def find_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            return candidate
    raise SystemExit(json.dumps({"pass": False, "score": 0.0, "detail": "marketplace root not found"}))


def read_field(path: Path, field: str) -> str | None:
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    for line in text[3:end].splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            if key.strip() == field:
                return value.strip()
    return None


def main() -> int:
    root = find_root()
    adr_new = root / "plugins" / "core-orchestration" / "scripts" / "adr_new.py"
    if not adr_new.is_file():
        print(json.dumps({"pass": False, "score": 0.0, "detail": "adr_new.py missing"}))
        return 0

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        (tmp / ".claude-plugin").mkdir()
        (tmp / ".claude-plugin" / "marketplace.json").write_text('{"name":"t","plugins":[]}')

        def run(*args: str):
            return subprocess.run([sys.executable, str(adr_new), *args, "--root", str(tmp)],
                                  capture_output=True, text=True, timeout=20)

        r1 = run("First decision", "--status", "accepted")
        if r1.returncode != 0:
            print(json.dumps({"pass": False, "score": 0.0, "detail": f"create failed: {r1.stderr.strip()[:80]}"}))
            return 0
        first = next((tmp / "adr").glob("0001-*.md"), None)
        if first is None:
            print(json.dumps({"pass": False, "score": 0.0, "detail": "ADR-0001 not created"}))
            return 0

        r2 = run("Replacement decision", "--supersedes", "0001")
        if r2.returncode != 0:
            print(json.dumps({"pass": False, "score": 0.0, "detail": f"supersede failed: {r2.stderr.strip()[:80]}"}))
            return 0
        second = next((tmp / "adr").glob("0002-*.md"), None)
        if second is None:
            print(json.dumps({"pass": False, "score": 0.0, "detail": "ADR-0002 not created"}))
            return 0

        checks = {
            "old status flipped": read_field(first, "status") == "superseded",
            "old points to new": "0002" in (read_field(first, "superseded-by") or ""),
            "new declares supersedes": "0001" in (read_field(second, "supersedes") or ""),
            "new is proposed": read_field(second, "status") == "proposed",
        }

        # Numbers must never be reused: a third record allocates 0003.
        run("Third decision")
        checks["numbers not reused"] = (tmp / "adr" / "0003-third-decision.md").is_file()

        # Superseding a non-existent record must fail.
        bad = run("Bogus", "--supersedes", "9999")
        checks["rejects bad supersede"] = bad.returncode == 1

        passed = sum(checks.values())
        total = len(checks)
        failed = [k for k, v in checks.items() if not v]
        print(json.dumps({
            "pass": passed == total,
            "score": round(passed / total, 4),
            "detail": "" if passed == total else "failed: " + ", ".join(failed),
        }))
    return 0


if __name__ == "__main__":
    sys.exit(main())
