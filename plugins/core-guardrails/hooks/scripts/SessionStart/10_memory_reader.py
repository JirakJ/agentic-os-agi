#!/usr/bin/env python3
"""memory-reader (SessionStart): drain the capture queue (flock-guarded, orphan-safe),
then inject recent memory into context as plain stdout (SessionStart channel):
last 3 daily notes + open decisions + the PreCompact anchor after a compaction resume.
Fail-open, injection capped under the 10k output limit."""
import json
import os
import pathlib
import time

from lib import cc, telem

def _drain(vault: pathlib.Path) -> int:
    """Move capture records into 00-inbox notes. Single-consumer via lock file."""
    q = vault / "70-telemetry" / "queue"
    if not q.is_dir():
        return 0
    lock = q / ".drain.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # Stale lock (> 5 min) from a crashed drainer is reclaimed.
        try:
            if time.time() - lock.stat().st_mtime > 300:
                lock.unlink()
                fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            else:
                return 0
        except OSError:
            return 0
    processed = q / "processed"
    processed.mkdir(exist_ok=True)
    n = 0
    try:
        for f in sorted(q.glob("*.jsonl")):
            captures = []
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    rec = json.loads(line)
                except Exception:
                    continue  # partial last line from a crashed writer
                if rec.get("event") == "capture":
                    captures.append(rec)
            if captures:
                day = time.strftime("%Y-%m-%d")
                note = vault / "00-inbox" / f"capture-{day}-{f.stem[:12]}.md"
                body = ["---", "schema: 2", "type: capture",
                        f"session_id: {f.stem}", f"captured: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
                        "source: hook", "---", "",
                        "# Session capture (raw, refine via /memory-capture)", ""]
                for c in captures:
                    for ln in c.get("detail", {}).get("lines", [])[:40]:
                        body.append(f"- {ln}")
                note.parent.mkdir(exist_ok=True)
                note.write_text("\n".join(body) + "\n", encoding="utf-8")
                n += 1
            f.rename(processed / f.name)  # atomic commit point
        # retention: prune processed > 30 days
        cutoff = time.time() - 30 * 86400
        for old in processed.glob("*.jsonl"):
            try:
                if old.stat().st_mtime < cutoff:
                    old.unlink()
            except OSError:
                pass
    finally:
        os.close(fd)
        try:
            lock.unlink()
        except OSError:
            pass
    return n

def main() -> None:
    data = cc.read_input()
    source = data.get("source", "startup")
    parts: list[str] = []
    root = telem.vault_root()
    if root:
        drained = _drain(root)
        if drained:
            parts.append(f"[memory] Drained {drained} pending capture file(s) into 00-inbox.")
        dailies = sorted((root / "10-daily").glob("*.md"))[-3:]
        for d in dailies:
            try:
                txt = d.read_text(encoding="utf-8", errors="replace")
                parts.append(f"## Daily note {d.stem}\n{txt[:1200]}")
            except OSError:
                pass
        open_dec = []
        for dec in sorted((root / "20-decisions").glob("*.md"))[-20:]:
            try:
                head = dec.read_text(encoding="utf-8", errors="replace")[:400]
                if "status: proposed" in head or "status: accepted" in head:
                    open_dec.append(dec.stem)
            except OSError:
                pass
        if open_dec:
            parts.append("## Open decisions\n" + ", ".join(open_dec[-10:]))
    if source == "compact":
        anchor = pathlib.Path(data.get("cwd") or ".") / ".claude" / "session-anchor.md"
        if anchor.exists():
            parts.append("## Session anchor (pre-compaction state)\n" +
                         anchor.read_text(encoding="utf-8", errors="replace")[:2500])
    if not parts:
        cc.allow()
    cc.plain("<agentic-os-memory>\n" + "\n\n".join(parts)[:9000] + "\n</agentic-os-memory>")

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        cc.allow()
