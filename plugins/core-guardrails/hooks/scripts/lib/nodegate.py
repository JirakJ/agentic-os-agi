"""Shared runner for Stop-hook gates that delegate to a vendored Node script.

security-gate, test-gate and i18n-complete were machine-local ~/.claude/hooks/*.mjs
scripts wired directly in settings.json - a second, unconfigurable gate runtime for
concerns core-guardrails already owns (ADR-0022, ADR-0027). This module is what makes
gates.json the *only* source of truth for their mode: it passes the original Stop
payload through to the vendored .mjs unchanged (so the script's own stop_hook_active
loop guard still applies), then translates the script's exit code through gates.py:

    off      - skip before ever invoking node
    dryrun   - a non-zero exit becomes a systemMessage advisory; Stop is never blocked
    enforce  - a non-zero exit becomes sys.exit(2), which dispatch.sh's fail-closed
               path (the "Hard block path (fail-closed hooks)" branch) turns into a
               real Stop block, stderr fed back to Claude - the exact contract the
               vendored script already speaks natively.

A missing `node` binary or a timeout fails OPEN (advisory + telemetry), matching the
dispatcher's own "a broken hook must never break the session" rule; a vendored script
missing an external scanner (semgrep/osv-scanner/test runner) already reports
that gracefully on its own and exits 0.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from lib import cc, gates, telem


def run(gate: str, vendor: Path, raw_stdin: str, timeout: int) -> None:
    try:
        data = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except Exception:
        data = {}
    sid = data.get("session_id", "")

    # Cheap, low-volume marker: Stop fires once per turn-end (not per tool call like
    # PreToolUse/PostToolUse), so one record per gate per invocation is not noise - it
    # is the audit trail that proves this concern's Stop-level check actually ran.
    telem.emit("gate_checked", sid, hook=gate)

    if not gates.active(gate):
        cc.allow()

    node = shutil.which("node")
    if not node:
        telem.emit("gate_fired", sid, hook=gate, decision="advisory", reason="node_missing")
        cc.system_message(f"{gate}: node is not on PATH - Stop-level check skipped.")

    try:
        r = subprocess.run([node, str(vendor)], input=raw_stdin, capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        telem.emit("gate_fired", sid, hook=gate, decision="advisory", reason="timeout")
        cc.system_message(f"{gate}: scan timed out after {timeout}s - not blocking Stop; "
                           "investigate manually.")

    if r.returncode == 0:
        cc.allow()

    detail = (r.stderr or r.stdout or f"{gate}: unspecified failure").strip()[-4000:]
    if gates.enforcing(gate):
        telem.emit("gate_fired", sid, hook=gate, decision="block")
        print(detail, file=sys.stderr)
        sys.exit(2)
    telem.emit("gate_fired", sid, hook=gate, decision="advisory")
    cc.system_message(f"[dry-run] {gate} would block Stop:\n{detail}")
