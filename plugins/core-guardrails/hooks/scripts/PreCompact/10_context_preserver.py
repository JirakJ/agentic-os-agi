#!/usr/bin/env python3
"""PreCompact context-preserver: snapshot session-critical state to
.claude/session-anchor.md so the paired SessionStart(source=compact) injection restores it
after compaction. Belt-and-suspenders against context loss."""
import pathlib
import time

from lib import cc, gitutil, telem

def main() -> None:
    data = cc.read_input()
    cwd = pathlib.Path(data.get("cwd") or ".")
    anchor_dir = cwd / ".claude"
    try:
        anchor_dir.mkdir(exist_ok=True)
    except OSError:
        cc.allow()
    status = gitutil.status_porcelain(str(cwd))[:1500]
    branch = gitutil.run(["rev-parse", "--abbrev-ref", "HEAD"], cwd=str(cwd)).stdout.strip()
    body = [
        f"# Session anchor - {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        f"trigger: {data.get('trigger', 'unknown')} compaction",
        f"branch: {branch or 'n/a'}",
        "",
        "## Uncommitted changes",
        status or "(clean)",
        "",
        "## Standing rules",
        "- Commit only via the commit-integrity gate (scripts/preflight.sh -> attestation).",
        "- No placeholders; production-ready only; Conventional Commits.",
    ]
    try:
        (anchor_dir / "session-anchor.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        telem.emit("precompact_anchor", data.get("session_id", ""), branch=branch)
    except OSError:
        pass
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
