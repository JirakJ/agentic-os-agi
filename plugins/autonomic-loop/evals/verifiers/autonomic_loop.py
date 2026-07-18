#!/usr/bin/env python3
"""Capability verifier: the autonomic reflexes hold — sense, verify, block, brief, kill switch.

Builds a throwaway marketplace containing a copy of the eval harness and a two-eval mini suite
whose second eval toggles on a marker file — so a regression can be forced on demand without ever
touching the real suite (and without recursion: the mini suite does not contain this eval). Drives
the hooks exactly as Claude Code would: stdin payloads, env, stdout contracts. Prints one JSON
line.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def find_root() -> Path | None:
    for c in [Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents]:
        if (c / "plugins" / "autonomic-loop" / "hooks" / "scripts" / "verify_on_change.py").is_file():
            return c
    return None


def build_market(tmp: Path, real_root: Path) -> Path:
    market = tmp / "market"
    (market / ".claude-plugin").mkdir(parents=True)
    (market / ".claude-plugin" / "marketplace.json").write_text('{"name":"t","plugins":[]}')
    se = market / "plugins" / "self-evolution"
    (se / ".claude-plugin").mkdir(parents=True)
    (se / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "self-evolution", "version": "1.1.0", "description": "x"}))
    (se / "scripts").mkdir()
    shutil.copy2(real_root / "plugins" / "self-evolution" / "scripts" / "evalctl.py",
                 se / "scripts" / "evalctl.py")
    evals = se / "evals"
    evals.mkdir()
    (evals / "always-pass.json").write_text(json.dumps({
        "id": "always-pass", "capability": "control", "kind": "invariant", "description": "x",
        "verifier": {"type": "exit_zero", "command": ["python3", "-c", "raise SystemExit(0)"]}}))
    (evals / "toggle.json").write_text(json.dumps({
        "id": "toggle", "capability": "control", "kind": "invariant", "description": "x",
        "verifier": {"type": "exit_zero", "command": [
            "python3", "-c",
            "import os,sys; sys.exit(0 if os.path.exists(os.path.join('${REPO_ROOT}','MARKER')) else 1)"]}}))
    (evals / "baseline.json").write_text(json.dumps({
        "ts": "t", "sha": "t", "aggregate": 1.0,
        "scores": {"always-pass": 1.0, "toggle": 1.0},
        "by_capability": {"control": 1.0}}))
    (market / "MARKER").write_text("present")
    return market


def main() -> int:
    root = find_root()
    if root is None:
        print(json.dumps({"pass": False, "score": 0.0, "detail": "autonomic-loop scripts missing"}))
        return 0
    hooks = root / "plugins" / "autonomic-loop" / "hooks" / "scripts"

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        market = build_market(tmp, root)
        data = tmp / "data"

        def drive(script: str, payload: dict, extra_env: dict | None = None) -> tuple[int, str]:
            env = {**os.environ,
                   "CLAUDE_PLUGIN_ROOT": str(root / "plugins" / "autonomic-loop"),
                   "CLAUDE_PLUGIN_DATA": str(data), **(extra_env or {})}
            env.pop("AGENTIC_OS_AUTONOMIC", None)
            if extra_env and "AGENTIC_OS_AUTONOMIC" in extra_env:
                env["AGENTIC_OS_AUTONOMIC"] = extra_env["AGENTIC_OS_AUTONOMIC"]
            result = subprocess.run([sys.executable, str(hooks / script)],
                                    input=json.dumps(payload), capture_output=True,
                                    text=True, env=env, timeout=90)
            return result.returncode, result.stdout.strip()

        checks: dict[str, bool] = {}
        core_edit = {"session_id": "e1", "cwd": str(market),
                     "tool_input": {"file_path": str(market / "plugins" / "self-evolution" / "scripts" / "evalctl.py")}}
        outside_edit = {"session_id": "e2", "cwd": str(market),
                        "tool_input": {"file_path": str(market / "notes.md")}}

        drive("change_sentinel.py", core_edit)
        checks["sentinel marks a core edit"] = (data / "state" / "dirty-e1.json").is_file()
        drive("change_sentinel.py", outside_edit)
        checks["sentinel ignores a non-core edit"] = not (data / "state" / "dirty-e2.json").is_file()

        code, out = drive("verify_on_change.py", {"session_id": "clean", "cwd": str(market)})
        checks["clean session stops silently"] = code == 0 and out == ""

        code, out = drive("verify_on_change.py", {"session_id": "e1", "cwd": str(market)})
        checks["green verify allows the stop"] = code == 0 and out == ""
        checks["green verify clears the debt"] = not (data / "state" / "dirty-e1.json").is_file()
        checks["green verify records the state"] = (data / "state" / "last-verify.json").is_file()

        # force a regression: the toggle eval fails once the marker is gone
        (market / "MARKER").unlink()
        drive("change_sentinel.py", {**core_edit, "session_id": "e3"})
        code, out = drive("verify_on_change.py", {"session_id": "e3", "cwd": str(market)})
        blocked = {}
        try:
            blocked = json.loads(out) if out else {}
        except json.JSONDecodeError:
            blocked = {}
        checks["regression blocks the stop"] = blocked.get("decision") == "block"
        checks["block reason names the failure"] = "toggle" in blocked.get("reason", "")
        checks["debt survives a failed verify"] = (data / "state" / "dirty-e3.json").is_file()

        code, out = drive("verify_on_change.py",
                          {"session_id": "e3", "cwd": str(market), "stop_hook_active": True})
        checks["loop guard passes the second stop"] = code == 0 and out == ""

        code, out = drive("autonomic_brief.py", {"cwd": str(market)})
        brief = {}
        try:
            brief = json.loads(out) if out else {}
        except json.JSONDecodeError:
            brief = {}
        context = brief.get("hookSpecificOutput", {}).get("additionalContext", "")
        checks["brief surfaces the standing regression"] = "STANDING REGRESSION" in context and "toggle" in context

        fresh = tmp / "fresh-data"
        code, out = drive("autonomic_brief.py", {"cwd": str(market)},
                          {"CLAUDE_PLUGIN_DATA": str(fresh)})
        checks["brief is silent with no state"] = code == 0 and out == ""

        code, out = drive("change_sentinel.py", {**core_edit, "session_id": "ks"},
                          {"AGENTIC_OS_AUTONOMIC": "off"})
        checks["kill switch silences the reflexes"] = not (data / "state" / "dirty-ks.json").is_file()

        passed, total = sum(checks.values()), len(checks)
        failed = [k for k, v in checks.items() if not v]
        print(json.dumps({"pass": passed == total, "score": round(passed / total, 4),
                          "detail": "" if passed == total else "failed: " + ", ".join(failed)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
