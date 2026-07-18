#!/usr/bin/env python3
"""test-gate: after a source edit, run the repo's scoped test command (from preflight.toml
[commands].test). On failure emit decision=block so Claude fixes forward immediately.
Debounced per session+file (60s). enforce = run tests; dryrun = advisory reminder only."""
import json
import pathlib
import subprocess
import sys
import time

from lib import cc, gates, gitutil, telem

GATE = "test-gate"
_SRC_EXT = {".py", ".ts", ".tsx", ".js", ".swift", ".java", ".kt", ".rs", ".cpp", ".cc", ".hpp", ".h", ".c"}

def _test_cmd(root: pathlib.Path) -> str | None:
    cfg = root / "preflight.toml"
    if not cfg.exists():
        return None
    try:
        import tomllib
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
        return (data.get("commands") or {}).get("test")
    except Exception:
        return None

def _debounced(sid: str, path: str) -> bool:
    stamp = cc.home_dir() / f"testgate-{sid[:24]}.json"
    now = time.time()
    try:
        d = json.loads(stamp.read_text())
    except Exception:
        d = {}
    if now - float(d.get(path, 0)) < 60:
        return True
    d[path] = now
    try:
        stamp.write_text(json.dumps(d))
    except OSError:
        pass
    return False

def main() -> None:
    data = cc.read_input()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit") or not gates.active(GATE):
        cc.allow()
    path = str((data.get("tool_input") or {}).get("file_path") or "")
    if not path or pathlib.Path(path).suffix not in _SRC_EXT or "/tests/" in path:
        cc.allow()
    sid = data.get("session_id", "")
    if _debounced(sid, path):
        cc.allow()
    root_s = gitutil.toplevel(data.get("cwd"))
    if not root_s:
        cc.allow()
    root = pathlib.Path(root_s)
    cmd = _test_cmd(root)
    if not gates.enforcing(GATE) or not cmd:
        telem.emit("gate_fired", sid, hook=GATE, decision="advisory", path=path)
        cc.allow()  # silent in dry-run: preflight covers the commit boundary
    try:
        # Shell is required: `cmd` is the `commands.test` shell snippet from the repo's own
        # preflight.toml, not an argv list. Running it is the point of this gate, and the
        # test command it names already executes that repo's code. See ADR-0005.
        # nosemgrep: python.lang.security.audit.subprocess-shell-true.subprocess-shell-true
        r = subprocess.run(cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        telem.emit("gate_fired", sid, hook=GATE, decision="advisory", path=path, timeout=True)
        cc.allow()
    if r.returncode != 0:
        tail = (r.stdout + "\n" + r.stderr)[-1800:]
        telem.emit("gate_fired", sid, hook=GATE, decision="block", path=path)
        cc.post_block(f"test-gate: tests failed after editing {path}. Fix before moving on.\n{tail}")
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
