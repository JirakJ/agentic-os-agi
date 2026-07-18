#!/usr/bin/env python3
"""memory-writer (SessionEnd): enqueue only - SessionEnd cannot run long jobs. Pre-filters
the transcript for decision/blocker/retro/fix lines and appends a capture record to the
per-session queue; the SessionStart drainer materializes the note."""
import pathlib
import re

from lib import cc, telem

_PAT = re.compile(r"(decision|decided|blocked on|blocker|next step|retro|root cause|fixed|fix:)",
                  re.IGNORECASE)

def main() -> None:
    data = cc.read_input()
    tp = data.get("transcript_path")
    if not tp:
        cc.allow()
    p = pathlib.Path(tp)
    if not p.exists():
        cc.allow()
    lines: list[str] = []
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                if _PAT.search(raw):
                    clean = re.sub(r"\s+", " ", raw).strip()
                    if 15 < len(clean) < 400:
                        lines.append(clean[:300])
                if len(lines) >= 40:
                    break
    except OSError:
        cc.allow()
    if lines:
        telem.emit("capture", data.get("session_id", ""), lines=lines[:40],
                   transcript=str(p)[-120:])
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
