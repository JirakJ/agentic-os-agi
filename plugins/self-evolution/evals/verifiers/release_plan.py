#!/usr/bin/env python3
"""Capability verifier: the release tool derives a correct bump and a valid dry-run plan.

Builds a throwaway git repo with a plugin and a feat commit, then asserts release.py --dry-run
derives a minor bump and writes nothing. Prints one JSON line.
"""
from __future__ import annotations
import json, subprocess, sys, tempfile
from pathlib import Path


def find_root() -> Path:
    for c in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (c / ".claude-plugin" / "marketplace.json").is_file():
            return c
    raise SystemExit(json.dumps({"pass": False, "score": 0.0, "detail": "root not found"}))


def git(*a, cwd):
    return subprocess.run(("git", *a), cwd=cwd, capture_output=True, text=True)


def main() -> int:
    root = find_root()
    release = root / "plugins" / "core-orchestration" / "scripts" / "release.py"
    if not release.is_file():
        print(json.dumps({"pass": False, "score": 0.0, "detail": "release.py missing"})); return 0

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        (tmp / ".claude-plugin").mkdir()
        (tmp / "plugins" / "demo" / ".claude-plugin").mkdir(parents=True)
        (tmp / ".claude-plugin" / "marketplace.json").write_text(
            json.dumps({"name": "t", "plugins": [{"name": "demo", "source": "./plugins/demo"}]}))
        (tmp / "plugins" / "demo" / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "demo", "version": "1.0.0", "description": "x"}))

        git("init", "-q", cwd=tmp)
        git("config", "user.email", "t@e.com", cwd=tmp)
        git("config", "user.name", "T", cwd=tmp)
        git("config", "commit.gpgsign", "false", cwd=tmp)
        git("add", "-A", cwd=tmp)
        git("commit", "-q", "-m", "chore: init", cwd=tmp)
        # a feature commit touching the plugin → should derive a minor bump
        (tmp / "plugins" / "demo" / "feature.txt").write_text("x")
        git("add", "-A", cwd=tmp)
        git("commit", "-q", "-m", "feat(demo): add a capability", cwd=tmp)

        result = subprocess.run(
            [sys.executable, str(release), "demo", "--dry-run", "--root", str(tmp)],
            capture_output=True, text=True, timeout=25)
        out = result.stdout

        checks = {
            "dry-run succeeds": result.returncode == 0,
            "derives minor bump": "1.0.0 → 1.1.0 (minor)" in out,
            "plans the tag": "demo/v1.1.0" in out,
            "writes nothing": "nothing written" in out,
        }
        # nothing was written: manifest still 1.0.0
        after = json.loads((tmp / "plugins" / "demo" / ".claude-plugin" / "plugin.json").read_text())
        checks["manifest untouched"] = after.get("version") == "1.0.0"
        # no tag created by a dry run
        checks["no tag created"] = git("tag", "--list", "demo/v1.1.0", cwd=tmp).stdout.strip() == ""

        passed, total = sum(checks.values()), len(checks)
        failed = [k for k, v in checks.items() if not v]
        print(json.dumps({"pass": passed == total, "score": round(passed / total, 4),
                          "detail": "" if passed == total else "failed: " + ", ".join(failed)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
