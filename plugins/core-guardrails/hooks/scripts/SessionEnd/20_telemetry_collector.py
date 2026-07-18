#!/usr/bin/env python3
"""telemetry-collector (SessionEnd): end-of-session rollup record + queue size guard
(cap 10 MB / oldest-first prune) so the queue never grows unbounded."""
import os

from lib import cc, telem

_CAP_BYTES = 10 * 1024 * 1024

def main() -> None:
    data = cc.read_input()
    telem.emit("session_end", data.get("session_id", ""),
               reason=data.get("reason", ""), cwd=str(data.get("cwd", ""))[-80:])
    q = telem.queue_dir()
    files = sorted(q.glob("*.jsonl"), key=lambda f: f.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    while total > _CAP_BYTES and files:
        f = files.pop(0)
        try:
            total -= f.stat().st_size
            f.unlink()
            telem.emit("queue_overflow", data.get("session_id", ""), dropped=f.name)
        except OSError:
            break
    cc.allow()

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
