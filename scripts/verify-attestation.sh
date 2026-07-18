#!/usr/bin/env bash
# Plain-git attestation verifier - the runtime-agnostic twin of the Claude commit-integrity
# hook. Used by lefthook pre-commit/pre-push and by humans. No Claude JSON: exit 0 = green,
# exit 1 = blocked (actionable message on stderr).
#
#   --staged         verify the current index; if missing/stale, RUN preflight, then verify
#   --require-fresh  verify only; never runs preflight (fast pre-push check)
#   --report         print a human-readable status table and exit 0
#
# NOTE: git hooks are bypassable with `git commit --no-verify`. The authoritative backstop
# is the server-side required status check (jj-preflight.yml) + repository ruleset.
set -euo pipefail
MODE="${1:---staged}"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo "verify-attestation: not a git repo" >&2; exit 1; }
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python)"

TREE="$(git -C "$ROOT" write-tree)"
ATT="$ROOT/.git/jj-attest/$TREE.json"

check() {
  "$PY" - "$ATT" "$MODE" <<'PYEOF'
import json, pathlib, sys, time
att_path, mode = pathlib.Path(sys.argv[1]), sys.argv[2]
def fail(msg):
    print(f"commit-integrity: {msg}", file=sys.stderr)
    print("-> run scripts/preflight.sh, fix anything red, then retry.", file=sys.stderr)
    raise SystemExit(1)
if not att_path.exists():
    fail(f"no attestation for staged tree {att_path.stem[:12]}")
a = json.loads(att_path.read_text())
if mode == "--report":
    print(f"tree      : {a['tree_hash'][:12]}  overall: {a['overall']}  ts: {a['ts']} (ttl {a['ttl_s']}s)")
    for k, v in a.get("results", {}).items():
        print(f"  {k:<9} {v['status']:<7} {v['duration_ms']:>6}ms  {v['summary'].splitlines()[0][:90]}")
    raise SystemExit(0)
if a.get("overall") != "green":
    failed = [k for k, v in a.get("results", {}).items() if v.get("status") == "fail"]
    fail("preflight RED on: " + ", ".join(failed))
ts = time.mktime(time.strptime(a["ts"], "%Y-%m-%dT%H:%M:%SZ")) - time.timezone
if time.time() - ts > a.get("ttl_s", 1800):
    fail(f"attestation stale ({int(time.time()-ts)}s old)")
print(f"commit-integrity: green attestation {a['tree_hash'][:12]} ({int(time.time()-ts)}s old)")
PYEOF
}

if [ "$MODE" = "--report" ]; then check; exit 0; fi
if check 2>/dev/null; then exit 0; fi

if [ "$MODE" = "--staged" ]; then
  echo "commit-integrity: attestation missing/stale -> running preflight on the staged tree..." >&2
  if "$DIR/preflight.sh"; then
    TREE="$(git -C "$ROOT" write-tree)"; ATT="$ROOT/.git/jj-attest/$TREE.json"
    check
    exit $?
  fi
fi
check   # re-run to print the precise reason, exits 1
