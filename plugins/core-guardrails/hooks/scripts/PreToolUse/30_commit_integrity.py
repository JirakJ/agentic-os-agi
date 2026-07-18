#!/usr/bin/env python3
"""commit-integrity: only fully tested, buildable, runnable, error-free code without new
security debt gets committed.

Attestation pattern: scripts/preflight.sh runs the full pipeline out-of-band on the exact
staged tree (git write-tree identity) and writes .git/jj-attest/<tree>.json. This hook is
the <50ms verifier: fresh + green + tree-matching + toolchain-matching, else deny with an
actionable instruction. `git commit --no-verify` cannot bypass it (Claude-level hook, not a
git hook); the only override is /gate-unlock. Fail mode: CLOSED when enforcing.
Push policy: `git push` re-verifies that HEAD's tree has a green attestation on file.
"""
import json
import pathlib
import re
import sys
import time

from lib import cc, gates, gitutil, telem

GATE = "commit-integrity"
_GIT_RE = re.compile(r"\bgit(?:\s+-C\s+(?P<cdir>\S+))?\s+(?P<sub>commit|push)\b")
_RETRY_MAX = 3

def _parse_ts(ts: str) -> float:
    try:
        return time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
    except Exception:
        return 0.0

def _retry_count(sid: str, tree: str) -> int:
    f = cc.home_dir() / f"retry-{sid[:24]}.json"
    try:
        d = json.loads(f.read_text())
    except Exception:
        d = {}
    n = int(d.get(tree, 0)) + 1
    try:
        f.write_text(json.dumps({tree: n}))
    except OSError:
        pass
    return n

def _deny(sid: str, tree: str, result: str, msg: str, **detail) -> None:
    telem.emit("commit_gate", sid, hook=GATE, result=result, tree_hash=tree, **detail)
    if not gates.enforcing(GATE):
        cc.system_message(f"[dry-run] commit-integrity would block: {msg}")
    n = _retry_count(sid, tree)
    if n >= _RETRY_MAX:
        msg += (" You have hit the retry cap - stop retrying, report the failing steps to "
                "the user, and ask them to run /gate-unlock if they want to override.")
    cc.deny(f"commit-integrity: {msg}")

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") != "Bash":
        cc.allow()
    cmd = str((data.get("tool_input") or {}).get("command", ""))
    m = _GIT_RE.search(cmd)
    if not m:
        cc.allow()
    if not gates.active(GATE):
        cc.allow()
    sid = data.get("session_id", "")
    if cc.unlock_active():
        telem.emit("gate_override", sid, hook=GATE)
        cc.allow()

    cwd = m.group("cdir") or data.get("cwd") or None
    sub = m.group("sub")
    root = gitutil.toplevel(cwd)
    if not root:
        cc.allow()  # not a git repo; nothing to gate

    if sub == "push":
        # Trust the commit-time chain: HEAD's tree must have a green attestation on file.
        r = gitutil.run(["rev-parse", "HEAD^{tree}"], cwd=root)
        tree = r.stdout.strip() if r.returncode == 0 else ""
    else:
        tree = gitutil.write_tree(root) or ""
    if not tree:
        _deny(sid, "", "error", "could not resolve the staged tree (git write-tree failed). "
              "Run `scripts/preflight.sh` from the repo root, then retry.")

    att = pathlib.Path(root) / ".git" / "jj-attest" / f"{tree}.json"
    if not att.exists():
        _deny(sid, tree, "miss",
              "no build/test attestation for this exact staged tree. Run "
              "`scripts/preflight.sh` (it builds, tests, lints, scans and smoke-runs the "
              "staged content and writes the attestation), then retry the commit.")
    try:
        a = json.loads(att.read_text(encoding="utf-8"))
    except Exception:
        _deny(sid, tree, "error", "attestation unreadable. Rerun `scripts/preflight.sh`.")
    if a.get("overall") != "green":
        failed = [k for k, v in (a.get("results") or {}).items()
                  if v.get("status") not in ("pass", "skipped")]
        _deny(sid, tree, "red",
              f"preflight is RED on: {', '.join(failed) or 'unknown'}. Fix those, rerun "
              "`scripts/preflight.sh`, then retry the commit.",
              failed_steps=failed)
    age = time.time() - _parse_ts(str(a.get("ts", "")))
    ttl = int(a.get("ttl_s", 1800))
    if age > ttl:
        _deny(sid, tree, "stale",
              f"attestation is stale ({int(age)}s old, TTL {ttl}s). Rerun "
              "`scripts/preflight.sh`, then retry.", age_s=int(age))
    telem.emit("commit_gate", sid, hook=GATE, result="pass", tree_hash=tree, age_s=int(age))
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        if gates.enforcing(GATE):
            cc.deny(f"commit-integrity internal error (fail-closed): {e}. "
                    "Run scripts/preflight.sh; /gate-unlock to override.")
        cc.allow()
