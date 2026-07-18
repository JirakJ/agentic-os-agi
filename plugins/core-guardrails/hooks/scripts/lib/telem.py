"""Telemetry: per-session append-only JSONL queue. Records < 4 KiB => atomic POSIX append.

Queue root: $JJ_VAULT_ROOT/70-telemetry/queue if the vault exists, else ~/.jj-agentic-os/telemetry/queue.
A single flock-guarded drainer (memory_reader / rollup) consumes files; writers only append
to their own session file, so there is no cross-process write contention.
"""
from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path

from lib import cc

SCHEMA_VERSION = 3

def vault_root() -> Path | None:
    v = os.environ.get("JJ_VAULT_ROOT")
    if v and Path(v).is_dir():
        return Path(v)
    dflt = Path.home() / "jj-vault"
    return dflt if dflt.is_dir() else None

def queue_dir() -> Path:
    v = vault_root()
    base = (v / "70-telemetry" / "queue") if v else (cc.home_dir() / "telemetry" / "queue")
    base.mkdir(parents=True, exist_ok=True)
    return base

def emit(event: str, session_id: str = "", **detail) -> None:
    """Best-effort, never raises: telemetry loss must not break a session."""
    try:
        rec = {
            "schema_version": SCHEMA_VERSION,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": session_id or os.environ.get("CLAUDE_SESSION_ID", "unknown"),
            "host": socket.gethostname(),
            "event": event,
            "detail": detail,
        }
        line = json.dumps(rec, ensure_ascii=False)
        if len(line) > 3900:
            rec["detail"] = {"_truncated": True}
            line = json.dumps(rec)
        path = queue_dir() / f"{rec['session_id']}.jsonl"
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except Exception:
        pass
