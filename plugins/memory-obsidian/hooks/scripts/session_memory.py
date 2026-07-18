#!/usr/bin/env python3
"""SessionEnd: keep the L4 index fresh for whatever the session wrote.

Runs the incremental indexer over the episodic memory dir so the next session can recall what this
one committed. Cheap because it is incremental — unchanged files are a stat and a hash comparison,
not a re-read.

Deliberately does NOT write session summaries to the vault. What is worth keeping is a judgement
call, and a hook cannot make it: the result would be a vault full of machine noise, which is exactly
what ADR-0003 puts the L2/L3 boundary there to prevent. Claude captures deliberately, via the
vault-capture skill, when there is something worth capturing.

Non-blocking: a stale index is a worse answer, not a broken session.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    plugin_root = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", Path(__file__).resolve().parents[2]))
    indexer = plugin_root / "scripts" / "index_vault.py"
    if not indexer.is_file():
        sys.exit(0)

    cwd = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path.cwd())
    memory_dir = None
    for candidate in [cwd, *cwd.parents]:
        if (candidate / ".claude-plugin" / "marketplace.json").is_file():
            if (candidate / "memory").is_dir():
                memory_dir = candidate / "memory"
            break

    args = [sys.executable, str(indexer), "--quiet"]
    if memory_dir:
        args += ["--memory", str(memory_dir)]
    if os.environ.get("AGENTIC_OS_VAULT"):
        args += ["--vault", os.environ["AGENTIC_OS_VAULT"]]

    if len(args) == 3:  # nothing to index
        sys.exit(0)

    try:
        subprocess.run(args, capture_output=True, timeout=60)
    except (subprocess.SubprocessError, OSError):
        pass

    sys.exit(0)


if __name__ == "__main__":
    main()
